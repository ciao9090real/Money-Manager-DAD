from __future__ import annotations

import sqlite3
from decimal import Decimal

import pytest

from app.core.database import connect
from app.core.migrations import (
    SCHEMA_VERSION,
    _create_initial_schema,
    _migrate_v2,
    _migrate_v3,
    _migrate_v4,
    _migrate_v5,
    _run_migration,
)
from app.services.account_service import AccountService
from app.services.dashboard_service import DashboardService
from app.services.loan_service import LoanService


@pytest.fixture()
def services(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        yield db, AccountService(db), LoanService(db)
    finally:
        db.close()


def test_borrowed_loan_increases_cash_without_increasing_net_worth(services):
    db, accounts, loans = services
    current = accounts.create_account("Current", "current_account", opening_balance="1000")

    snapshot = loans.create_loan(
        "borrowed",
        "Car loan",
        "Local bank",
        current.id,
        "500",
        "2026-07-15",
        due_date="2028-07-15",
        interest_rate="4.5",
    )
    dashboard = DashboardService(db).global_snapshot()

    assert snapshot.outstanding == Decimal("500.00")
    assert accounts.account_balance(current.id) == Decimal("1500.00")
    assert dashboard["borrowed_loans"] == Decimal("500.00")
    assert dashboard["total_debt"] == Decimal("500.00")
    assert dashboard["net_worth"] == Decimal("1000.00")


def test_reference_interest_rate_does_not_accrue_into_principal_balance(services):
    _db, accounts, loans = services
    current = accounts.create_account("Current", "current_account")

    snapshot = loans.create_loan(
        "borrowed",
        "Reference-rate loan",
        "Bank",
        current.id,
        "1000",
        "2026-01-01",
        due_date="2030-01-01",
        interest_rate="12.5",
    )

    assert loans.CALCULATION_MODE == "principal_only"
    assert snapshot.outstanding == Decimal("1000.00")
    assert loans.summary()["borrowed"] == Decimal("1000.00")


def test_lent_loan_creates_a_receivable_without_reducing_net_worth(services):
    db, accounts, loans = services
    current = accounts.create_account("Current", "current_account", opening_balance="1000")

    snapshot = loans.create_loan(
        "lent",
        "Family loan",
        "Alex",
        current.id,
        "200",
        "2026-07-15",
    )
    dashboard = DashboardService(db).global_snapshot()

    assert snapshot.outstanding == Decimal("200.00")
    assert accounts.account_balance(current.id) == Decimal("800.00")
    assert dashboard["loan_receivables"] == Decimal("200.00")
    assert dashboard["total_assets"] == Decimal("1000.00")
    assert dashboard["net_worth"] == Decimal("1000.00")


def test_repayments_reduce_outstanding_and_preserve_net_worth(services):
    db, accounts, loans = services
    current = accounts.create_account("Current", "current_account", opening_balance="1000")
    borrowed = loans.create_loan(
        "borrowed", "Car loan", "Bank", current.id, "500", "2026-07-01"
    )
    lent = loans.create_loan(
        "lent", "Personal loan", "Sam", current.id, "200", "2026-07-02"
    )

    borrowed_after = loans.record_payment(
        borrowed.loan.id, current.id, "100", "2026-07-15"
    )
    lent_after = loans.record_payment(lent.loan.id, current.id, "50", "2026-07-15")
    dashboard = DashboardService(db).global_snapshot()

    assert borrowed_after.outstanding == Decimal("400.00")
    assert lent_after.outstanding == Decimal("150.00")
    assert accounts.account_balance(current.id) == Decimal("1250.00")
    assert dashboard["borrowed_loans"] == Decimal("400.00")
    assert dashboard["loan_receivables"] == Decimal("150.00")
    assert dashboard["net_worth"] == Decimal("1000.00")


def test_full_repayment_settles_loan_and_rejects_overpayment(services):
    _db, accounts, loans = services
    current = accounts.create_account("Current", "current_account", opening_balance="1000")
    created = loans.create_loan(
        "borrowed", "Short loan", "Bank", current.id, "100", "2026-07-01"
    )

    with pytest.raises(ValueError, match="outstanding"):
        loans.record_payment(created.loan.id, current.id, "101", "2026-07-15")

    settled = loans.record_payment(created.loan.id, current.id, "100", "2026-07-15")
    assert settled.outstanding == Decimal("0.00")
    assert settled.loan.status == "settled"
    assert loans.summary()["active_count"] == 0


def test_loan_generated_transactions_are_changed_from_loans_page(services):
    _db, accounts, loans = services
    current = accounts.create_account("Current", "current_account", opening_balance="1000")
    created = loans.create_loan(
        "borrowed", "Car loan", "Bank", current.id, "100", "2026-07-01"
    )
    transaction = loans.transactions.list_transactions(loan_id=created.loan.id)[0]

    with pytest.raises(ValueError, match="Loans page"):
        loans.transactions.delete_transaction(transaction.id)


def test_existing_v5_database_upgrades_to_loan_schema(tmp_path, monkeypatch):
    source = tmp_path / "version-5.db"
    legacy = sqlite3.connect(source)
    legacy.row_factory = sqlite3.Row
    legacy.execute("PRAGMA foreign_keys = ON")
    _run_migration(legacy, 1, _create_initial_schema)
    _run_migration(legacy, 2, _migrate_v2)
    legacy.execute("PRAGMA foreign_keys = OFF")
    _run_migration(legacy, 3, _migrate_v3)
    legacy.execute("PRAGMA foreign_keys = ON")
    _run_migration(legacy, 4, _migrate_v4)
    _run_migration(legacy, 5, _migrate_v5)
    legacy.close()

    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path / "app-data"))
    upgraded = connect(source)
    try:
        assert upgraded.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        tables = {
            row["name"]
            for row in upgraded.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {"loans", "loan_payments"} <= tables
        transaction_columns = {
            row["name"] for row in upgraded.execute("PRAGMA table_info(transactions)")
        }
        assert "loan_id" in transaction_columns
    finally:
        upgraded.close()
