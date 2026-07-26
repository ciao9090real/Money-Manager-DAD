from __future__ import annotations

import zipfile
from pathlib import Path

from app.core.database import connect
from app.services.account_service import AccountService
from app.services.export_service import ExportService
from app.services.import_service import ImportService, StatementMapping
from app.services.payment_method_service import PaymentMethodService
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


def test_bank_statement_maps_card_period_and_european_csv_columns(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path / "app-data"))
    db = connect(tmp_path / "money.db")
    try:
        account = AccountService(db).create_account("Everyday", "current_account")
        card = PaymentMethodService(db).create_payment_method(
            "Blue debit", account.id, "debit_card"
        )
        source = tmp_path / "statement.csv"
        source.write_text(
            "Data;Descrizione;Importo\n"
            "01/07/2026;Coffee;-3,50\n"
            "04/07/2026;Refund;12,00\n"
            "30/06/2026;Before period;-2,00\n",
            encoding="utf-8",
        )

        service = ImportService(db)
        table = service.read_spreadsheet(source)
        preview = service.preview_bank_statement(
            table,
            StatementMapping(
                payment_method_id=card.id,
                period_start="2026-07-01",
                period_end="2026-07-31",
                date_column=0,
                description_column=1,
                amount_column=2,
            ),
        )

        assert preview.errors == ()
        assert preview.import_count == 2
        assert preview.outside_period_count == 1
        assert [row.transaction_type for row in preview.rows] == [
            "expense",
            "income",
        ]
        assert service.import_transactions(preview) == 2
        imported = TransactionService(db).list_transactions()
        assert {transaction.payment_method_id for transaction in imported} == {
            card.id
        }

        repeated = service.preview_bank_statement(
            table,
            StatementMapping(
                payment_method_id=card.id,
                period_start="2026-07-01",
                period_end="2026-07-31",
                date_column=0,
                description_column=1,
                amount_column=2,
            ),
        )
        assert repeated.import_count == 0
        assert repeated.duplicate_count == 2
    finally:
        db.close()


def test_bank_statement_reads_xlsx_sheets_and_split_debit_credit(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path / "app-data"))
    db = connect(tmp_path / "money.db")
    try:
        account = AccountService(db).create_account("Bank", "current_account")
        card = PaymentMethodService(db).create_payment_method(
            "Daily card", account.id, "debit_card"
        )
        source = tmp_path / "bank.xlsx"
        _write_minimal_statement_xlsx(source)

        service = ImportService(db)
        assert service.spreadsheet_sheets(source) == ("July",)
        table = service.read_spreadsheet(source, "July")
        assert table.headers == ("Booking date", "Details", "Debit", "Credit")
        assert table.header_row_number == 3
        preview = service.preview_bank_statement(
            table,
            StatementMapping(
                payment_method_id=card.id,
                period_start="2026-07-01",
                period_end="2026-07-31",
                date_column=0,
                description_column=1,
                amount_mode="split",
                debit_column=2,
                credit_column=3,
            ),
        )

        assert preview.errors == ()
        assert [(row.transaction_type, row.amount) for row in preview.rows] == [
            ("expense", 4),
            ("income", 20),
        ]
    finally:
        db.close()


def _write_minimal_statement_xlsx(target: Path) -> None:
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
    root_relationships = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
    workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="July" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    workbook_relationships = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""
    worksheet = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="inlineStr"><is><t>Card statement for July</t></is></c>
    </row>
    <row r="3">
      <c r="A3" t="inlineStr"><is><t>Booking date</t></is></c>
      <c r="B3" t="inlineStr"><is><t>Details</t></is></c>
      <c r="C3" t="inlineStr"><is><t>Debit</t></is></c>
      <c r="D3" t="inlineStr"><is><t>Credit</t></is></c>
    </row>
    <row r="4">
      <c r="A4" t="inlineStr"><is><t>2026-07-03</t></is></c>
      <c r="B4" t="inlineStr"><is><t>Lunch</t></is></c>
      <c r="C4"><v>4</v></c>
    </row>
    <row r="5">
      <c r="A5" t="inlineStr"><is><t>2026-07-05</t></is></c>
      <c r="B5" t="inlineStr"><is><t>Cashback</t></is></c>
      <c r="D5"><v>20</v></c>
    </row>
  </sheetData>
</worksheet>"""
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_relationships)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_relationships)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
