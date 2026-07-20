from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.core.database import connect
from app.services.account_service import AccountService
from app.services.dashboard_service import DashboardService
from app.services.transaction_service import TransactionService


@pytest.fixture()
def services(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        yield db, AccountService(db), TransactionService(db), DashboardService(db)
    finally:
        db.close()


def test_savings_rate_aggregates_months_and_excludes_transfers(services):
    _db, accounts, transactions, dashboard = services
    current = accounts.create_account("Current", "current_account")
    savings = accounts.create_account("Savings", "savings_account")
    transactions.add_income(current.id, "2000", "2026-04-01", "Wage")
    transactions.add_expense(current.id, "500", "2026-04-10", "Rent")
    transactions.add_income(current.id, "1000", "2026-05-01", "Wage")
    transactions.add_expense(current.id, "250", "2026-05-10", "Bills")
    transactions.add_expense(current.id, "250", "2026-06-10", "Bills")
    transactions.add_transfer(current.id, savings.id, "300", "2026-06-12", "Save")

    assert dashboard.savings_rate(3, date(2026, 6, 15)) == Decimal("0.6667")


def test_savings_rate_is_zero_without_income_and_validates_months(services):
    _db, accounts, transactions, dashboard = services
    current = accounts.create_account("Current", "current_account")
    transactions.add_expense(current.id, "100", "2026-06-10", "Bills")

    assert dashboard.savings_rate(1, date(2026, 6, 15)) == Decimal("0")
    with pytest.raises(ValueError, match="at least 1"):
        dashboard.savings_rate(0, date(2026, 6, 15))


def test_emergency_coverage_uses_six_completed_calendar_months(services):
    _db, accounts, transactions, dashboard = services
    current = accounts.create_account(
        "Current",
        "current_account",
        opening_balance="12000",
    )
    for month in range(1, 7):
        transactions.add_expense(
            current.id,
            "1000",
            f"2026-{month:02d}-10",
            "Living costs",
        )

    assert dashboard.emergency_fund_coverage(
        date(2026, 7, 20),
    ) == Decimal("6.00")


def test_emergency_coverage_is_zero_for_nonpositive_liquidity_or_no_expenses(services):
    _db, accounts, transactions, dashboard = services
    overdrawn = accounts.create_account(
        "Overdrawn",
        "current_account",
        opening_balance="-100",
    )
    transactions.add_expense(overdrawn.id, "100", "2026-06-10", "Bills")

    assert dashboard.emergency_fund_coverage(date(2026, 7, 20)) == Decimal("0")

    positive = accounts.create_account(
        "Cash",
        "cash",
        opening_balance="500",
    )
    transactions.add_income(positive.id, "500", "2026-07-01", "Income")
    assert dashboard.emergency_fund_coverage(date(2025, 7, 20)) == Decimal("0")


def test_global_snapshot_surfaces_health_metrics_and_thresholds(services):
    _db, accounts, transactions, dashboard = services
    current = accounts.create_account("Current", "current_account")
    today = date.today().isoformat()
    transactions.add_income(current.id, "1000", today, "Income")
    transactions.add_expense(current.id, "250", today, "Expense")

    snapshot = dashboard.global_snapshot()

    assert snapshot["savings_rate"] == Decimal("0.7500")
    assert "emergency_fund_coverage" in snapshot
    assert dashboard.EMERGENCY_FUND_WARNING_MONTHS == Decimal("3")
    assert dashboard.EMERGENCY_FUND_HEALTHY_MONTHS == Decimal("6")
