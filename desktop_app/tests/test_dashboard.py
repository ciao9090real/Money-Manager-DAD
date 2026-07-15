from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.database import connect
from app.core.paths import backup_dir
from app.services.account_service import AccountService
from app.services.backup_service import BackupService
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


def test_dashboard_with_zero_data(db):
    summary = DashboardService(db).summary()

    assert summary["net_worth"] == Decimal("0")
    assert summary["total_assets"] == Decimal("0")
    assert summary["liquidity"] == Decimal("0")
    assert summary["investments_property"] == Decimal("0")
    assert summary["total_debt"] == Decimal("0")
    assert summary["monthly_income"] == Decimal("0")
    assert summary["monthly_expenses"] == Decimal("0")
    assert summary["monthly_net_flow"] == Decimal("0")
    assert summary["recent_transactions"] == []
    assert summary["accounts"] == []


def test_dashboard_debt_is_absolute_per_liability(db):
    accounts = AccountService(db)
    transactions = TransactionService(db)
    dashboard = DashboardService(db)
    accounts.create_account("Current", "current_account", opening_balance="1000")
    accounts.create_account("Credit card", "credit_card", opening_balance="500")
    overpaid = accounts.create_account("Overpaid card", "credit_card", opening_balance="0")
    transactions.add_adjustment(overpaid.id, "100", "2026-07-10", "Overpayment")

    summary = dashboard.global_snapshot()

    assert summary["net_worth"] == Decimal("600.00")
    assert summary["total_debt"] == Decimal("500.00")


def test_dashboard_scope_includes_descendant_accounts_only(db):
    accounts = AccountService(db)
    transactions = TransactionService(db)
    payment_methods = PaymentMethodService(db)
    dashboard = DashboardService(db)
    bank = accounts.create_account("Intesa Sanpaolo", "bank")
    current = accounts.create_account("Current account", "current_account", parent_id=bank.id, opening_balance="100")
    savings = accounts.create_account("Savings account", "savings_account", parent_id=bank.id, opening_balance="50")
    other = accounts.create_account("Revolut", "current_account", opening_balance="200")
    payment_methods.create_payment_method("Debit card", current.id, "debit_card")
    transactions.add_income(current.id, "25", "2026-07-10", "Salary")
    transactions.add_expense(other.id, "40", "2026-07-10", "Groceries")

    global_summary = dashboard.global_snapshot()
    scoped = dashboard.scope_summary(bank.id, "2026-07-01", "2026-08-01")

    assert global_summary["net_worth"] == Decimal("335.00")
    assert scoped["scope_label"] == "Intesa Sanpaolo"
    assert scoped["selected_balance"] == Decimal("175.00")
    assert scoped["monthly_income"] == Decimal("25.00")
    assert scoped["monthly_expenses"] == Decimal("0.00")
    assert scoped["child_account_count"] == 2
    assert scoped["payment_method_count"] == 1
    assert {account["id"] for account in scoped["accounts"]} == {bank.id, current.id, savings.id}


def test_backup_creates_database_copy(db):
    target = BackupService(db).create_backup()

    assert target.exists()
    assert target.parent == backup_dir()
    assert target.name.startswith("money_manager_backup_")
    assert target.suffix == ".db"
