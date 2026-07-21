from __future__ import annotations

import os
from decimal import Decimal

import pytest

from app.core.database import connect
from app.core.database_security import KEY_FILE_HEADER, SQLITE_HEADER
from app.core.paths import database_key_path, database_path
from app.services.account_service import AccountService
from app.services.backup_service import BackupService
from app.services.transaction_service import TransactionService


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Desktop DPAPI is Windows-only")


def test_desktop_database_and_automatic_backups_are_encrypted_for_windows_user(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MONEY_MANAGER_DAD_ENCRYPT_DATABASE", "1")
    db = connect()
    try:
        account = AccountService(db).create_account(
            "Current", "current_account", opening_balance="100"
        )
        backup = BackupService(db).create_backup()
    finally:
        db.close()

    assert not database_path().read_bytes().startswith(SQLITE_HEADER)
    assert not backup.read_bytes().startswith(SQLITE_HEADER)
    assert database_key_path().read_bytes().startswith(KEY_FILE_HEADER)

    reopened = connect()
    try:
        assert AccountService(reopened).account_balance(account.id) == Decimal("100.00")
        inspection = BackupService(reopened).inspect_backup(backup)
        assert inspection.encrypted is True
    finally:
        reopened.close()


def test_plain_existing_database_migrates_without_losing_data(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MONEY_MANAGER_DAD_ENCRYPT_DATABASE", "0")
    plain = connect()
    try:
        account = AccountService(plain).create_account(
            "Current", "current_account", opening_balance="100"
        )
        TransactionService(plain).add_expense(
            account.id, "25", "2026-07-21", "Before encryption"
        )
    finally:
        plain.close()
    assert database_path().read_bytes().startswith(SQLITE_HEADER)

    monkeypatch.setenv("MONEY_MANAGER_DAD_ENCRYPT_DATABASE", "1")
    encrypted = connect()
    try:
        assert AccountService(encrypted).account_balance(account.id) == Decimal("75.00")
        assert [
            item.description
            for item in TransactionService(encrypted).list_transactions()
        ] == ["Before encryption"]
    finally:
        encrypted.close()
    assert not database_path().read_bytes().startswith(SQLITE_HEADER)


def test_portable_password_backup_restores_into_encrypted_database(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MONEY_MANAGER_DAD_ENCRYPT_DATABASE", "1")
    db = connect()
    try:
        accounts = AccountService(db)
        transactions = TransactionService(db)
        account = accounts.create_account(
            "Current", "current_account", opening_balance="100"
        )
        service = BackupService(db)
        portable = service.create_encrypted_backup("correct horse battery staple")
        transactions.add_expense(account.id, "25", "2026-07-21", "After backup")

        rollback = service.restore_backup(
            portable,
            password="correct horse battery staple",
        )

        assert rollback.exists()
        assert accounts.account_balance(account.id) == Decimal("100.00")
        assert transactions.list_transactions() == []
        assert not database_path().read_bytes().startswith(SQLITE_HEADER)
    finally:
        db.close()


def test_interrupted_encryption_swap_recovers_the_verified_plain_copy(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MONEY_MANAGER_DAD_ENCRYPT_DATABASE", "0")
    plain = connect()
    try:
        account = AccountService(plain).create_account(
            "Current", "current_account", opening_balance="80"
        )
    finally:
        plain.close()
    original_plaintext = database_path().read_bytes()

    monkeypatch.setenv("MONEY_MANAGER_DAD_ENCRYPT_DATABASE", "1")
    encrypted = connect()
    encrypted.close()
    rollback = database_path().with_name(
        f".{database_path().name}.plaintext-migration"
    )
    rollback.write_bytes(original_plaintext)
    database_path().write_bytes(b"incomplete encrypted database")

    recovered = connect()
    try:
        assert AccountService(recovered).account_balance(account.id) == Decimal("80.00")
    finally:
        recovered.close()
    assert not rollback.exists()
    assert not database_path().read_bytes().startswith(SQLITE_HEADER)
