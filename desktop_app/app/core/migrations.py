from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


SCHEMA_VERSION = 2


def migrate(connection: sqlite3.Connection) -> None:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema {version} is newer than supported schema {SCHEMA_VERSION}"
        )
    if version < SCHEMA_VERSION:
        _backup_before_migration(connection, version)
        assert_database_integrity(connection)
    try:
        if version < 1:
            _create_initial_schema(connection)
            version = 1
        if version < 2:
            _migrate_v2(connection)
        if version < SCHEMA_VERSION:
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.commit()
            assert_database_integrity(connection)
    except Exception:
        connection.rollback()
        raise


def assert_database_integrity(connection: sqlite3.Connection) -> None:
    integrity_rows = connection.execute("PRAGMA integrity_check").fetchall()
    messages = [str(row[0]) for row in integrity_rows]
    if messages != ["ok"]:
        raise RuntimeError("SQLite integrity check failed: " + "; ".join(messages))
    foreign_key_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_rows:
        details = "; ".join(
            f"table={row[0]}, rowid={row[1]}, parent={row[2]}" for row in foreign_key_rows[:10]
        )
        raise RuntimeError("SQLite foreign-key check failed: " + details)


def _backup_before_migration(connection: sqlite3.Connection, from_version: int) -> Path | None:
    database_row = connection.execute("PRAGMA database_list").fetchone()
    source = Path(str(database_row[2])) if database_row and database_row[2] else None
    if source is None or not source.exists() or source.stat().st_size == 0:
        return None
    backup_directory = source.parent / "backups"
    backup_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = backup_directory / f"money_manager_pre_migration_v{from_version}_{timestamp}.db"
    destination = sqlite3.connect(target)
    try:
        connection.backup(destination)
    finally:
        destination.close()
    return target


def _create_initial_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        BEGIN IMMEDIATE;
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN (
                'bank', 'current_account', 'savings_account', 'cash', 'wallet',
                'benefit', 'payment_method', 'investment', 'property',
                'credit_card', 'loan', 'mortgage', 'liability', 'other'
            )),
            parent_id INTEGER REFERENCES accounts(id),
            opening_balance NUMERIC NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            display_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            account_id INTEGER NOT NULL REFERENCES accounts(id),
            type TEXT NOT NULL CHECK (type IN ('debit_card', 'credit_card', 'paypal', 'wallet', 'other')),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
            type TEXT NOT NULL CHECK (type IN ('income', 'expense', 'transfer_out', 'transfer_in', 'adjustment')),
            account_id INTEGER NOT NULL REFERENCES accounts(id),
            payment_method_id INTEGER REFERENCES payment_methods(id),
            amount NUMERIC NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            category_id INTEGER REFERENCES categories(id),
            transfer_group_id TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_accounts_parent ON accounts(parent_id);
        CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_id);
        CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
        CREATE INDEX IF NOT EXISTS idx_transactions_transfer_group ON transactions(transfer_group_id);
        """
    )


def _migrate_v2(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        BEGIN IMMEDIATE;
        CREATE INDEX IF NOT EXISTS idx_transactions_account_date
            ON transactions(account_id, date DESC, id DESC);
        CREATE INDEX IF NOT EXISTS idx_transactions_type_date
            ON transactions(type, date DESC, id DESC);
        CREATE INDEX IF NOT EXISTS idx_transactions_category_date
            ON transactions(category_id, date DESC, id DESC);
        CREATE INDEX IF NOT EXISTS idx_transactions_account_balance
            ON transactions(account_id, amount);

        CREATE TRIGGER IF NOT EXISTS validate_accounts_insert
        BEFORE INSERT ON accounts
        WHEN NEW.is_active NOT IN (0, 1)
          OR NEW.type NOT IN (
              'bank', 'current_account', 'savings_account', 'cash', 'wallet',
              'benefit', 'payment_method', 'investment', 'property',
              'credit_card', 'loan', 'mortgage', 'liability', 'other'
          )
        BEGIN
            SELECT RAISE(ABORT, 'invalid account values');
        END;

        CREATE TRIGGER IF NOT EXISTS validate_accounts_update
        BEFORE UPDATE ON accounts
        WHEN NEW.is_active NOT IN (0, 1)
          OR NEW.type NOT IN (
              'bank', 'current_account', 'savings_account', 'cash', 'wallet',
              'benefit', 'payment_method', 'investment', 'property',
              'credit_card', 'loan', 'mortgage', 'liability', 'other'
          )
        BEGIN
            SELECT RAISE(ABORT, 'invalid account values');
        END;

        CREATE TRIGGER IF NOT EXISTS validate_categories_insert
        BEFORE INSERT ON categories
        WHEN NEW.is_active NOT IN (0, 1)
          OR NEW.type NOT IN ('income', 'expense')
          OR (NEW.is_active = 1 AND EXISTS (
              SELECT 1 FROM categories
              WHERE type = NEW.type AND lower(name) = lower(NEW.name) AND is_active = 1
          ))
        BEGIN
            SELECT RAISE(ABORT, 'invalid or duplicate category');
        END;

        CREATE TRIGGER IF NOT EXISTS validate_categories_update
        BEFORE UPDATE ON categories
        WHEN NEW.is_active NOT IN (0, 1)
          OR NEW.type NOT IN ('income', 'expense')
          OR (NEW.is_active = 1 AND EXISTS (
              SELECT 1 FROM categories
              WHERE type = NEW.type AND lower(name) = lower(NEW.name)
                AND is_active = 1 AND id != NEW.id
          ))
        BEGIN
            SELECT RAISE(ABORT, 'invalid or duplicate category');
        END;

        CREATE TRIGGER IF NOT EXISTS validate_payment_methods_insert
        BEFORE INSERT ON payment_methods
        WHEN NEW.is_active NOT IN (0, 1)
          OR NEW.type NOT IN ('debit_card', 'credit_card', 'paypal', 'wallet', 'other')
          OR (NEW.is_active = 1 AND EXISTS (
              SELECT 1 FROM payment_methods
              WHERE account_id = NEW.account_id AND lower(name) = lower(NEW.name)
                AND is_active = 1
          ))
        BEGIN
            SELECT RAISE(ABORT, 'invalid or duplicate payment method');
        END;

        CREATE TRIGGER IF NOT EXISTS validate_payment_methods_update
        BEFORE UPDATE ON payment_methods
        WHEN NEW.is_active NOT IN (0, 1)
          OR NEW.type NOT IN ('debit_card', 'credit_card', 'paypal', 'wallet', 'other')
          OR (NEW.is_active = 1 AND EXISTS (
              SELECT 1 FROM payment_methods
              WHERE account_id = NEW.account_id AND lower(name) = lower(NEW.name)
                AND is_active = 1 AND id != NEW.id
          ))
        BEGIN
            SELECT RAISE(ABORT, 'invalid or duplicate payment method');
        END;

        CREATE TRIGGER IF NOT EXISTS validate_transactions_insert
        BEFORE INSERT ON transactions
        WHEN NEW.type NOT IN ('income', 'expense', 'transfer_out', 'transfer_in', 'adjustment')
          OR NEW.date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
        BEGIN
            SELECT RAISE(ABORT, 'invalid transaction values');
        END;

        CREATE TRIGGER IF NOT EXISTS validate_transactions_update
        BEFORE UPDATE ON transactions
        WHEN NEW.type NOT IN ('income', 'expense', 'transfer_out', 'transfer_in', 'adjustment')
          OR NEW.date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
        BEGIN
            SELECT RAISE(ABORT, 'invalid transaction values');
        END;
        """
    )
