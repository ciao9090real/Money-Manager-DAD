from __future__ import annotations

import sqlite3
from decimal import Decimal

import pytest

from app.core.database import connect, unit_of_work
from app.core.migrations import _run_migration
from app.repositories.settings_repository import SettingsRepository
from app.repositories.sync_repository import SyncRepository
from app.services.account_service import AccountService
from app.services.category_service import CategoryService
from app.services.transaction_service import TransactionService


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


def test_money_is_stored_as_exact_integer_cents(db):
    accounts = AccountService(db)
    transactions = TransactionService(db)
    account = accounts.create_account("Exact", "current_account", opening_balance="0.10")
    transactions.add_income(account.id, "0.20", "2026-07-14")

    row = db.execute(
        """
        SELECT a.opening_balance_cents, t.amount_cents
        FROM accounts a JOIN transactions t ON t.account_id = a.id
        WHERE a.id = ?
        """,
        (account.id,),
    ).fetchone()
    assert (row["opening_balance_cents"], row["amount_cents"]) == (10, 20)
    assert accounts.account_balance(account.id) == Decimal("0.30")


def test_uuid_revisions_and_change_log_are_generated(db):
    service = AccountService(db)
    account = service.create_account("Current", "current_account")
    assert account.id is not None and len(account.id) == 36
    assert account.revision == 1

    updated = service.update_account(
        account.id, "Main current", "current_account", None, "5"
    )
    assert updated.id == account.id
    assert updated.revision == 2
    assert updated.updated_at is not None and updated.updated_at.endswith("Z")

    changes = db.execute(
        """
        SELECT operation, revision, device_id
        FROM change_log WHERE entity_type = 'accounts' AND entity_id = ?
        ORDER BY sequence
        """,
        (account.id,),
    ).fetchall()
    assert [(row["operation"], row["revision"]) for row in changes] == [
        ("insert", 1),
        ("update", 2),
    ]
    assert {row["device_id"] for row in changes} == {SyncRepository(db).local_device_id()}


def test_transaction_delete_is_a_tombstone_and_no_longer_affects_balance(db):
    accounts = AccountService(db)
    transactions = TransactionService(db)
    account = accounts.create_account("Current", "current_account", opening_balance="10")
    transaction = transactions.add_expense(account.id, "3", "2026-07-14")
    assert accounts.account_balance(account.id) == Decimal("7.00")

    transactions.delete_transaction(transaction.id)

    assert transactions.list_transactions() == []
    assert accounts.account_balance(account.id) == Decimal("10.00")
    stored = db.execute(
        "SELECT deleted_at, revision FROM transactions WHERE id = ?", (transaction.id,)
    ).fetchone()
    assert stored["deleted_at"].endswith("Z")
    assert stored["revision"] == 2
    tombstone = db.execute(
        "SELECT * FROM tombstones WHERE entity_type = 'transactions' AND entity_id = ?",
        (transaction.id,),
    ).fetchone()
    assert tombstone is not None and tombstone["revision"] == 2
    assert db.execute(
        """
        SELECT operation FROM change_log
        WHERE entity_type = 'transactions' AND entity_id = ? AND revision = 2
        """,
        (transaction.id,),
    ).fetchone()[0] == "delete"
    with pytest.raises(sqlite3.IntegrityError, match="hard delete"):
        db.execute("DELETE FROM transactions WHERE id = ?", (transaction.id,))


def test_sync_device_cursor_conflict_and_change_origin(db):
    sync = SyncRepository(db)
    remote_id = sync.register_device("Phone", "sha256:test-fingerprint")
    sync.advance_cursor(remote_id, 4)
    assert sync.cursor_for(remote_id) == 4
    with pytest.raises(ValueError, match="backwards"):
        sync.advance_cursor(remote_id, 3)

    sync.set_active_device(remote_id)
    category = CategoryService(db).create_category("Groceries", "expense")
    sync.set_active_device(sync.local_device_id())
    origin = db.execute(
        """
        SELECT device_id FROM change_log
        WHERE entity_type = 'categories' AND entity_id = ?
        """,
        (category.id,),
    ).fetchone()[0]
    assert origin == remote_id

    conflict_id = sync.record_conflict(
        remote_id,
        "categories",
        category.id,
        2,
        2,
        {"name": "Food"},
        {"name": "Groceries"},
    )
    assert [row["id"] for row in sync.list_conflicts()] == [conflict_id]
    sync.resolve_conflict(conflict_id)
    assert sync.list_conflicts() == []


def test_settings_are_revisioned_and_audited(db):
    settings = SettingsRepository(db)
    with unit_of_work(db):
        settings.set("currency", "EUR")
    with unit_of_work(db):
        settings.set("currency", "USD")

    row = db.execute(
        "SELECT value, revision, updated_at FROM settings WHERE key = 'currency'"
    ).fetchone()
    assert (row["value"], row["revision"]) == ("USD", 2)
    assert row["updated_at"].endswith("Z")
    assert db.execute(
        "SELECT COUNT(*) FROM change_log WHERE entity_type = 'settings' AND entity_id = 'currency'"
    ).fetchone()[0] == 2


def test_migration_runner_rolls_back_ddl_on_failure(tmp_path):
    db = sqlite3.connect(tmp_path / "atomic.db")
    db.execute("CREATE TABLE original (value TEXT)")
    db.commit()

    def broken_migration(connection):
        connection.execute("ALTER TABLE original RENAME TO changed")
        raise RuntimeError("stop")

    with pytest.raises(RuntimeError, match="stop"):
        _run_migration(db, 99, broken_migration)

    assert db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'original'"
    ).fetchone()[0] == "original"
    assert db.execute("PRAGMA user_version").fetchone()[0] == 0
    db.close()
