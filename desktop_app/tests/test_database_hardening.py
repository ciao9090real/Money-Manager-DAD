from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.database import connect
from app.core.migrations import SCHEMA_VERSION, assert_database_integrity
from app.repositories.transaction_repository import TransactionRepository
from app.services.account_service import AccountService
from app.services.category_service import CategoryService
from app.services.dashboard_service import DashboardService
from app.services.payment_method_service import PaymentMethodService
from app.services.transaction_service import TransactionService


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


def test_connection_pragmas_and_integrity(db):
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert db.execute("PRAGMA synchronous").fetchone()[0] == 1
    assert db.execute("PRAGMA busy_timeout").fetchone()[0] == 10_000
    assert_database_integrity(db)


def test_legacy_fixture_migrates_with_backup(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path / "app-data"))
    source = tmp_path / "legacy.db"
    fixture = Path(__file__).parent / "fixtures" / "legacy_v1.sql"
    legacy = sqlite3.connect(source)
    legacy.executescript(fixture.read_text(encoding="utf-8"))
    legacy.close()

    migrated = connect(source)
    try:
        assert migrated.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert migrated.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 4
        balances = AccountService(migrated)
        account_ids = {
            row["name"]: row["id"]
            for row in migrated.execute("SELECT id, name FROM accounts")
        }
        assert all(len(account_id) == 36 for account_id in account_ids.values())
        assert balances.account_balance(account_ids["Current"]) == Decimal("95")
        assert balances.account_balance(account_ids["Savings"]) == Decimal("70")
        assert migrated.execute(
            "SELECT opening_balance_cents FROM accounts WHERE name = 'Current'"
        ).fetchone()[0] == 10_000
        assert_database_integrity(migrated)
    finally:
        migrated.close()

    backups = list((tmp_path / "backups").glob("money_manager_pre_migration_v1_*.db"))
    assert len(backups) == 1
    backup = sqlite3.connect(backups[0])
    try:
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 1
        assert backup.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 4
    finally:
        backup.close()


def test_transfer_rolls_back_when_second_post_fails(db, monkeypatch):
    accounts = AccountService(db)
    service = TransactionService(db)
    source = accounts.create_account("Current", "current_account", opening_balance="100")
    target = accounts.create_account("Savings", "savings_account")
    original_create = service.transactions.create
    calls = 0

    def fail_second_create(transaction):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise sqlite3.IntegrityError("simulated second-post failure")
        return original_create(transaction)

    monkeypatch.setattr(service.transactions, "create", fail_second_create)
    with pytest.raises(sqlite3.IntegrityError, match="second-post"):
        service.add_transfer(source.id, target.id, "25", "2026-07-10")

    assert service.list_transactions() == []
    assert accounts.account_balance(source.id) == Decimal("100")
    assert accounts.account_balance(target.id) == Decimal("0")


def test_transaction_service_validates_category_and_payment_account(db):
    accounts = AccountService(db)
    transactions = TransactionService(db)
    payments = PaymentMethodService(db)
    first = accounts.create_account("First", "current_account")
    second = accounts.create_account("Second", "current_account")
    category = CategoryService(db).create_category("Salary", "income").id
    method = payments.create_payment_method("First card", first.id, "debit_card")

    with pytest.raises(ValueError, match="Category type"):
        transactions.add_expense(second.id, "10", "2026-07-10", category_id=category)
    with pytest.raises(ValueError, match="does not belong"):
        transactions.add_expense(
            second.id, "10", "2026-07-10", payment_method_id=method.id
        )
    assert transactions.list_transactions() == []


def test_inline_category_rolls_back_when_transaction_is_invalid(db):
    account = AccountService(db).create_account("Current", "current_account")
    service = TransactionService(db)

    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        service.add_income(account.id, "10", "not-a-date", category_id="Salary")

    assert service.categories.list() == []


def test_parent_with_active_child_cannot_be_deactivated(db):
    accounts = AccountService(db)
    parent = accounts.create_account("Parent", "bank")
    accounts.create_account("Child", "current_account", parent_id=parent.id)

    with pytest.raises(ValueError, match="child"):
        accounts.deactivate_account(parent.id)


def test_categories_and_payment_methods_can_be_edited_archived_and_restored(db):
    account = AccountService(db).create_account("Current", "current_account")
    categories = CategoryService(db)
    payments = PaymentMethodService(db)

    category = categories.create_category("Food", "expense")
    category = categories.update_category(category.id, "Groceries", "expense")
    categories.archive_category(category.id)
    assert categories.categories.get(category.id).is_active is False
    categories.restore_category(category.id)
    assert categories.categories.get(category.id).is_active is True

    method = payments.create_payment_method("Card", account.id, "debit_card")
    method = payments.update_payment_method(method.id, "Main card", account.id, "debit_card")
    payments.archive_payment_method(method.id)
    assert payments.payment_methods.get(method.id).is_active is False
    payments.restore_payment_method(method.id)
    assert payments.payment_methods.get(method.id).is_active is True


def test_filters_and_keyset_cursor_are_database_backed(db):
    account = AccountService(db).create_account("Current", "current_account")
    service = TransactionService(db)
    for day in ("2026-07-03", "2026-07-02", "2026-07-01"):
        service.add_income(account.id, "1", day, f"Income {day}")
    service.add_expense(account.id, "1", "2026-07-04", "Expense")

    first_page = service.list_transactions(limit=2, transaction_type="income")
    cursor = (first_page[-1].date, first_page[-1].id)
    second_page = service.list_transactions(
        limit=2, transaction_type="income", cursor=cursor
    )

    assert [item.date for item in first_page] == ["2026-07-03", "2026-07-02"]
    assert [item.date for item in second_page] == ["2026-07-01"]
    assert not ({item.id for item in first_page} & {item.id for item in second_page})


def test_account_tree_and_dashboard_avoid_n_plus_one_queries(db):
    accounts = AccountService(db)
    for index in range(25):
        accounts.create_account(f"Account {index}", "current_account")
    statements: list[str] = []
    db.set_trace_callback(statements.append)
    accounts.account_tree()
    account_selects = [
        sql for sql in statements if sql.lstrip().upper().startswith(("SELECT", "WITH"))
    ]
    assert len(account_selects) == 1

    statements.clear()
    DashboardService(db).summary()
    dashboard_selects = [
        sql for sql in statements if sql.lstrip().upper().startswith(("SELECT", "WITH"))
    ]
    db.set_trace_callback(None)
    # Accounts, active loans, monthly totals, and recent activity stay constant
    # regardless of the number of account or loan rows.
    assert len(dashboard_selects) == 4


def test_dashboard_distinguishes_net_worth_and_liquidity(db):
    accounts = AccountService(db)
    accounts.create_account("Cash", "current_account", opening_balance="100")
    accounts.create_account("Brokerage", "investment", opening_balance="50")
    accounts.create_account("Loan", "loan", opening_balance="30")

    summary = DashboardService(db).summary()

    assert summary["net_worth"] == Decimal("120")
    assert summary["liquidity"] == Decimal("100")


def test_composite_indexes_are_used_for_filtered_lists(db):
    plans = db.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT * FROM transactions
        WHERE type = ? AND deleted_at IS NULL
        ORDER BY date DESC, id DESC
        LIMIT 100
        """,
        ("expense",),
    ).fetchall()
    detail = " ".join(str(row[3]) for row in plans)
    assert "idx_transactions_type_date" in detail

    latest_plans = db.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT * FROM transactions
        WHERE deleted_at IS NULL
        ORDER BY date DESC, id DESC
        LIMIT 100
        """
    ).fetchall()
    latest_detail = " ".join(str(row[3]) for row in latest_plans)
    assert "idx_transactions_date" in latest_detail

    repository = TransactionRepository(db)
    assert repository.monthly_totals("2026-07-01", "2026-08-01") == (
        Decimal("0"),
        Decimal("0"),
    )
