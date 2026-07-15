from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.core.database import connect
from app.services.account_service import AccountService
from app.services.recurring_service import RecurringService
from app.services.reporting_service import ReportingService


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
