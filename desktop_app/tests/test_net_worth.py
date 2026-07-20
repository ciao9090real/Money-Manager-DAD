from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.core.database import connect
from app.services.account_service import AccountService
from app.services.investment_service import InvestmentService
from app.services.loan_service import LoanService
from app.services.net_worth_service import NetWorthService
from app.services.transaction_service import TransactionService


@pytest.fixture()
def services(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        yield (
            db,
            AccountService(db),
            TransactionService(db),
            InvestmentService(db),
            LoanService(db),
            NetWorthService(db),
        )
    finally:
        db.close()


def test_current_counts_investment_accounts_once_and_borrowing_as_debt(services):
    _db, accounts, _transactions, investments, loans, net_worth = services
    current = accounts.create_account(
        "Current",
        "current_account",
        opening_balance="1000",
    )
    investments.create_investment(
        "Index",
        "etf",
        current.id,
        "200",
        "2026-07-01",
        current_value="250",
    )
    loans.create_loan(
        "borrowed",
        "Car loan",
        "Bank",
        current.id,
        "400",
        "2026-07-02",
    )

    point = net_worth.current()

    assert point.assets == Decimal("1450.00")
    assert point.liabilities == Decimal("400.00")
    assert point.net_worth == Decimal("1050.00")
    assert not point.estimated


def test_record_snapshot_is_idempotent_and_updates_changed_same_day_value(services):
    db, accounts, transactions, _investments, _loans, net_worth = services
    current = accounts.create_account(
        "Current",
        "current_account",
        opening_balance="100",
    )

    first = net_worth.record_snapshot()
    second = net_worth.record_snapshot()
    stored = db.execute(
        "SELECT assets_cents, revision FROM net_worth_snapshots WHERE date = ?",
        (first.date,),
    ).fetchone()

    assert first == second
    assert db.execute("SELECT COUNT(*) FROM net_worth_snapshots").fetchone()[0] == 1
    assert stored["assets_cents"] == 10000
    assert stored["revision"] == 1

    transactions.add_income(current.id, "25", date.today().isoformat(), "Income")
    updated = net_worth.record_snapshot()
    stored = db.execute(
        "SELECT assets_cents, revision FROM net_worth_snapshots WHERE date = ?",
        (first.date,),
    ).fetchone()

    assert updated.assets == Decimal("125.00")
    assert stored["assets_cents"] == 12500
    assert stored["revision"] == 2
    changes = db.execute(
        """
        SELECT operation, revision FROM change_log
        WHERE entity_type = 'net_worth_snapshots' AND entity_id = ?
        ORDER BY sequence
        """,
        (first.date,),
    ).fetchall()
    assert [(row["operation"], row["revision"]) for row in changes] == [
        ("insert", 1),
        ("update", 2),
    ]


def test_history_uses_month_end_cutoffs_and_backfills_ledger_and_loans(services):
    _db, accounts, transactions, _investments, loans, net_worth = services
    current = accounts.create_account(
        "Current",
        "current_account",
        opening_balance="1000",
    )
    transactions.add_expense(current.id, "100", "2026-01-10", "January")
    transactions.add_expense(current.id, "200", "2026-02-10", "February")
    borrowed = loans.create_loan(
        "borrowed",
        "Loan",
        "Bank",
        current.id,
        "500",
        "2026-02-05",
    )
    transactions.add_income(current.id, "50", "2026-03-01", "March")
    loans.record_payment(borrowed.loan.id, current.id, "100", "2026-03-05")

    points = net_worth.history(3, date(2026, 3, 20))

    assert [point.date for point in points] == [
        "2026-01-31",
        "2026-02-28",
        "2026-03-20",
    ]
    assert [
        (point.assets, point.liabilities, point.net_worth)
        for point in points
    ] == [
        (Decimal("900.00"), Decimal("0.00"), Decimal("900.00")),
        (Decimal("1200.00"), Decimal("500.00"), Decimal("700.00")),
        (Decimal("1150.00"), Decimal("400.00"), Decimal("750.00")),
    ]
    assert all(point.estimated for point in points)


def test_history_prefers_an_exact_recorded_snapshot(services):
    db, _accounts, _transactions, _investments, _loans, net_worth = services
    db.execute(
        """
        INSERT INTO net_worth_snapshots (date, assets_cents, liabilities_cents)
        VALUES ('2026-01-31', 12345, 2345)
        """
    )
    db.commit()

    point = net_worth.history(1, date(2026, 1, 31))[0]

    assert point.assets == Decimal("123.45")
    assert point.liabilities == Decimal("23.45")
    assert point.net_worth == Decimal("100.00")
    assert not point.estimated


def test_history_rejects_an_empty_period(services):
    _db, _accounts, _transactions, _investments, _loans, net_worth = services

    with pytest.raises(ValueError, match="at least 1"):
        net_worth.history(0)
