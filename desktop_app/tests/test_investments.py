from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

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
from app.models.investment import Investment
from app.repositories.investment_repository import InvestmentRepository
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
    visible_activity = investments.transactions.list_transactions(
        investment_id=snapshot.investment.id,
        exclude_investment_adjustments=True,
    )
    assert sorted(item.type for item in visible_activity) == [
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

    history = investments.value_history(created.investment.id)
    assert [(point.date, point.value) for point in history] == [
        ("2026-07-01", Decimal("220.00")),
        ("2026-07-10", Decimal("270.00")),
        ("2026-07-15", Decimal("230.00")),
    ]


def test_partial_withdrawal_moves_cash_without_counting_it_as_a_loss(services):
    db, accounts, investments = services
    source = accounts.create_account(
        "Current",
        "current_account",
        opening_balance="1000",
    )
    destination = accounts.create_account("Savings", "savings_account")
    created = investments.create_investment(
        "Global index",
        "etf",
        source.id,
        "200",
        "2026-07-01",
        current_value="220",
    )
    net_worth_before = DashboardService(db).summary()["net_worth"]

    withdrawn = investments.withdraw_funds(
        created.investment.id,
        destination.id,
        "50",
        "2026-07-16",
    )

    assert withdrawn.current_value == Decimal("170.00")
    assert withdrawn.contributed == Decimal("150.00")
    assert withdrawn.gross_contributed == Decimal("200.00")
    assert withdrawn.gain_loss == Decimal("20.00")
    assert withdrawn.return_percent == Decimal("10.00")
    assert accounts.account_balance(destination.id) == Decimal("50.00")
    assert accounts.account_balance(withdrawn.investment.account_id) == Decimal(
        "170.00"
    )
    assert DashboardService(db).summary()["net_worth"] == net_worth_before
    history = investments.value_history(created.investment.id)
    assert (history[-1].contributed, history[-1].value) == (
        Decimal("150.00"),
        Decimal("170.00"),
    )


def test_partial_withdrawal_rejects_full_liquidation(services):
    _db, accounts, investments = services
    source = accounts.create_account("Current", "current_account", opening_balance="500")
    created = investments.create_investment(
        "Index",
        "etf",
        source.id,
        "100",
        "2026-07-01",
    )

    with pytest.raises(ValueError, match="use Delete to liquidate"):
        investments.withdraw_funds(
            created.investment.id,
            source.id,
            "100",
            "2026-07-16",
        )

    assert accounts.account_balance(source.id) == Decimal("400.00")
    assert investments.get_snapshot(created.investment.id).current_value == Decimal(
        "100.00"
    )
    assert len(investments.value_history(created.investment.id)) == 1


def test_value_history_preserves_every_same_day_update(services):
    _db, accounts, investments = services
    source = accounts.create_account("Current", "current_account", opening_balance="500")
    created = investments.create_investment(
        "Index", "etf", source.id, "100", "2026-07-01"
    )

    investments.update_value(created.investment.id, "100", "2026-07-15")
    investments.update_value(created.investment.id, "105", "2026-07-15")
    investments.add_funds(created.investment.id, source.id, "50", "2026-07-15")
    investments.update_value(created.investment.id, "148", "2026-07-15")

    history = investments.value_history(created.investment.id)
    assert [(point.date, point.contributed, point.value) for point in history] == [
        ("2026-07-01", Decimal("100.00"), Decimal("100.00")),
        ("2026-07-15", Decimal("100.00"), Decimal("100.00")),
        ("2026-07-15", Decimal("100.00"), Decimal("105.00")),
        ("2026-07-15", Decimal("150.00"), Decimal("155.00")),
        ("2026-07-15", Decimal("150.00"), Decimal("148.00")),
    ]
    assert len({point.id for point in history}) == 5

    updates = investments.performance_history(created.investment.id, "updates")
    assert [
        (point.contributed, point.current_value)
        for point in updates
    ] == [
        (Decimal("100.00"), Decimal("100.00")),
        (Decimal("100.00"), Decimal("100.00")),
        (Decimal("100.00"), Decimal("105.00")),
        (Decimal("150.00"), Decimal("155.00")),
        (Decimal("150.00"), Decimal("148.00")),
    ]


def test_portfolio_history_carries_each_investment_forward(services):
    _db, accounts, investments = services
    source = accounts.create_account("Current", "current_account", opening_balance="1000")
    first = investments.create_investment(
        "First", "etf", source.id, "100", "2026-07-01"
    )
    investments.create_investment(
        "Second", "fund", source.id, "200", "2026-07-10"
    )
    investments.update_value(first.investment.id, "150", "2026-07-15")

    assert [(point.date, point.value) for point in investments.portfolio_history()] == [
        ("2026-07-01", Decimal("100.00")),
        ("2026-07-10", Decimal("300.00")),
        ("2026-07-15", Decimal("350.00")),
    ]


def test_monthly_performance_compares_contributions_and_market_value(services):
    _db, accounts, investments = services
    source = accounts.create_account("Current", "current_account", opening_balance="1000")
    created = investments.create_investment(
        "Index",
        "etf",
        source.id,
        "100",
        "2026-01-05",
        current_value="110",
    )
    investments.add_funds(created.investment.id, source.id, "50", "2026-02-10")
    investments.update_value(created.investment.id, "140", "2026-03-15")

    history = investments.performance_history(
        created.investment.id,
        "monthly",
        date(2026, 3, 20),
    )

    assert [
        (point.date, point.contributed, point.current_value)
        for point in history
    ] == [
        ("2026-01-31", Decimal("100.00"), Decimal("110.00")),
        ("2026-02-28", Decimal("150.00"), Decimal("160.00")),
        ("2026-03-20", Decimal("150.00"), Decimal("140.00")),
    ]


def test_performance_views_keep_every_update_and_monthly_summary(services):
    _db, accounts, investments = services
    source = accounts.create_account("Current", "current_account", opening_balance="500")
    created = investments.create_investment(
        "Index", "etf", source.id, "100", "2026-01-01"
    )
    investments.update_value(created.investment.id, "120", "2026-01-29")

    updates = investments.performance_history(
        created.investment.id,
        "updates",
        date(2026, 1, 29),
    )
    monthly = investments.performance_history(
        created.investment.id,
        "monthly",
        date(2026, 1, 29),
    )

    assert len(updates) == 2
    assert updates[-1].current_value == Decimal("120.00")
    assert len(monthly) == 1
    assert monthly[-1].current_value == Decimal("120.00")
    with pytest.raises(ValueError, match="not supported"):
        investments.performance_history(created.investment.id, "weekly")


def test_editing_historical_value_does_not_change_current_balance(services):
    _db, accounts, investments = services
    source = accounts.create_account("Current", "current_account", opening_balance="500")
    created = investments.create_investment(
        "Index", "etf", source.id, "100", "2026-07-01"
    )
    investments.update_value(created.investment.id, "120", "2026-07-10")
    investments.update_value(created.investment.id, "130", "2026-07-15")
    history = investments.value_history(created.investment.id)

    investments.edit_value_update(created.investment.id, history[1].id, "110")

    assert [point.value for point in investments.value_history(created.investment.id)] == [
        Decimal("100.00"),
        Decimal("110.00"),
        Decimal("130.00"),
    ]
    assert accounts.account_balance(created.investment.account_id) == Decimal("130.00")


def test_editing_or_deleting_latest_value_reconciles_current_balance(services):
    _db, accounts, investments = services
    source = accounts.create_account("Current", "current_account", opening_balance="500")
    created = investments.create_investment(
        "Index", "etf", source.id, "100", "2026-07-01"
    )
    investments.update_value(created.investment.id, "120", "2026-07-10")
    investments.update_value(created.investment.id, "130", "2026-07-15")
    latest = investments.value_history(created.investment.id)[-1]

    investments.edit_value_update(created.investment.id, latest.id, "125")

    assert accounts.account_balance(created.investment.account_id) == Decimal("125.00")
    corrected = investments.value_history(created.investment.id)[-1]
    assert corrected.value == Decimal("125.00")

    investments.delete_value_update(created.investment.id, corrected.id)

    assert [point.value for point in investments.value_history(created.investment.id)] == [
        Decimal("100.00"),
        Decimal("120.00"),
    ]
    assert accounts.account_balance(created.investment.account_id) == Decimal("120.00")


def test_every_value_log_can_be_deleted(services):
    _db, accounts, investments = services
    source = accounts.create_account("Current", "current_account", opening_balance="500")
    created = investments.create_investment(
        "Index", "etf", source.id, "100", "2026-07-01"
    )
    investments.update_value(created.investment.id, "120", "2026-07-05")
    investments.add_funds(created.investment.id, source.id, "50", "2026-07-10")
    history = investments.value_history(created.investment.id)

    investments.delete_value_update(created.investment.id, history[-1].id)
    assert accounts.account_balance(created.investment.account_id) == Decimal("120.00")

    remaining = investments.value_history(created.investment.id)
    investments.delete_value_update(created.investment.id, remaining[-1].id)
    assert accounts.account_balance(created.investment.account_id) == Decimal("100.00")

    only_log = investments.value_history(created.investment.id)[0]
    investments.delete_value_update(created.investment.id, only_log.id)

    assert investments.value_history(created.investment.id) == []
    assert accounts.account_balance(created.investment.account_id) == Decimal("100.00")


def test_clearing_logs_unblocks_legacy_future_portfolio_deletion(services):
    _db, accounts, investments = services
    source = accounts.create_account("Current", "current_account", opening_balance="500")
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    created = investments.create_investment(
        "Index",
        "etf",
        source.id,
        "100",
        today,
    )
    investments.investments.record_value(
        created.investment.id,
        tomorrow,
        Decimal("100"),
    )
    balance_before = accounts.account_balance(created.investment.account_id)
    transactions_before = investments.transactions.list_transactions(
        investment_id=created.investment.id
    )

    with pytest.raises(ValueError, match="earlier than the latest"):
        investments.delete_investment(created.investment.id, today)

    assert investments.clear_value_logs(created.investment.id) == 2
    assert investments.value_history(created.investment.id) == []
    assert accounts.account_balance(created.investment.account_id) == balance_before
    assert investments.transactions.list_transactions(
        investment_id=created.investment.id
    ) == transactions_before

    investments.delete_investment(created.investment.id, today)

    assert accounts.account_balance(source.id) == Decimal("500.00")
    assert investments.list_snapshots() == []


def test_investment_changes_reject_future_dates(services):
    _db, accounts, investments = services
    source = accounts.create_account("Current", "current_account", opening_balance="500")
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    with pytest.raises(ValueError, match="cannot be in the future"):
        investments.create_investment("Future", "etf", source.id, "100", tomorrow)

    assert investments.list_snapshots() == []
    assert accounts.account_balance(source.id) == Decimal("500.00")

    created = investments.create_investment(
        "Index", "etf", source.id, "100", today
    )
    with pytest.raises(ValueError, match="cannot be in the future"):
        investments.update_value(created.investment.id, "110", tomorrow)
    with pytest.raises(ValueError, match="cannot be in the future"):
        investments.add_funds(created.investment.id, source.id, "25", tomorrow)

    assert len(investments.value_history(created.investment.id)) == 1
    assert accounts.account_balance(created.investment.account_id) == Decimal("100.00")


def test_investment_changes_reject_dates_before_latest_value(services):
    _db, accounts, investments = services
    source = accounts.create_account("Current", "current_account", opening_balance="500")
    created = investments.create_investment(
        "Index", "etf", source.id, "100", "2026-07-10"
    )

    with pytest.raises(ValueError, match="earlier than the latest"):
        investments.update_value(created.investment.id, "110", "2026-07-09")
    with pytest.raises(ValueError, match="earlier than the latest"):
        investments.add_funds(created.investment.id, source.id, "25", "2026-07-01")


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


def test_delete_investment_returns_current_value_to_original_account(services):
    db, accounts, investments = services
    source = accounts.create_account(
        "Current",
        "current_account",
        opening_balance="1000",
    )
    created = investments.create_investment(
        "Index",
        "etf",
        source.id,
        "200",
        "2026-07-01",
        current_value="220",
    )
    investment_id = created.investment.id
    managed_account_id = created.investment.account_id
    net_worth_before = DashboardService(db).summary()["net_worth"]

    plan = investments.liquidation_plan(investment_id)
    assert [(share.account_id, share.proceeds) for share in plan] == [
        (source.id, Decimal("220.00")),
    ]

    investments.delete_investment(investment_id, "2026-07-16")

    assert investments.list_snapshots() == []
    assert accounts.account_balance(source.id) == Decimal("1020.00")
    assert accounts.account_balance(managed_account_id) == Decimal("0.00")
    assert accounts.accounts.get(managed_account_id).is_active is False
    assert DashboardService(db).summary()["net_worth"] == net_worth_before
    final_value = db.execute(
        """
        SELECT value_cents, contributed_cents
        FROM investment_value_history
        WHERE investment_id = ?
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (investment_id,),
    ).fetchone()
    assert final_value["value_cents"] == 0
    assert final_value["contributed_cents"] == 20000


def test_delete_investment_splits_proceeds_across_funding_accounts(services):
    db, accounts, investments = services
    current = accounts.create_account(
        "Current",
        "current_account",
        opening_balance="1000",
    )
    savings = accounts.create_account(
        "Savings",
        "savings_account",
        opening_balance="1000",
    )
    created = investments.create_investment(
        "Index",
        "etf",
        current.id,
        "100",
        "2026-07-01",
    )
    investments.add_funds(
        created.investment.id,
        savings.id,
        "300",
        "2026-07-10",
    )
    investments.update_value(created.investment.id, "500", "2026-07-15")
    net_worth_before = DashboardService(db).summary()["net_worth"]

    plan = {
        share.account_id: share.proceeds
        for share in investments.liquidation_plan(created.investment.id)
    }
    assert plan == {
        current.id: Decimal("125.00"),
        savings.id: Decimal("375.00"),
    }

    investments.delete_investment(created.investment.id, "2026-07-16")

    assert accounts.account_balance(current.id) == Decimal("1025.00")
    assert accounts.account_balance(savings.id) == Decimal("1075.00")
    assert DashboardService(db).summary()["net_worth"] == net_worth_before


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
        assert upgraded.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'investment_value_history'
            """
        ).fetchone()
        transaction_columns = {
            row["name"] for row in upgraded.execute("PRAGMA table_info(transactions)")
        }
        assert "investment_id" in transaction_columns
        history_columns = {
            row["name"]
            for row in upgraded.execute("PRAGMA table_info(investment_value_history)")
        }
        assert "contributed_cents" in history_columns
    finally:
        upgraded.close()


def test_existing_investment_ledger_is_backfilled_into_value_history(
    tmp_path,
    monkeypatch,
):
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

    accounts = AccountService(legacy)
    current = accounts.create_account(
        "Current",
        "current_account",
        opening_balance="500",
    )
    investment_account = accounts.create_account("Index", "investment")
    investment = InvestmentRepository(legacy).create(
        Investment(None, "Index", "etf", investment_account.id)
    )
    legacy.execute(
        """
        INSERT INTO transactions (
            id, date, type, account_id, amount_cents, description,
            transfer_group_id, investment_id, status
        ) VALUES (?, ?, 'transfer_in', ?, 10000, ?, ?, ?, 'cleared')
        """,
        (
            str(uuid4()),
            "2026-07-01",
            investment_account.id,
            "Invest in Index",
            str(uuid4()),
            investment.id,
        ),
    )
    legacy.commit()
    legacy.close()

    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path / "app-data"))
    upgraded = connect(source)
    try:
        history = InvestmentService(upgraded).value_history(investment.id)
        assert [(point.date, point.value) for point in history] == [
            ("2026-07-01", Decimal("100.00")),
        ]
        assert history[0].contributed == Decimal("100.00")
    finally:
        upgraded.close()
