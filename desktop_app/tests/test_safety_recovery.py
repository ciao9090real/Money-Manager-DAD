from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.database import connect
from app.core.paths import backup_dir
from app.services.account_service import AccountService
from app.services.backup_service import BackupService
from app.services.recurring_service import RecurringService
from app.services.trash_service import TrashService
from app.services.transaction_service import TransactionService


@pytest.fixture()
def services(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        yield (
            db,
            AccountService(db),
            TransactionService(db),
            RecurringService(db),
            TrashService(db),
        )
    finally:
        db.close()


def test_restore_backup_replaces_data_and_keeps_rollback_copy(services):
    db, accounts, transactions, _recurring, _trash = services
    current = accounts.create_account("Current", "current_account", opening_balance="100")
    backup = BackupService(db).create_backup()
    transactions.add_expense(current.id, "25", "2026-07-15", "After backup")
    assert accounts.account_balance(current.id) == Decimal("75.00")

    rollback = BackupService(db).restore_backup(backup)

    assert rollback.exists()
    assert rollback.name.startswith("money_manager_before_restore_")
    assert AccountService(db).account_balance(current.id) == Decimal("100.00")
    assert TransactionService(db).list_transactions() == []


def test_encrypted_backup_restores_with_correct_password(services):
    db, accounts, transactions, _recurring, _trash = services
    current = accounts.create_account("Current", "current_account", opening_balance="100")
    service = BackupService(db)
    backup = service.create_encrypted_backup("correct horse battery staple")

    assert backup.suffix == BackupService.ENCRYPTED_SUFFIX
    assert BackupService.is_encrypted_backup(backup)
    assert not backup.read_bytes().startswith(b"SQLite format 3")

    transactions.add_expense(current.id, "25", "2026-07-15", "After backup")
    rollback = service.restore_backup(
        backup,
        password="correct horse battery staple",
    )

    assert rollback.exists()
    assert AccountService(db).account_balance(current.id) == Decimal("100.00")
    assert TransactionService(db).list_transactions() == []


def test_encrypted_backup_rejects_wrong_password_without_changing_data(services):
    db, accounts, transactions, _recurring, _trash = services
    current = accounts.create_account("Current", "current_account", opening_balance="100")
    service = BackupService(db)
    backup = service.create_encrypted_backup("correct horse battery staple")
    transactions.add_expense(current.id, "25", "2026-07-15", "Keep me")

    with pytest.raises(ValueError, match="Incorrect password"):
        service.restore_backup(backup, password="definitely the wrong password")

    assert accounts.account_balance(current.id) == Decimal("75.00")
    assert [item.description for item in transactions.list_transactions()] == [
        "Keep me"
    ]


def test_encrypted_backup_rejects_tampering_without_changing_data(services):
    db, accounts, _transactions, _recurring, _trash = services
    current = accounts.create_account("Current", "current_account", opening_balance="100")
    service = BackupService(db)
    backup = service.create_encrypted_backup("correct horse battery staple")
    payload = bytearray(backup.read_bytes())
    payload[-1] ^= 1
    backup.write_bytes(payload)

    with pytest.raises(ValueError, match="damaged encrypted backup"):
        service.restore_backup(
            backup,
            password="correct horse battery staple",
        )

    assert accounts.account_balance(current.id) == Decimal("100.00")


def test_encrypted_backup_requires_a_substantial_password(services):
    db, _accounts, _transactions, _recurring, _trash = services

    with pytest.raises(ValueError, match="at least 10 characters"):
        BackupService(db).create_encrypted_backup("short")


def test_invalid_restore_is_rejected_without_changing_current_data(services, tmp_path):
    db, accounts, _transactions, _recurring, _trash = services
    current = accounts.create_account("Current", "current_account", opening_balance="100")
    invalid = tmp_path / "not-a-database.db"
    invalid.write_text("not sqlite", encoding="utf-8")

    with pytest.raises(Exception):
        BackupService(db).restore_backup(invalid)

    assert accounts.account_balance(current.id) == Decimal("100.00")


def test_daily_backup_is_once_per_day_and_rotates_old_files(services):
    db, _accounts, _transactions, _recurring, _trash = services
    directory = backup_dir()
    for day in ("20260101", "20260102", "20260103"):
        (directory / f"money_manager_daily_{day}.db").touch()

    service = BackupService(db)
    created = service.ensure_daily_backup(retention=2)

    assert created is not None and created.exists()
    assert service.ensure_daily_backup(retention=2) is None
    assert len(list(directory.glob("money_manager_daily_*.db"))) == 2


def test_deleted_transaction_can_be_restored_with_balance(services):
    db, accounts, transactions, _recurring, trash = services
    current = accounts.create_account("Current", "current_account", opening_balance="100")
    expense = transactions.add_expense(current.id, "30", "2026-07-15", "Groceries")
    transactions.delete_transaction(expense.id)

    item = trash.list_items()[0]
    assert item.entity_type == "transactions"
    assert accounts.account_balance(current.id) == Decimal("100.00")

    trash.restore(item.entity_type, item.entity_id)

    assert accounts.account_balance(current.id) == Decimal("70.00")
    assert len(transactions.list_transactions()) == 1
    assert db.execute(
        "SELECT 1 FROM tombstones WHERE entity_type = 'transactions' AND entity_id = ?",
        (expense.id,),
    ).fetchone() is None


def test_deleted_transfer_restores_both_ledger_entries(services):
    _db, accounts, transactions, _recurring, trash = services
    source = accounts.create_account("Current", "current_account", opening_balance="100")
    target = accounts.create_account("Savings", "savings_account")
    outgoing, _incoming = transactions.add_transfer(
        source.id, target.id, "40", "2026-07-15", "Move savings"
    )
    transactions.delete_transaction(outgoing.id)

    items = trash.list_items()
    assert len(items) == 1
    trash.restore(items[0].entity_type, items[0].entity_id)

    assert len(transactions.list_transactions()) == 2
    assert accounts.account_balance(source.id) == Decimal("60.00")
    assert accounts.account_balance(target.id) == Decimal("40.00")


def test_deleted_recurring_payment_can_be_restored(services):
    _db, accounts, _transactions, recurring, trash = services
    current = accounts.create_account("Current", "current_account")
    rule = recurring.create_rule(
        "Internet",
        "bill",
        "fixed",
        current.id,
        "monthly",
        "2026-08-01",
        amount="35",
    )
    recurring.delete_rule(rule.id)

    item = trash.list_items()[0]
    assert item.entity_type == "recurring_rules"
    trash.restore(item.entity_type, item.entity_id)

    restored = recurring.get_rule(rule.id)
    assert restored is not None
    assert restored.name == "Internet"
