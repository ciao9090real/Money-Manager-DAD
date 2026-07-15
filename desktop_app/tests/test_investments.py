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
    _run_migration,
)
from app.services.account_service import AccountService
from app.services.dashboard_service import DashboardService
from app.services.investment_service import InvestmentService


@pytest.fixture()
def services(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        yield db, AccountService(db), InvestmentService(db)
    finally:
        db.close()


def test_create_investment_uses_transfer_and_market_value_adjustment(services):
    db, accounts, investments = services
    source = accounts.create_account("Current", "current_account", opening_balance="1000")

    snapshot = investments.create_investment(
        "Global index",
        "etf",
        source.id,
        "200",
        "2026-07-15",
        current_value="220",
        symbol="vwce",
    )

    assert snapshot.investment.symbol == "VWCE"
    assert snapshot.contributed == Decimal("200.00")
    assert snapshot.current_value == Decimal("220.00")
    assert snapshot.gain_loss == Decimal("20.00")
    assert snapshot.return_percent == Decimal("10.00")
    assert accounts.account_balance(source.id) == Decimal("800.00")
    assert accounts.account_balance(snapshot.investment.account_id) == Decimal("220.00")
    linked = investments.transactions.list_transactions(
        investment_id=snapshot.investment.id
    )
    assert sorted(item.type for item in linked) == [
        "adjustment",
        "transfer_in",
        "transfer_out",
    ]

    dashboard = DashboardService(db).summary()
    assert dashboard["liquidity"] == Decimal("800.00")
    assert dashboard["investments_property"] == Decimal("220.00")
    assert dashboard["net_worth"] == Decimal("1020.00")


def test_add_funds_and_update_value_calculate_performance(services):
    _db, accounts, investments = services
    source = accounts.create_account("Current", "current_account", opening_balance="1000")
    created = investments.create_investment(
        "Managed fund", "fund", source.id, "200", "2026-07-01", current_value="220"
    )

    funded = investments.add_funds(created.investment.id, source.id, "50", "2026-07-10")
    assert funded.contributed == Decimal("250.00")
    assert funded.current_value == Decimal("270.00")
    assert funded.gain_loss == Decimal("20.00")
    assert funded.return_percent == Decimal("8.00")

    valued = investments.update_value(created.investment.id, "230", "2026-07-15")
    assert valued.current_value == Decimal("230.00")
    assert valued.gain_loss == Decimal("-20.00")
    assert valued.return_percent == Decimal("-8.00")
    assert accounts.account_balance(source.id) == Decimal("750.00")


def test_investment_creation_rolls_back_if_transfer_is_incomplete(services, monkeypatch):
    _db, accounts, investments = services
    source = accounts.create_account("Current", "current_account", opening_balance="500")
    original_create = investments.transactions.transactions.create
    calls = 0

    def fail_second_create(transaction):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise sqlite3.IntegrityError("simulated investment transfer failure")
        return original_create(transaction)

    monkeypatch.setattr(investments.transactions.transactions, "create", fail_second_create)
    with pytest.raises(sqlite3.IntegrityError, match="investment transfer"):
        investments.create_investment(
            "Index", "etf", source.id, "100", "2026-07-15"
        )

    assert investments.list_snapshots() == []
    assert investments.transactions.list_transactions() == []
    assert [account.name for account in accounts.list_accounts()] == ["Current"]
    assert accounts.account_balance(source.id) == Decimal("500.00")


def test_investment_generated_transactions_are_changed_from_investments(services):
    _db, accounts, investments = services
    source = accounts.create_account("Current", "current_account", opening_balance="500")
    snapshot = investments.create_investment(
        "Index", "etf", source.id, "100", "2026-07-15"
    )
    transaction = investments.transactions.list_transactions(
        investment_id=snapshot.investment.id
    )[0]

    with pytest.raises(ValueError, match="Investments page"):
        investments.transactions.delete_transaction(transaction.id)


def test_existing_v4_database_upgrades_to_investment_schema(tmp_path, monkeypatch):
    source = tmp_path / "version-4.db"
    legacy = sqlite3.connect(source)
    legacy.row_factory = sqlite3.Row
    legacy.execute("PRAGMA foreign_keys = ON")
    _run_migration(legacy, 1, _create_initial_schema)
    _run_migration(legacy, 2, _migrate_v2)
    legacy.execute("PRAGMA foreign_keys = OFF")
    _run_migration(legacy, 3, _migrate_v3)
    legacy.execute("PRAGMA foreign_keys = ON")
    _run_migration(legacy, 4, _migrate_v4)
    legacy.close()

    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path / "app-data"))
    upgraded = connect(source)
    try:
        assert upgraded.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert upgraded.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'investments'"
        ).fetchone()
        transaction_columns = {
            row["name"] for row in upgraded.execute("PRAGMA table_info(transactions)")
        }
        assert "investment_id" in transaction_columns
    finally:
        upgraded.close()
