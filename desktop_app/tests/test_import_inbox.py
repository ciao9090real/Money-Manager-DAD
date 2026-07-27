from __future__ import annotations

import json

import pytest

from app.core.database import connect
from app.services.account_service import AccountService
from app.services.category_service import CategoryService
from app.services.home_service import HomeService
from app.services.import_inbox_service import ImportInboxService
from app.services.import_service import ImportService
from app.services.transaction_service import TransactionService


def _csv(target, rows: str) -> None:
    target.write_text(
        "date,type,account,amount,description,category\n" + rows,
        encoding="utf-8",
    )


def test_import_is_staged_until_rows_are_reviewed_and_posted(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path / "data"))
    db = connect(tmp_path / "money.db")
    try:
        account = AccountService(db).create_account(
            "Everyday", "current_account"
        )
        food = CategoryService(db).create_category("Food", "expense")
        salary = CategoryService(db).create_category("Salary", "income")
        transactions = TransactionService(db)
        transactions.add_expense(
            account.id, "9.50", "2026-07-02", "Already recorded"
        )
        source = tmp_path / "statement.csv"
        _csv(
            source,
            "2026-07-01,expense,Everyday,12.40,Coffee,\n"
            "2026-07-02,expense,Everyday,9.50,Already recorded,\n"
            "2026-07-03,income,Everyday,2200,Salary,Salary\n",
        )

        preview = ImportService(db).preview_transactions_csv(source)
        inbox = ImportInboxService(db)
        batch = inbox.stage_preview(preview)

        assert len(transactions.list_transactions()) == 1
        summary = inbox.list_batches()[0]
        assert summary.batch.id == batch.id
        assert summary.needs_category_count == 1
        assert summary.ready_count == 1
        assert summary.duplicate_count == 1

        rows = inbox.list_rows(batch.id)
        coffee = next(row for row in rows if row.description == "Coffee")
        assert inbox.set_category([coffee.id], food.id) == 1
        assert inbox.post_ready(batch.id) == 2

        assert len(transactions.list_transactions()) == 3
        closed = inbox.list_batches()[0]
        assert closed.batch.status == "posted"
        assert closed.posted_count == 2
        assert all(
            row.status in {"posted", "duplicate"}
            for row in inbox.list_rows(batch.id)
        )
        assert salary.id in {
            transaction.category_id
            for transaction in transactions.list_transactions()
        }
    finally:
        db.close()


def test_posting_a_batch_is_atomic(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path / "data"))
    db = connect(tmp_path / "money.db")
    try:
        AccountService(db).create_account("Everyday", "current_account")
        CategoryService(db).create_category("Food", "expense")
        source = tmp_path / "two.csv"
        _csv(
            source,
            "2026-07-01,expense,Everyday,10,One,Food\n"
            "2026-07-02,expense,Everyday,20,Two,Food\n",
        )
        inbox = ImportInboxService(db)
        batch = inbox.stage_preview(
            ImportService(db).preview_transactions_csv(source)
        )
        original = inbox.transactions.add_expense
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("simulated posting failure")
            return original(*args, **kwargs)

        monkeypatch.setattr(inbox.transactions, "add_expense", fail_second)
        with pytest.raises(RuntimeError, match="simulated"):
            inbox.post_ready(batch.id)

        assert TransactionService(db).list_transactions() == []
        assert {row.status for row in inbox.list_rows(batch.id)} == {"ready"}
        assert inbox.list_batches()[0].batch.status == "review"
    finally:
        db.close()


def test_parse_issues_are_persisted_without_storing_the_source_file(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path / "data"))
    db = connect(tmp_path / "money.db")
    try:
        AccountService(db).create_account("Everyday", "current_account")
        source = tmp_path / "private-bank-download.csv"
        source.write_text(
            "date,type,account,amount,description,secret_bank_field\n"
            "not-a-date,expense,Everyday,15,Coffee,do-not-stage\n",
            encoding="utf-8",
        )
        inbox = ImportInboxService(db)
        batch = inbox.stage_preview(
            ImportService(db).preview_transactions_csv(source)
        )

        rows = inbox.list_rows(batch.id)
        assert len(rows) == 1
        assert rows[0].status == "error"
        assert rows[0].issue_code == "parse_error"
        raw = json.loads(rows[0].raw_payload_json)
        assert "secret_bank_field" not in raw
        assert "do-not-stage" not in rows[0].raw_payload_json
        stored = db.execute(
            "SELECT source_name, mapping_json FROM import_batches WHERE id = ?",
            (batch.id,),
        ).fetchone()
        assert stored["source_name"] == source.name
        assert str(source.resolve()) not in stored["mapping_json"]

        assert inbox.ignore_rows([rows[0].id]) == 1
        assert inbox.list_batches()[0].batch.status == "review"
        assert inbox.restore_rows([rows[0].id]) == 1
        assert inbox.list_rows(batch.id)[0].status == "error"
        inbox.cancel_batch(batch.id)
        assert inbox.list_batches()[0].batch.status == "cancelled"
    finally:
        db.close()


def test_home_surfaces_the_exact_import_batch_needing_attention(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path / "data"))
    db = connect(tmp_path / "money.db")
    try:
        AccountService(db).create_account("Everyday", "current_account")
        source = tmp_path / "review.csv"
        _csv(
            source,
            "2026-07-01,expense,Everyday,12.40,Coffee,\n",
        )
        batch = ImportInboxService(db).stage_preview(
            ImportService(db).preview_transactions_csv(source)
        )

        brief = HomeService(db).brief()

        assert brief.primary_action.id == f"import:{batch.id}"
        assert brief.primary_action.route.workspace == "activity"
        assert brief.primary_action.route.section == "import"
        assert brief.primary_action.route.entity_id == batch.id
    finally:
        db.close()
