from __future__ import annotations

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
        yield AccountService(db), TransactionService(db), DashboardService(db)
    finally:
        db.close()


def test_adding_income(services):
    accounts, transactions, _dashboard = services
    account = accounts.create_account("Current", "current_account", opening_balance="100")

    transactions.add_income(account.id, "25", "2026-07-10", "Salary")

    assert accounts.account_balance(account.id) == Decimal("125.00")


def test_adding_expense(services):
    accounts, transactions, _dashboard = services
    account = accounts.create_account("Current", "current_account", opening_balance="100")

    transactions.add_expense(account.id, "25", "2026-07-10", "Groceries")

    assert accounts.account_balance(account.id) == Decimal("75.00")


def test_adding_transfer(services):
    accounts, transactions, _dashboard = services
    source = accounts.create_account("Current", "current_account", opening_balance="100")
    target = accounts.create_account("Savings", "savings_account", opening_balance="50")

    outgoing, incoming = transactions.add_transfer(source.id, target.id, "30", "2026-07-10")

    assert outgoing.transfer_group_id == incoming.transfer_group_id
    assert outgoing.type == "transfer_out"
    assert incoming.type == "transfer_in"
    assert accounts.account_balance(source.id) == Decimal("70.00")
    assert accounts.account_balance(target.id) == Decimal("80.00")


def test_transfer_does_not_change_net_worth(services):
    accounts, transactions, dashboard = services
    source = accounts.create_account("Current", "current_account", opening_balance="100")
    target = accounts.create_account("Savings", "savings_account", opening_balance="50")
    before = dashboard.summary()["net_worth"]

    transactions.add_transfer(source.id, target.id, "30", "2026-07-10")

    assert dashboard.summary()["net_worth"] == before


def test_transfer_rejects_same_account(services):
    accounts, transactions, _dashboard = services
    account = accounts.create_account("Current", "current_account")

    with pytest.raises(ValueError, match="different"):
        transactions.add_transfer(account.id, account.id, "30", "2026-07-10")

