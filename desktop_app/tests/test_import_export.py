from __future__ import annotations

from pathlib import Path

from app.core.database import connect
from app.services.account_service import AccountService
from app.services.export_service import ExportService
from app.services.import_service import ImportService
from app.services.transaction_service import TransactionService


def test_export_can_be_previewed_imported_and_safely_repeated(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path / "app-data"))
    source_db = connect(tmp_path / "source.db")
    target_db = connect(tmp_path / "target.db")
    try:
        source_accounts = AccountService(source_db)
        current = source_accounts.create_account("Current", "current_account")
        savings = source_accounts.create_account("Savings", "savings_account")
        source_transactions = TransactionService(source_db)
        source_transactions.add_income(current.id, "2500", "2026-07-01", "Salary")
        source_transactions.add_expense(
            current.id,
            "42.50",
            "2026-07-02",
            "Groceries",
            notes="Weekly shop",
        )
        source_transactions.add_transfer(
            current.id,
            savings.id,
            "300",
            "2026-07-03",
            "Monthly saving",
        )
        exported = ExportService(source_db).export_transactions_csv(
            tmp_path / "transactions.csv"
        )

        target_accounts = AccountService(target_db)
        target_accounts.create_account("Current", "current_account")
        target_accounts.create_account("Savings", "savings_account")
        imports = ImportService(target_db)
        preview = imports.preview_transactions_csv(exported)

        assert preview.errors == ()
        assert preview.import_count == 3
        assert preview.duplicate_count == 0
        assert imports.import_transactions(preview) == 3
        assert len(TransactionService(target_db).list_transactions()) == 4

        repeated = imports.preview_transactions_csv(exported)
        assert repeated.import_count == 0
        assert repeated.duplicate_count == 3
        assert imports.import_transactions(repeated) == 0
        assert len(TransactionService(target_db).list_transactions()) == 4
    finally:
        source_db.close()
        target_db.close()


def test_import_reports_all_bad_rows_without_writing(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path / "app-data"))
    db = connect(tmp_path / "money.db")
    try:
        AccountService(db).create_account("Current", "current_account")
        source = tmp_path / "bad.csv"
        source.write_text(
            "date,type,account,amount\n"
            "not-a-date,expense,Current,12\n"
            "2026-07-02,income,Missing,20\n",
            encoding="utf-8",
        )

        preview = ImportService(db).preview_transactions_csv(source)

        assert len(preview.errors) == 2
        assert "Row 2" in preview.errors[0]
        assert "Row 3" in preview.errors[1]
        assert TransactionService(db).list_transactions() == []
    finally:
        db.close()


def test_export_neutralizes_spreadsheet_formulas_and_import_restores_text(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path / "app-data"))
    source_db = connect(tmp_path / "source.db")
    target_db = connect(tmp_path / "target.db")
    try:
        account = AccountService(source_db).create_account("=Wallet", "wallet")
        TransactionService(source_db).add_expense(
            account.id,
            "10",
            "2026-07-04",
            "=HYPERLINK(\"bad\")",
        )
        exported = ExportService(source_db).export_transactions_csv(
            tmp_path / "safe.csv"
        )
        raw = exported.read_text(encoding="utf-8")
        assert "'=Wallet" in raw
        assert "'=HYPERLINK" in raw

        target = AccountService(target_db).create_account("=Wallet", "wallet")
        imports = ImportService(target_db)
        preview = imports.preview_transactions_csv(exported)
        assert preview.errors == ()
        imports.import_transactions(preview)
        imported = TransactionService(target_db).list_transactions()[0]
        assert imported.account_id == target.id
        assert imported.description == '=HYPERLINK("bad")'
    finally:
        source_db.close()
        target_db.close()
