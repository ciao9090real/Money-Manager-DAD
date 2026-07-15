from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.database import connect
from app.services.category_service import CategoryService
from app.services.account_service import AccountService
from app.services.dashboard_service import DashboardService
from app.services.transaction_service import TransactionService
from app.ui.transaction_table_model import TransactionTableModel


@pytest.fixture()
def services(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        yield AccountService(db), TransactionService(db), DashboardService(db), CategoryService(db)
    finally:
        db.close()


def test_adding_income(services):
    accounts, transactions, _dashboard, _categories = services
    account = accounts.create_account("Current", "current_account", opening_balance="100")

    transactions.add_income(account.id, "25", "2026-07-10", "Salary")

    assert accounts.account_balance(account.id) == Decimal("125.00")


def test_adding_expense(services):
    accounts, transactions, _dashboard, _categories = services
    account = accounts.create_account("Current", "current_account", opening_balance="100")

    transactions.add_expense(account.id, "25", "2026-07-10", "Groceries")

    assert accounts.account_balance(account.id) == Decimal("75.00")


def test_adding_transfer(services):
    accounts, transactions, _dashboard, _categories = services
    source = accounts.create_account("Current", "current_account", opening_balance="100")
    target = accounts.create_account("Savings", "savings_account", opening_balance="50")

    outgoing, incoming = transactions.add_transfer(source.id, target.id, "30", "2026-07-10")

    assert outgoing.transfer_group_id == incoming.transfer_group_id
    assert outgoing.type == "transfer_out"
    assert incoming.type == "transfer_in"
    assert accounts.account_balance(source.id) == Decimal("70.00")
    assert accounts.account_balance(target.id) == Decimal("80.00")


def test_transaction_table_groups_transfer_pair_into_one_row(services):
    accounts, transactions, _dashboard, _categories = services
    source = accounts.create_account("Current", "current_account", opening_balance="100")
    target = accounts.create_account("Savings", "savings_account")
    transactions.add_transfer(
        source.id,
        target.id,
        "30",
        "2026-07-10",
        "Monthly savings",
    )
    model = TransactionTableModel()
    model.replace(
        transactions.list_transactions(),
        {source.id: source.name, target.id: target.name},
        {},
    )

    assert model.rowCount() == 1
    assert model.data(model.index(0, 1)) == "Transfer"
    assert model.data(model.index(0, 2)) == "Current → Savings"
    assert model.transaction_at(0).type == "transfer_out"


def test_transfer_does_not_change_net_worth(services):
    accounts, transactions, dashboard, _categories = services
    source = accounts.create_account("Current", "current_account", opening_balance="100")
    target = accounts.create_account("Savings", "savings_account", opening_balance="50")
    before = dashboard.summary()["net_worth"]

    transactions.add_transfer(source.id, target.id, "30", "2026-07-10")

    assert dashboard.summary()["net_worth"] == before


def test_transfer_rejects_same_account(services):
    accounts, transactions, _dashboard, _categories = services
    account = accounts.create_account("Current", "current_account")

    with pytest.raises(ValueError, match="different"):
        transactions.add_transfer(account.id, account.id, "30", "2026-07-10")


def test_updating_income_updates_balance_and_category(services):
    accounts, transactions, _dashboard, categories = services
    account = accounts.create_account("Current", "current_account", opening_balance="100")
    category = categories.create_category("Salary", "income")
    transaction = transactions.add_income(account.id, "25", "2026-07-10", "Initial")

    updated = transactions.update_transaction(
        transaction.id,
        "income",
        account.id,
        "40",
        "2026-07-11",
        "Updated",
        category_id=category.id,
    )

    assert accounts.account_balance(account.id) == Decimal("140.00")
    assert updated.category_id == category.id
    assert updated.description == "Updated"


def test_deleting_expense_restores_balance(services):
    accounts, transactions, _dashboard, _categories = services
    account = accounts.create_account("Current", "current_account", opening_balance="100")
    transaction = transactions.add_expense(account.id, "25", "2026-07-10", "Groceries")

    transactions.delete_transaction(transaction.id)

    assert accounts.account_balance(account.id) == Decimal("100.00")
    assert transactions.list_transactions() == []


def test_updating_transfer_updates_both_sides_and_keeps_net_worth(services):
    accounts, transactions, dashboard, _categories = services
    source = accounts.create_account("Current", "current_account", opening_balance="100")
    target = accounts.create_account("Savings", "savings_account", opening_balance="50")
    outgoing, _incoming = transactions.add_transfer(source.id, target.id, "30", "2026-07-10")
    before = dashboard.summary()["net_worth"]

    updated_outgoing, updated_incoming = transactions.update_transaction(
        outgoing.id,
        "transfer",
        source.id,
        "45",
        "2026-07-11",
        "Moved",
        target_account_id=target.id,
    )

    assert updated_outgoing.transfer_group_id == updated_incoming.transfer_group_id
    assert accounts.account_balance(source.id) == Decimal("55.00")
    assert accounts.account_balance(target.id) == Decimal("95.00")
    assert dashboard.summary()["net_worth"] == before


def test_deleting_transfer_deletes_both_sides(services):
    accounts, transactions, _dashboard, _categories = services
    source = accounts.create_account("Current", "current_account", opening_balance="100")
    target = accounts.create_account("Savings", "savings_account", opening_balance="50")
    outgoing, _incoming = transactions.add_transfer(source.id, target.id, "30", "2026-07-10")

    transactions.delete_transaction(outgoing.id)

    assert accounts.account_balance(source.id) == Decimal("100.00")
    assert accounts.account_balance(target.id) == Decimal("50.00")
    assert transactions.list_transactions() == []
