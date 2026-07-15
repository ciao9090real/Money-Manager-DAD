from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4


SCHEMA_VERSION = 7
UTC_NOW_SQL = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


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
            _run_migration(connection, 1, _create_initial_schema)
            version = 1
        if version < 2:
            _run_migration(connection, 2, _migrate_v2)
            version = 2
        if version < 3:
            # Rebuilding tables with TEXT primary keys requires foreign-key
            # enforcement to be disabled outside the migration transaction.
            connection.execute("PRAGMA foreign_keys = OFF")
            try:
                _run_migration(connection, 3, _migrate_v3)
            finally:
                connection.execute("PRAGMA foreign_keys = ON")
            version = 3
        if version < 4:
            _run_migration(connection, 4, _migrate_v4)
            version = 4
        if version < 5:
            _run_migration(connection, 5, _migrate_v5)
            version = 5
        if version < 6:
            _run_migration(connection, 6, _migrate_v6)
            version = 6
        if version < 7:
            _run_migration(connection, 7, _migrate_v7)
            version = 7
        assert_database_integrity(connection)
    except Exception:
        connection.rollback()
        connection.execute("PRAGMA foreign_keys = ON")
        raise


def _run_migration(connection: sqlite3.Connection, version: int, migration) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        migration(connection)
        connection.execute(f"PRAGMA user_version = {version}")
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def _execute_script(connection: sqlite3.Connection, script: str) -> None:
    """Execute a SQL script without sqlite3.executescript's implicit COMMIT."""
    statement = ""
    for line in script.splitlines():
        statement += line + "\n"
        if sqlite3.complete_statement(statement):
            sql = statement.strip()
            if sql:
                connection.execute(sql)
            statement = ""
    if statement.strip():
        raise sqlite3.OperationalError("Incomplete migration SQL statement")


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
    backups = sorted(
        backup_directory.glob("money_manager_pre_migration_v*.db"), reverse=True
    )
    for expired in backups[10:]:
        expired.unlink(missing_ok=True)
    return target


def _create_initial_schema(connection: sqlite3.Connection) -> None:
    _execute_script(connection,
        """
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
    _execute_script(connection,
        """
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


def _migrate_v3(connection: sqlite3.Connection) -> None:
    local_device_id = str(uuid4())
    _execute_script(connection,
        """
        DROP TRIGGER IF EXISTS validate_accounts_insert;
        DROP TRIGGER IF EXISTS validate_accounts_update;
        DROP TRIGGER IF EXISTS validate_categories_insert;
        DROP TRIGGER IF EXISTS validate_categories_update;
        DROP TRIGGER IF EXISTS validate_payment_methods_insert;
        DROP TRIGGER IF EXISTS validate_payment_methods_update;
        DROP TRIGGER IF EXISTS validate_transactions_insert;
        DROP TRIGGER IF EXISTS validate_transactions_update;

        ALTER TABLE transactions RENAME TO transactions_legacy_v2;
        ALTER TABLE payment_methods RENAME TO payment_methods_legacy_v2;
        ALTER TABLE categories RENAME TO categories_legacy_v2;
        ALTER TABLE accounts RENAME TO accounts_legacy_v2;
        ALTER TABLE settings RENAME TO settings_legacy_v2;

        CREATE TEMP TABLE account_id_map (old_id INTEGER PRIMARY KEY, new_id TEXT NOT NULL UNIQUE);
        CREATE TEMP TABLE payment_method_id_map (old_id INTEGER PRIMARY KEY, new_id TEXT NOT NULL UNIQUE);
        CREATE TEMP TABLE category_id_map (old_id INTEGER PRIMARY KEY, new_id TEXT NOT NULL UNIQUE);
        CREATE TEMP TABLE transaction_id_map (old_id INTEGER PRIMARY KEY, new_id TEXT NOT NULL UNIQUE);
        CREATE TEMP TABLE transfer_group_id_map (old_id TEXT PRIMARY KEY, new_id TEXT NOT NULL UNIQUE);
        """
    )

    uuid_sql = _sqlite_uuid_expression()
    for table, legacy_table in (
        ("account", "accounts_legacy_v2"),
        ("payment_method", "payment_methods_legacy_v2"),
        ("category", "categories_legacy_v2"),
        ("transaction", "transactions_legacy_v2"),
    ):
        connection.execute(
            f"INSERT INTO {table}_id_map (old_id, new_id) "
            f"SELECT id, {uuid_sql} FROM {legacy_table}"
        )
    connection.execute(
        "INSERT INTO transfer_group_id_map (old_id, new_id) "
        f"SELECT transfer_group_id, {uuid_sql} FROM transactions_legacy_v2 "
        "WHERE transfer_group_id IS NOT NULL GROUP BY transfer_group_id"
    )

    _execute_script(connection,
        f"""
        CREATE TABLE sync_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        ) WITHOUT ROWID;

        CREATE TABLE devices (
            id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            certificate_fingerprint TEXT,
            paired_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            last_seen_at TEXT,
            is_local INTEGER NOT NULL DEFAULT 0 CHECK (is_local IN (0, 1))
        );

        CREATE TABLE accounts (
            id TEXT PRIMARY KEY CHECK (length(id) = 36),
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN (
                'bank', 'current_account', 'savings_account', 'cash', 'wallet',
                'benefit', 'payment_method', 'investment', 'property',
                'credit_card', 'loan', 'mortgage', 'liability', 'other'
            )),
            parent_id TEXT REFERENCES accounts(id),
            opening_balance_cents INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            display_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            updated_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            deleted_at TEXT,
            revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1)
        );

        CREATE TABLE categories (
            id TEXT PRIMARY KEY CHECK (length(id) = 36),
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            updated_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            deleted_at TEXT,
            revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1)
        );

        CREATE TABLE payment_methods (
            id TEXT PRIMARY KEY CHECK (length(id) = 36),
            name TEXT NOT NULL,
            account_id TEXT NOT NULL REFERENCES accounts(id),
            type TEXT NOT NULL CHECK (type IN ('debit_card', 'credit_card', 'paypal', 'wallet', 'other')),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            updated_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            deleted_at TEXT,
            revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1)
        );

        CREATE TABLE transactions (
            id TEXT PRIMARY KEY CHECK (length(id) = 36),
            date TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
            type TEXT NOT NULL CHECK (type IN ('income', 'expense', 'transfer_out', 'transfer_in', 'adjustment')),
            account_id TEXT NOT NULL REFERENCES accounts(id),
            payment_method_id TEXT REFERENCES payment_methods(id),
            amount_cents INTEGER NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            category_id TEXT REFERENCES categories(id),
            transfer_group_id TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'cleared' CHECK (status IN ('draft', 'scheduled', 'cleared', 'reconciled')),
            created_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            updated_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            deleted_at TEXT,
            revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1)
        );

        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            updated_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            deleted_at TEXT,
            revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1)
        ) WITHOUT ROWID;

        CREATE TABLE attachments (
            id TEXT PRIMARY KEY CHECK (length(id) = 36),
            transaction_id TEXT REFERENCES transactions(id),
            original_name TEXT NOT NULL,
            relative_path TEXT NOT NULL UNIQUE,
            media_type TEXT,
            size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
            content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
            created_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            updated_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            deleted_at TEXT,
            revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1)
        );

        CREATE TABLE change_log (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            operation TEXT NOT NULL CHECK (operation IN ('insert', 'update', 'delete')),
            revision INTEGER NOT NULL CHECK (revision >= 1),
            device_id TEXT NOT NULL,
            changed_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            UNIQUE (device_id, entity_type, entity_id, revision)
        );

        CREATE TABLE tombstones (
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            deleted_at TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK (revision >= 1),
            device_id TEXT NOT NULL,
            PRIMARY KEY (entity_type, entity_id)
        ) WITHOUT ROWID;

        CREATE TABLE sync_cursors (
            device_id TEXT PRIMARY KEY REFERENCES devices(id),
            last_change_sequence INTEGER NOT NULL DEFAULT 0 CHECK (last_change_sequence >= 0),
            updated_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL})
        ) WITHOUT ROWID;

        CREATE TABLE conflicts (
            id TEXT PRIMARY KEY CHECK (length(id) = 36),
            device_id TEXT NOT NULL REFERENCES devices(id),
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            local_revision INTEGER NOT NULL,
            remote_revision INTEGER NOT NULL,
            local_payload TEXT NOT NULL,
            remote_payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'resolved', 'ignored')),
            created_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            resolved_at TEXT
        );

        INSERT INTO accounts (
            id, name, type, parent_id, opening_balance_cents, is_active,
            display_order, created_at, updated_at, revision
        )
        SELECT m.new_id, a.name, a.type, parent.new_id,
               CAST(ROUND(a.opening_balance * 100.0) AS INTEGER), a.is_active,
               a.display_order,
               CASE WHEN a.created_at LIKE '%Z' THEN a.created_at
                    ELSE replace(a.created_at, ' ', 'T') || 'Z' END,
               CASE WHEN a.updated_at LIKE '%Z' THEN a.updated_at
                    ELSE replace(a.updated_at, ' ', 'T') || 'Z' END,
               1
        FROM accounts_legacy_v2 a
        JOIN account_id_map m ON m.old_id = a.id
        LEFT JOIN account_id_map parent ON parent.old_id = a.parent_id;

        INSERT INTO categories (id, name, type, is_active, revision)
        SELECT m.new_id, c.name, c.type, c.is_active, 1
        FROM categories_legacy_v2 c
        JOIN category_id_map m ON m.old_id = c.id;

        INSERT INTO payment_methods (
            id, name, account_id, type, is_active, created_at, updated_at, revision
        )
        SELECT m.new_id, p.name, account.new_id, p.type, p.is_active,
               CASE WHEN p.created_at LIKE '%Z' THEN p.created_at
                    ELSE replace(p.created_at, ' ', 'T') || 'Z' END,
               CASE WHEN p.updated_at LIKE '%Z' THEN p.updated_at
                    ELSE replace(p.updated_at, ' ', 'T') || 'Z' END,
               1
        FROM payment_methods_legacy_v2 p
        JOIN payment_method_id_map m ON m.old_id = p.id
        JOIN account_id_map account ON account.old_id = p.account_id;

        INSERT INTO transactions (
            id, date, type, account_id, payment_method_id, amount_cents,
            description, category_id, transfer_group_id, notes, status,
            created_at, updated_at, revision
        )
        SELECT m.new_id, t.date, t.type, account.new_id, payment.new_id,
               CAST(ROUND(t.amount * 100.0) AS INTEGER), t.description,
               category.new_id, transfer_group.new_id, t.notes, 'cleared',
               CASE WHEN t.created_at LIKE '%Z' THEN t.created_at
                    ELSE replace(t.created_at, ' ', 'T') || 'Z' END,
               CASE WHEN t.updated_at LIKE '%Z' THEN t.updated_at
                    ELSE replace(t.updated_at, ' ', 'T') || 'Z' END,
               1
        FROM transactions_legacy_v2 t
        JOIN transaction_id_map m ON m.old_id = t.id
        JOIN account_id_map account ON account.old_id = t.account_id
        LEFT JOIN payment_method_id_map payment ON payment.old_id = t.payment_method_id
        LEFT JOIN category_id_map category ON category.old_id = t.category_id
        LEFT JOIN transfer_group_id_map transfer_group ON transfer_group.old_id = t.transfer_group_id;

        INSERT INTO settings (key, value, revision)
        SELECT key, value, 1 FROM settings_legacy_v2;

        DROP TABLE transactions_legacy_v2;
        DROP TABLE payment_methods_legacy_v2;
        DROP TABLE categories_legacy_v2;
        DROP TABLE accounts_legacy_v2;
        DROP TABLE settings_legacy_v2;

        DROP TABLE temp.account_id_map;
        DROP TABLE temp.payment_method_id_map;
        DROP TABLE temp.category_id_map;
        DROP TABLE temp.transaction_id_map;
        DROP TABLE temp.transfer_group_id_map;

        CREATE INDEX idx_accounts_parent ON accounts(parent_id) WHERE deleted_at IS NULL;
        CREATE INDEX idx_transactions_account_date
            ON transactions(account_id, date DESC, id DESC) WHERE deleted_at IS NULL;
        CREATE INDEX idx_transactions_date
            ON transactions(date DESC, id DESC) WHERE deleted_at IS NULL;
        CREATE INDEX idx_transactions_type_date
            ON transactions(type, date DESC, id DESC) WHERE deleted_at IS NULL;
        CREATE INDEX idx_transactions_category_date
            ON transactions(category_id, date DESC, id DESC) WHERE deleted_at IS NULL;
        CREATE INDEX idx_transactions_account_balance
            ON transactions(account_id, amount_cents) WHERE deleted_at IS NULL;
        CREATE INDEX idx_transactions_transfer_group
            ON transactions(transfer_group_id) WHERE deleted_at IS NULL;
        CREATE INDEX idx_change_log_device_sequence ON change_log(device_id, sequence);
        CREATE INDEX idx_attachments_hash ON attachments(content_hash) WHERE deleted_at IS NULL;
        CREATE INDEX idx_conflicts_status ON conflicts(status, created_at);
        """
    )

    connection.execute(
        "INSERT INTO sync_metadata (key, value) VALUES ('local_device_id', ?), ('active_device_id', ?)",
        (local_device_id, local_device_id),
    )
    connection.execute(
        "INSERT INTO devices (id, display_name, is_local) VALUES (?, 'This device', 1)",
        (local_device_id,),
    )
    _create_v3_triggers(connection)


def _sqlite_uuid_expression() -> str:
    return "(" + " || ".join(
        (
            "lower(hex(randomblob(4)))",
            "'-'",
            "lower(hex(randomblob(2)))",
            "'-'",
            "lower(hex(randomblob(2)))",
            "'-'",
            "lower(hex(randomblob(2)))",
            "'-'",
            "lower(hex(randomblob(6)))",
        )
    ) + ")"


def _create_v3_triggers(connection: sqlite3.Connection) -> None:
    validation_triggers = f"""
        CREATE TRIGGER validate_accounts_insert
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

        CREATE TRIGGER validate_accounts_update
        BEFORE UPDATE ON accounts
        WHEN NEW.revision != OLD.revision + 1
          OR NEW.is_active NOT IN (0, 1)
          OR NEW.type NOT IN (
              'bank', 'current_account', 'savings_account', 'cash', 'wallet',
              'benefit', 'payment_method', 'investment', 'property',
              'credit_card', 'loan', 'mortgage', 'liability', 'other'
          )
        BEGIN
            SELECT RAISE(ABORT, 'invalid account values or revision');
        END;

        CREATE TRIGGER validate_categories_insert
        BEFORE INSERT ON categories
        WHEN NEW.is_active NOT IN (0, 1)
          OR NEW.type NOT IN ('income', 'expense')
          OR (NEW.is_active = 1 AND NEW.deleted_at IS NULL AND EXISTS (
              SELECT 1 FROM categories
              WHERE type = NEW.type AND lower(name) = lower(NEW.name)
                AND is_active = 1 AND deleted_at IS NULL
          ))
        BEGIN
            SELECT RAISE(ABORT, 'invalid or duplicate category');
        END;

        CREATE TRIGGER validate_categories_update
        BEFORE UPDATE ON categories
        WHEN NEW.revision != OLD.revision + 1
          OR NEW.is_active NOT IN (0, 1)
          OR NEW.type NOT IN ('income', 'expense')
          OR (NEW.is_active = 1 AND NEW.deleted_at IS NULL AND EXISTS (
              SELECT 1 FROM categories
              WHERE type = NEW.type AND lower(name) = lower(NEW.name)
                AND is_active = 1 AND deleted_at IS NULL AND id != NEW.id
          ))
        BEGIN
            SELECT RAISE(ABORT, 'invalid category values or revision');
        END;

        CREATE TRIGGER validate_payment_methods_insert
        BEFORE INSERT ON payment_methods
        WHEN NEW.is_active NOT IN (0, 1)
          OR NEW.type NOT IN ('debit_card', 'credit_card', 'paypal', 'wallet', 'other')
          OR (NEW.is_active = 1 AND NEW.deleted_at IS NULL AND EXISTS (
              SELECT 1 FROM payment_methods
              WHERE account_id = NEW.account_id AND lower(name) = lower(NEW.name)
                AND is_active = 1 AND deleted_at IS NULL
          ))
        BEGIN
            SELECT RAISE(ABORT, 'invalid or duplicate payment method');
        END;

        CREATE TRIGGER validate_payment_methods_update
        BEFORE UPDATE ON payment_methods
        WHEN NEW.revision != OLD.revision + 1
          OR NEW.is_active NOT IN (0, 1)
          OR NEW.type NOT IN ('debit_card', 'credit_card', 'paypal', 'wallet', 'other')
          OR (NEW.is_active = 1 AND NEW.deleted_at IS NULL AND EXISTS (
              SELECT 1 FROM payment_methods
              WHERE account_id = NEW.account_id AND lower(name) = lower(NEW.name)
                AND is_active = 1 AND deleted_at IS NULL AND id != NEW.id
          ))
        BEGIN
            SELECT RAISE(ABORT, 'invalid payment method values or revision');
        END;

        CREATE TRIGGER validate_transactions_insert
        BEFORE INSERT ON transactions
        WHEN NEW.type NOT IN ('income', 'expense', 'transfer_out', 'transfer_in', 'adjustment')
          OR NEW.status NOT IN ('draft', 'scheduled', 'cleared', 'reconciled')
          OR NEW.date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
        BEGIN
            SELECT RAISE(ABORT, 'invalid transaction values');
        END;

        CREATE TRIGGER validate_transactions_update
        BEFORE UPDATE ON transactions
        WHEN NEW.revision != OLD.revision + 1
          OR NEW.type NOT IN ('income', 'expense', 'transfer_out', 'transfer_in', 'adjustment')
          OR NEW.status NOT IN ('draft', 'scheduled', 'cleared', 'reconciled')
          OR NEW.date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
        BEGIN
            SELECT RAISE(ABORT, 'invalid transaction values or revision');
        END;

        CREATE TRIGGER validate_attachments_update
        BEFORE UPDATE ON attachments
        WHEN NEW.revision != OLD.revision + 1
        BEGIN
            SELECT RAISE(ABORT, 'invalid attachment revision');
        END;

        CREATE TRIGGER validate_settings_update
        BEFORE UPDATE ON settings
        WHEN NEW.revision != OLD.revision + 1
        BEGIN
            SELECT RAISE(ABORT, 'invalid settings revision');
        END;
    """
    _execute_script(connection, validation_triggers)

    for table, entity_id in (
        ("accounts", "NEW.id"),
        ("categories", "NEW.id"),
        ("payment_methods", "NEW.id"),
        ("transactions", "NEW.id"),
        ("attachments", "NEW.id"),
        ("settings", "NEW.key"),
    ):
        entity_type = table
        _execute_script(connection,
            f"""
            CREATE TRIGGER capture_{table}_insert
            AFTER INSERT ON {table}
            BEGIN
                INSERT INTO change_log (
                    entity_type, entity_id, operation, revision, device_id
                ) VALUES (
                    '{entity_type}', {entity_id}, 'insert', NEW.revision,
                    (SELECT value FROM sync_metadata WHERE key = 'active_device_id')
                );
            END;

            CREATE TRIGGER capture_{table}_update
            AFTER UPDATE ON {table}
            BEGIN
                INSERT INTO change_log (
                    entity_type, entity_id, operation, revision, device_id
                ) VALUES (
                    '{entity_type}', {entity_id},
                    CASE WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL
                         THEN 'delete' ELSE 'update' END,
                    NEW.revision,
                    (SELECT value FROM sync_metadata WHERE key = 'active_device_id')
                );
            END;

            CREATE TRIGGER prevent_{table}_hard_delete
            BEFORE DELETE ON {table}
            BEGIN
                SELECT RAISE(ABORT, 'hard delete is not allowed; use a tombstone');
            END;
            """
        )

    for table, entity_id in (
        ("accounts", "NEW.id"),
        ("categories", "NEW.id"),
        ("payment_methods", "NEW.id"),
        ("transactions", "NEW.id"),
        ("attachments", "NEW.id"),
        ("settings", "NEW.key"),
    ):
        _execute_script(connection,
            f"""
            CREATE TRIGGER tombstone_{table}_delete
            AFTER UPDATE OF deleted_at ON {table}
            WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL
            BEGIN
                INSERT INTO tombstones (
                    entity_type, entity_id, deleted_at, revision, device_id
                ) VALUES (
                    '{table}', {entity_id}, NEW.deleted_at, NEW.revision,
                    (SELECT value FROM sync_metadata WHERE key = 'active_device_id')
                )
                ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                    deleted_at = excluded.deleted_at,
                    revision = excluded.revision,
                    device_id = excluded.device_id;
            END;
            """
        )


def _migrate_v4(connection: sqlite3.Connection) -> None:
    _execute_script(
        connection,
        f"""
        CREATE TABLE recurring_rules (
            id TEXT PRIMARY KEY CHECK (length(id) = 36),
            name TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('subscription', 'bill', 'other')),
            amount_mode TEXT NOT NULL CHECK (amount_mode IN ('fixed', 'variable')),
            amount_cents INTEGER,
            account_id TEXT NOT NULL REFERENCES accounts(id),
            category_id TEXT REFERENCES categories(id),
            payment_method_id TEXT REFERENCES payment_methods(id),
            frequency TEXT NOT NULL CHECK (frequency IN ('weekly', 'monthly', 'quarterly', 'yearly')),
            start_date TEXT NOT NULL CHECK (start_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
            next_due_date TEXT NOT NULL CHECK (next_due_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
            end_date TEXT CHECK (end_date IS NULL OR end_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
            reminder_days INTEGER NOT NULL DEFAULT 3 CHECK (reminder_days BETWEEN 0 AND 90),
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed')),
            last_recorded_date TEXT CHECK (
                last_recorded_date IS NULL
                OR last_recorded_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            ),
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            updated_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            deleted_at TEXT,
            revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
            CHECK (
                (amount_mode = 'fixed' AND amount_cents IS NOT NULL AND amount_cents > 0)
                OR (amount_mode = 'variable' AND (amount_cents IS NULL OR amount_cents > 0))
            ),
            CHECK (next_due_date >= start_date),
            CHECK (end_date IS NULL OR end_date >= start_date)
        );

        ALTER TABLE transactions
            ADD COLUMN recurring_rule_id TEXT REFERENCES recurring_rules(id);

        CREATE INDEX idx_recurring_rules_next_due
            ON recurring_rules(status, next_due_date) WHERE deleted_at IS NULL;
        CREATE INDEX idx_recurring_rules_account
            ON recurring_rules(account_id) WHERE deleted_at IS NULL;
        CREATE INDEX idx_transactions_recurring_rule
            ON transactions(recurring_rule_id) WHERE deleted_at IS NULL;

        CREATE TRIGGER validate_recurring_rules_update
        BEFORE UPDATE ON recurring_rules
        WHEN NEW.revision != OLD.revision + 1
        BEGIN
            SELECT RAISE(ABORT, 'invalid recurring rule revision');
        END;

        CREATE TRIGGER capture_recurring_rules_insert
        AFTER INSERT ON recurring_rules
        BEGIN
            INSERT INTO change_log (
                entity_type, entity_id, operation, revision, device_id
            ) VALUES (
                'recurring_rules', NEW.id, 'insert', NEW.revision,
                (SELECT value FROM sync_metadata WHERE key = 'active_device_id')
            );
        END;

        CREATE TRIGGER capture_recurring_rules_update
        AFTER UPDATE ON recurring_rules
        BEGIN
            INSERT INTO change_log (
                entity_type, entity_id, operation, revision, device_id
            ) VALUES (
                'recurring_rules', NEW.id,
                CASE WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL
                     THEN 'delete' ELSE 'update' END,
                NEW.revision,
                (SELECT value FROM sync_metadata WHERE key = 'active_device_id')
            );
        END;

        CREATE TRIGGER prevent_recurring_rules_hard_delete
        BEFORE DELETE ON recurring_rules
        BEGIN
            SELECT RAISE(ABORT, 'hard delete is not allowed; use a tombstone');
        END;

        CREATE TRIGGER tombstone_recurring_rules_delete
        AFTER UPDATE OF deleted_at ON recurring_rules
        WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL
        BEGIN
            INSERT INTO tombstones (
                entity_type, entity_id, deleted_at, revision, device_id
            ) VALUES (
                'recurring_rules', NEW.id, NEW.deleted_at, NEW.revision,
                (SELECT value FROM sync_metadata WHERE key = 'active_device_id')
            )
            ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                deleted_at = excluded.deleted_at,
                revision = excluded.revision,
                device_id = excluded.device_id;
        END;
        """,
    )


def _migrate_v5(connection: sqlite3.Connection) -> None:
    _execute_script(
        connection,
        f"""
        CREATE TABLE investments (
            id TEXT PRIMARY KEY CHECK (length(id) = 36),
            name TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (
                kind IN ('fund', 'etf', 'stock', 'bond', 'crypto', 'other')
            ),
            symbol TEXT,
            account_id TEXT NOT NULL UNIQUE REFERENCES accounts(id),
            notes TEXT,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            updated_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            deleted_at TEXT,
            revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1)
        );

        ALTER TABLE transactions
            ADD COLUMN investment_id TEXT REFERENCES investments(id);

        CREATE INDEX idx_investments_account
            ON investments(account_id) WHERE deleted_at IS NULL;
        CREATE INDEX idx_transactions_investment
            ON transactions(investment_id, date) WHERE deleted_at IS NULL;

        CREATE TRIGGER validate_investments_update
        BEFORE UPDATE ON investments
        WHEN NEW.revision != OLD.revision + 1
        BEGIN
            SELECT RAISE(ABORT, 'invalid investment revision');
        END;

        CREATE TRIGGER capture_investments_insert
        AFTER INSERT ON investments
        BEGIN
            INSERT INTO change_log (
                entity_type, entity_id, operation, revision, device_id
            ) VALUES (
                'investments', NEW.id, 'insert', NEW.revision,
                (SELECT value FROM sync_metadata WHERE key = 'active_device_id')
            );
        END;

        CREATE TRIGGER capture_investments_update
        AFTER UPDATE ON investments
        BEGIN
            INSERT INTO change_log (
                entity_type, entity_id, operation, revision, device_id
            ) VALUES (
                'investments', NEW.id,
                CASE WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL
                     THEN 'delete' ELSE 'update' END,
                NEW.revision,
                (SELECT value FROM sync_metadata WHERE key = 'active_device_id')
            );
        END;

        CREATE TRIGGER prevent_investments_hard_delete
        BEFORE DELETE ON investments
        BEGIN
            SELECT RAISE(ABORT, 'hard delete is not allowed; use a tombstone');
        END;

        CREATE TRIGGER tombstone_investments_delete
        AFTER UPDATE OF deleted_at ON investments
        WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL
        BEGIN
            INSERT INTO tombstones (
                entity_type, entity_id, deleted_at, revision, device_id
            ) VALUES (
                'investments', NEW.id, NEW.deleted_at, NEW.revision,
                (SELECT value FROM sync_metadata WHERE key = 'active_device_id')
            )
            ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                deleted_at = excluded.deleted_at,
                revision = excluded.revision,
                device_id = excluded.device_id;
        END;
        """,
    )


def _migrate_v6(connection: sqlite3.Connection) -> None:
    _execute_script(
        connection,
        f"""
        CREATE TABLE loans (
            id TEXT PRIMARY KEY CHECK (length(id) = 36),
            direction TEXT NOT NULL CHECK (direction IN ('borrowed', 'lent')),
            name TEXT NOT NULL,
            counterparty TEXT NOT NULL,
            principal_cents INTEGER NOT NULL CHECK (principal_cents > 0),
            account_id TEXT NOT NULL REFERENCES accounts(id),
            start_date TEXT NOT NULL CHECK (
                start_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            ),
            due_date TEXT CHECK (
                due_date IS NULL
                OR due_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            ),
            interest_rate_bps INTEGER NOT NULL DEFAULT 0 CHECK (
                interest_rate_bps BETWEEN 0 AND 10000
            ),
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'settled')),
            created_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            updated_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            deleted_at TEXT,
            revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
            CHECK (due_date IS NULL OR due_date >= start_date)
        );

        ALTER TABLE transactions
            ADD COLUMN loan_id TEXT REFERENCES loans(id);

        CREATE TABLE loan_payments (
            id TEXT PRIMARY KEY CHECK (length(id) = 36),
            loan_id TEXT NOT NULL REFERENCES loans(id),
            account_id TEXT NOT NULL REFERENCES accounts(id),
            transaction_id TEXT NOT NULL UNIQUE REFERENCES transactions(id),
            amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
            date TEXT NOT NULL CHECK (
                date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            ),
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            updated_at TEXT NOT NULL DEFAULT ({UTC_NOW_SQL}),
            deleted_at TEXT,
            revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1)
        );

        CREATE INDEX idx_loans_direction_status
            ON loans(direction, status) WHERE deleted_at IS NULL;
        CREATE INDEX idx_loans_account
            ON loans(account_id) WHERE deleted_at IS NULL;
        CREATE INDEX idx_loan_payments_loan
            ON loan_payments(loan_id, date DESC) WHERE deleted_at IS NULL;
        CREATE INDEX idx_transactions_loan
            ON transactions(loan_id, date DESC) WHERE deleted_at IS NULL;

        CREATE TRIGGER validate_loans_update
        BEFORE UPDATE ON loans
        WHEN NEW.revision != OLD.revision + 1
        BEGIN
            SELECT RAISE(ABORT, 'invalid loan revision');
        END;

        CREATE TRIGGER validate_loan_payments_update
        BEFORE UPDATE ON loan_payments
        WHEN NEW.revision != OLD.revision + 1
        BEGIN
            SELECT RAISE(ABORT, 'invalid loan payment revision');
        END;
        """,
    )

    for table in ("loans", "loan_payments"):
        _execute_script(
            connection,
            f"""
            CREATE TRIGGER capture_{table}_insert
            AFTER INSERT ON {table}
            BEGIN
                INSERT INTO change_log (
                    entity_type, entity_id, operation, revision, device_id
                ) VALUES (
                    '{table}', NEW.id, 'insert', NEW.revision,
                    (SELECT value FROM sync_metadata WHERE key = 'active_device_id')
                );
            END;

            CREATE TRIGGER capture_{table}_update
            AFTER UPDATE ON {table}
            BEGIN
                INSERT INTO change_log (
                    entity_type, entity_id, operation, revision, device_id
                ) VALUES (
                    '{table}', NEW.id,
                    CASE WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL
                         THEN 'delete' ELSE 'update' END,
                    NEW.revision,
                    (SELECT value FROM sync_metadata WHERE key = 'active_device_id')
                );
            END;

            CREATE TRIGGER prevent_{table}_hard_delete
            BEFORE DELETE ON {table}
            BEGIN
                SELECT RAISE(ABORT, 'hard delete is not allowed; use a tombstone');
            END;

            CREATE TRIGGER tombstone_{table}_delete
            AFTER UPDATE OF deleted_at ON {table}
            WHEN NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL
            BEGIN
                INSERT INTO tombstones (
                    entity_type, entity_id, deleted_at, revision, device_id
                ) VALUES (
                    '{table}', NEW.id, NEW.deleted_at, NEW.revision,
                    (SELECT value FROM sync_metadata WHERE key = 'active_device_id')
                )
                ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                    deleted_at = excluded.deleted_at,
                    revision = excluded.revision,
                    device_id = excluded.device_id;
            END;
            """,
        )


def _migrate_v7(connection: sqlite3.Connection) -> None:
    _execute_script(
        connection,
        """
        ALTER TABLE recurring_rules
            ADD COLUMN transaction_type TEXT NOT NULL DEFAULT 'expense'
            CHECK (transaction_type IN ('income', 'expense'));

        DROP TRIGGER validate_recurring_rules_update;

        CREATE TRIGGER validate_recurring_rules_update
        BEFORE UPDATE ON recurring_rules
        WHEN NEW.revision != OLD.revision + 1
          OR NEW.transaction_type NOT IN ('income', 'expense')
        BEGIN
            SELECT RAISE(ABORT, 'invalid recurring rule values or revision');
        END;
        """,
    )
