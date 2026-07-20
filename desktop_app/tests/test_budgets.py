from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

import pytest

from app.core.database import connect, unit_of_work
from app.repositories.budget_repository import BudgetRepository
from app.services.account_service import AccountService
from app.services.budget_service import BudgetService
from app.services.category_service import CategoryService
from app.services.transaction_service import TransactionService


@pytest.fixture()
def services(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        yield (
            db,
            AccountService(db),
            CategoryService(db),
            TransactionService(db),
            BudgetService(db),
        )
    finally:
        db.close()


def test_budget_crud_uses_cents_revisions_and_change_log(services):
    db, _accounts, categories, _transactions, service = services
    category = categories.create_category("Groceries", "expense")

    created = service.set_budget(
        category.id, "250.125", rollover=True, start_date="2026-07-01"
    )
    assert created.amount == Decimal("250.13")
    assert created.rollover is True
    assert BudgetRepository(db).get_by_category(category.id) == created
    assert db.execute(
        "SELECT amount_cents FROM budgets WHERE id = ?", (created.id,)
    ).fetchone()[0] == 25_013

    updated = service.set_budget(
        category.id, "300", rollover=False, start_date="2026-07-01"
    )
    assert updated.id == created.id
    assert updated.revision == 2
    assert updated.amount == Decimal("300.00")
    operations = db.execute(
        "SELECT operation, revision FROM change_log WHERE entity_type = 'budgets' ORDER BY sequence"
    ).fetchall()
    assert [(row["operation"], row["revision"]) for row in operations] == [
        ("insert", 1),
        ("update", 2),
    ]

    service.delete_budget(created.id)
    assert BudgetRepository(db).get(created.id) is None
    tombstone = db.execute(
        "SELECT revision FROM tombstones WHERE entity_type = 'budgets' AND entity_id = ?",
        (created.id,),
    ).fetchone()
    assert tombstone["revision"] == 3
    with pytest.raises(sqlite3.IntegrityError, match="hard delete"):
        with unit_of_work(db):
            db.execute("DELETE FROM budgets WHERE id = ?", (created.id,))


def test_budget_status_across_month_boundary_and_overspend(services):
    _db, accounts, categories, transactions, budgets = services
    account = accounts.create_account("Current", "current_account", opening_balance="1000")
    groceries = categories.create_category("Groceries", "expense")
    dining = categories.create_category("Dining", "expense")
    budgets.set_budget(groceries.id, "100", start_date="2026-01-01")
    budgets.set_budget(dining.id, "50", start_date="2026-01-01")
    transactions.add_expense(
        account.id, "90", "2026-01-31", "Groceries", category_id=groceries.id
    )
    transactions.add_expense(
        account.id, "120", "2026-02-01", "Groceries", category_id=groceries.id
    )
    transactions.add_expense(
        account.id, "25", "2026-02-15", "Dining", category_id=dining.id
    )

    january = {s.budget.category_id: s for s in budgets.status_for_period(date(2026, 1, 15))}
    february = {s.budget.category_id: s for s in budgets.status_for_period(date(2026, 2, 15))}
    assert january[groceries.id].spent == Decimal("90.00")
    assert february[groceries.id].spent == Decimal("120.00")
    assert february[groceries.id].remaining == Decimal("-20.00")
    assert february[groceries.id].percent_used == Decimal("120.00")
    assert february[dining.id].percent_used == Decimal("50.00")
    assert [status.budget.category_id for status in budgets.overspent(date(2026, 2, 1))] == [
        groceries.id
    ]


def test_rollover_is_cumulative_and_does_not_carry_overspending(services):
    _db, accounts, categories, transactions, budgets = services
    account = accounts.create_account("Current", "current_account", opening_balance="1000")
    category = categories.create_category("Household", "expense")
    budgets.set_budget(category.id, "100", rollover=True, start_date="2026-01-15")
    transactions.add_expense(
        account.id, "80", "2026-01-10", "Before budget", category_id=category.id
    )
    transactions.add_expense(
        account.id, "40", "2026-01-20", "January", category_id=category.id
    )
    transactions.add_expense(
        account.id, "30", "2026-02-02", "February", category_id=category.id
    )

    march = budgets.status_for_period(date(2026, 3, 1))[0]
    assert march.rolled_over_from_prior == Decimal("130.00")
    assert march.limit == Decimal("230.00")
    assert march.spent == Decimal("0.00")

    transactions.add_expense(
        account.id, "250", "2026-03-02", "Overspend", category_id=category.id
    )
    april = budgets.status_for_period(date(2026, 4, 1))[0]
    assert april.rolled_over_from_prior == Decimal("0.00")
    assert april.limit == Decimal("100.00")


def test_budget_validation_and_future_start(services):
    _db, _accounts, categories, _transactions, budgets = services
    income = categories.create_category("Salary", "income")
    expense = categories.create_category("Travel", "expense")
    with pytest.raises(ValueError, match="expense categories"):
        budgets.set_budget(income.id, "100")
    with pytest.raises(ValueError, match="positive"):
        budgets.set_budget(expense.id, "0")
    budgets.set_budget(expense.id, "100", start_date="2026-08-01")
    assert budgets.status_for_period(date(2026, 7, 1)) == []
