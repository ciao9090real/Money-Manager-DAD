from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.core.database import connect
from app.services.account_service import AccountService
from app.services.loan_service import LoanService


@pytest.fixture()
def services(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    accounts = AccountService(db)
    loans = LoanService(db)
    account = accounts.create_account(
        "Current",
        "current_account",
        opening_balance="20000",
    )
    try:
        yield db, account, loans
    finally:
        db.close()


def test_due_date_schedule_matches_known_first_period_and_reconciles_cents(services):
    _db, account, loans = services
    created = loans.create_loan(
        "borrowed",
        "Two-year loan",
        "Bank",
        account.id,
        "10000",
        "2026-01-01",
        due_date="2028-01-01",
        interest_rate="6",
    )

    schedule = loans.amortization_schedule(
        created.loan.id,
        reference_date=date(2026, 1, 1),
    )

    assert len(schedule) == 24
    assert schedule[0].date == "2026-02-01"
    assert schedule[0].payment == Decimal("443.21")
    assert schedule[0].interest_portion == Decimal("50.00")
    assert schedule[0].principal_portion == Decimal("393.21")
    assert schedule[0].remaining_balance == Decimal("9606.79")
    assert schedule[-1].date == "2028-01-01"
    assert schedule[-1].remaining_balance == Decimal("0.00")
    assert sum(
        (entry.principal_portion for entry in schedule),
        Decimal("0"),
    ) == Decimal("10000.00")


def test_custom_zero_interest_schedule_and_non_amortizing_validation(services):
    _db, account, loans = services
    zero_rate = loans.create_loan(
        "borrowed",
        "Zero-rate loan",
        "Family",
        account.id,
        "1200",
        "2026-01-01",
    )

    schedule = loans.amortization_schedule(
        zero_rate.loan.id,
        "100",
        date(2026, 1, 1),
    )

    assert len(schedule) == 12
    assert all(entry.interest_portion == Decimal("0.00") for entry in schedule)
    assert schedule[-1].payment == Decimal("100.00")

    interest_only = loans.create_loan(
        "borrowed",
        "Interest-only amount",
        "Bank",
        account.id,
        "10000",
        "2026-01-01",
        interest_rate="6",
    )
    with pytest.raises(ValueError, match="greater than the monthly interest"):
        loans.amortization_schedule(
            interest_only.loan.id,
            "50",
            date(2026, 1, 1),
        )


def test_missing_or_expired_due_date_cannot_derive_minimum(services):
    _db, account, loans = services
    no_due_date = loans.create_loan(
        "borrowed",
        "Open-ended loan",
        "Bank",
        account.id,
        "1000",
        "2026-01-01",
    )

    with pytest.raises(ValueError, match="due date is required"):
        loans.amortization_schedule(
            no_due_date.loan.id,
            reference_date=date(2026, 1, 1),
        )

    expired = loans.create_loan(
        "borrowed",
        "Expired loan",
        "Bank",
        account.id,
        "1000",
        "2026-01-01",
        due_date="2026-06-01",
    )
    with pytest.raises(ValueError, match="must be after"):
        loans.amortization_schedule(
            expired.loan.id,
            reference_date=date(2026, 7, 1),
        )


def test_payoff_comparison_reports_interest_and_period_savings(services):
    _db, account, loans = services
    created = loans.create_loan(
        "borrowed",
        "Comparison loan",
        "Bank",
        account.id,
        "10000",
        "2026-01-01",
        due_date="2028-01-01",
        interest_rate="6",
    )

    comparison = loans.payoff_comparison(
        created.loan.id,
        "50",
        reference_date=date(2026, 1, 1),
    )
    baseline = comparison["without_extra"]
    accelerated = comparison["with_extra"]

    assert baseline.payoff_date == "2028-01-01"
    assert accelerated.payoff_date < baseline.payoff_date
    assert accelerated.total_interest_paid < baseline.total_interest_paid
    assert comparison["interest_saved"] > 0
    assert comparison["periods_saved"] == comparison["months_saved"]
    assert comparison["periods_saved"] > 0


def test_multi_loan_strategy_orders_and_rolls_extra_budget(services):
    _db, account, loans = services
    small = loans.create_loan(
        "borrowed",
        "Small",
        "Bank",
        account.id,
        "1000",
        "2026-01-01",
        due_date="2028-01-01",
        interest_rate="3",
    )
    expensive = loans.create_loan(
        "borrowed",
        "Expensive",
        "Bank",
        account.id,
        "2000",
        "2026-01-01",
        due_date="2028-01-01",
        interest_rate="8",
    )

    snowball = loans.multi_loan_strategy(
        "snowball",
        "100",
        date(2026, 1, 1),
    )
    avalanche = loans.multi_loan_strategy(
        "avalanche",
        "100",
        date(2026, 1, 1),
    )

    assert [plan.loan_id for plan in snowball] == [small.loan.id, expensive.loan.id]
    assert [plan.loan_id for plan in avalanche] == [expensive.loan.id, small.loan.id]
    assert all(plan.entries[-1].remaining_balance == Decimal("0.00") for plan in snowball)
    assert all(plan.entries[-1].remaining_balance == Decimal("0.00") for plan in avalanche)
    assert snowball[0].entries[0].payment > loans.amortization_schedule(
        small.loan.id,
        reference_date=date(2026, 1, 1),
    )[0].payment


def test_multi_loan_strategy_requires_due_dates_for_every_active_debt(services):
    _db, account, loans = services
    loans.create_loan(
        "borrowed",
        "No maturity",
        "Bank",
        account.id,
        "500",
        "2026-01-01",
    )

    with pytest.raises(ValueError, match="due date is required"):
        loans.multi_loan_strategy(
            "snowball",
            "50",
            date(2026, 1, 1),
        )
