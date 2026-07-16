from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.core.database import connect
from app.services.account_service import AccountService
from app.services.recurring_service import RecurringService
from app.services.reporting_service import ReportingService
from app.services.transaction_service import TransactionService


@pytest.fixture()
def services(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        yield db, AccountService(db), RecurringService(db), ReportingService(db)
    finally:
        db.close()


def test_forecast_projects_three_and_six_month_recurring_cash_flow(services):
    _db, accounts, recurring, reporting = services
    current = accounts.create_account("Current", "current_account", opening_balance="500")
    recurring.create_rule(
        "Wage",
        "other",
        "fixed",
        current.id,
        "monthly",
        "2027-02-01",
        amount="3000",
        transaction_type="income",
    )
    recurring.create_rule(
        "Living costs",
        "bill",
        "fixed",
        current.id,
        "monthly",
        "2027-02-01",
        amount="1000",
    )

    forecast = reporting.cash_forecast(date(2027, 1, 15))

    assert forecast["current_balance"] == Decimal("500.00")
    assert forecast["three_month_income"] == Decimal("9000.00")
    assert forecast["three_month_outgoings"] == Decimal("3000.00")
    assert forecast["three_month_balance"] == Decimal("6500.00")
    assert forecast["six_month_income"] == Decimal("18000.00")
    assert forecast["six_month_outgoings"] == Decimal("6000.00")
    assert forecast["six_month_balance"] == Decimal("12500.00")


def test_forecast_reports_decline_and_excludes_unknown_variable_amounts(services):
    _db, accounts, recurring, reporting = services
    current = accounts.create_account("Current", "current_account", opening_balance="1000")
    recurring.create_rule(
        "Wage",
        "other",
        "fixed",
        current.id,
        "monthly",
        "2027-02-01",
        amount="500",
        transaction_type="income",
    )
    recurring.create_rule(
        "Rent",
        "bill",
        "fixed",
        current.id,
        "monthly",
        "2027-02-01",
        amount="600",
    )
    recurring.create_rule(
        "Electricity",
        "bill",
        "variable",
        current.id,
        "monthly",
        "2027-02-05",
    )

    forecast = reporting.cash_forecast(date(2027, 1, 15))

    assert forecast["six_month_change"] == Decimal("-600.00")
    assert forecast["six_month_balance"] == Decimal("400.00")
    assert forecast["unknown_amount_count"] == 1


def test_paused_schedules_do_not_affect_forecast(services):
    _db, accounts, recurring, reporting = services
    current = accounts.create_account("Current", "current_account", opening_balance="100")
    wage = recurring.create_rule(
        "Paused wage",
        "other",
        "fixed",
        current.id,
        "monthly",
        "2027-02-01",
        amount="1000",
        transaction_type="income",
    )
    recurring.set_paused(wage.id, True)

    forecast = reporting.cash_forecast(date(2027, 1, 15))

    assert forecast["six_month_change"] == Decimal("0")
    assert forecast["six_month_balance"] == Decimal("100.00")
    assert forecast["known_schedule_count"] == 0


def test_monthly_cash_flow_fills_empty_months_and_excludes_transfers(services):
    db, accounts, _recurring, reporting = services
    transactions = TransactionService(db)
    current = accounts.create_account("Current", "current_account", opening_balance="1000")
    savings = accounts.create_account("Savings", "savings_account")
    transactions.add_income(current.id, "2000", "2026-04-01", "Wage")
    transactions.add_expense(current.id, "450", "2026-04-12", "Rent")
    transactions.add_transfer(current.id, savings.id, "200", "2026-05-01", "Save")
    transactions.add_expense(current.id, "75", "2026-06-05", "Utilities")

    months = reporting.monthly_cash_flow(3, date(2026, 6, 15))

    assert [(item["month"], item["income"], item["expenses"]) for item in months] == [
        ("2026-04", Decimal("2000.00"), Decimal("450.00")),
        ("2026-05", Decimal("0.00"), Decimal("0.00")),
        ("2026-06", Decimal("0.00"), Decimal("75.00")),
    ]
