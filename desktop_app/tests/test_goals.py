from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.core.database import connect, unit_of_work
from app.services.account_service import AccountService
from app.services.dashboard_service import DashboardService
from app.services.goal_service import GoalService
from app.services.transaction_service import TransactionService


@pytest.fixture()
def services(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        yield db, AccountService(db), TransactionService(db), GoalService(db)
    finally:
        db.close()


def test_goal_crud_activation_and_soft_delete(services):
    db, accounts, _transactions, goals = services
    savings = accounts.create_account("Savings", "savings_account")
    created = goals.create_goal(
        "Emergency fund",
        "5000",
        "2027-01-31",
        savings.id,
    )

    updated = goals.update_goal(
        created.id,
        "Emergency reserve",
        "6000",
        "2027-03-31",
        savings.id,
    )
    inactive = goals.set_active(created.id, False)

    assert updated.name == "Emergency reserve"
    assert updated.target_amount == Decimal("6000.00")
    assert not inactive.is_active
    assert goals.list_goals() == []
    assert goals.list_goals(include_inactive=True)[0].id == created.id

    goals.delete_goal(created.id)
    assert goals.list_goals(include_inactive=True) == []
    row = db.execute(
        "SELECT deleted_at, revision FROM savings_goals WHERE id = ?",
        (created.id,),
    ).fetchone()
    assert row["deleted_at"] is not None
    assert row["revision"] == 4
    changes = db.execute(
        """
        SELECT operation, revision FROM change_log
        WHERE entity_type = 'savings_goals' AND entity_id = ?
        ORDER BY sequence
        """,
        (created.id,),
    ).fetchall()
    assert [(change["operation"], change["revision"]) for change in changes] == [
        ("insert", 1),
        ("update", 2),
        ("update", 3),
        ("delete", 4),
    ]
    assert db.execute(
        "SELECT 1 FROM tombstones WHERE entity_type = 'savings_goals' AND entity_id = ?",
        (created.id,),
    ).fetchone()
    with pytest.raises(sqlite3.IntegrityError, match="hard delete"):
        with unit_of_work(db):
            db.execute("DELETE FROM savings_goals WHERE id = ?", (created.id,))


def test_linked_goal_uses_nonnegative_account_balance_and_monthly_requirement(services):
    _db, accounts, _transactions, goals = services
    savings = accounts.create_account(
        "Savings",
        "savings_account",
        opening_balance="250",
    )
    goal = goals.create_goal(
        "Deposit",
        "1000",
        "2026-12-20",
        savings.id,
    )

    progress = goals.progress(goal.id, date(2026, 7, 20))

    assert progress.current_amount == Decimal("250.00")
    assert progress.percent_complete == Decimal("25.00")
    assert progress.required_monthly_contribution == Decimal("150.00")
    assert progress.on_track

    overdrawn = accounts.create_account(
        "Overdrawn savings",
        "savings_account",
        opening_balance="-50",
    )
    negative_goal = goals.create_goal("Buffer", "500", linked_account_id=overdrawn.id)
    assert goals.progress(negative_goal.id).current_amount == Decimal("0")


def test_manual_goal_counts_only_tagged_incoming_transfers_up_to_reference(services):
    db, accounts, transactions, goals = services
    current = accounts.create_account(
        "Current",
        "current_account",
        opening_balance="1000",
    )
    savings = accounts.create_account("Savings", "savings_account")
    other = accounts.create_account("Other", "savings_account")
    goal = goals.create_goal("Holiday", "500", "2026-12-31")

    goals.add_contribution(
        goal.id,
        current.id,
        savings.id,
        "100",
        "2026-07-10",
    )
    goals.add_contribution(
        goal.id,
        current.id,
        savings.id,
        "100",
        "2026-08-10",
    )
    transactions.add_transfer(current.id, other.id, "50", "2026-07-12", "Other")

    progress = goals.progress(goal.id, date(2026, 7, 20))
    tagged = db.execute(
        """
        SELECT type, savings_goal_id FROM transactions
        WHERE savings_goal_id = ? ORDER BY type
        """,
        (goal.id,),
    ).fetchall()

    assert progress.current_amount == Decimal("100.00")
    assert progress.percent_complete == Decimal("20.00")
    assert sum(
        (
            accounts.account_balance(current.id),
            accounts.account_balance(savings.id),
            accounts.account_balance(other.id),
        ),
        Decimal("0"),
    ) == Decimal("1000.00")
    assert [(row["type"], row["savings_goal_id"]) for row in tagged] == [
        ("transfer_in", goal.id),
        ("transfer_in", goal.id),
        ("transfer_out", goal.id),
        ("transfer_out", goal.id),
    ]
    goal_transaction = transactions.list_transactions(savings_goal_id=goal.id)[0]
    with pytest.raises(ValueError, match="Savings Goals page"):
        transactions.delete_transaction(goal_transaction.id)


def test_on_track_uses_linear_pace_from_creation_to_deadline(services):
    _db, accounts, _transactions, goals = services
    current = accounts.create_account(
        "Current",
        "current_account",
        opening_balance="1000",
    )
    savings = accounts.create_account("Savings", "savings_account")
    created = goals.create_goal("Course", "100")
    created_date = date.fromisoformat(created.created_at[:10])
    target = created_date + timedelta(days=100)
    goal = goals.update_goal(created.id, "Course", "100", target.isoformat())
    reference = created_date + timedelta(days=50)

    goals.add_contribution(
        goal.id,
        current.id,
        savings.id,
        "40",
        (created_date + timedelta(days=10)).isoformat(),
    )
    assert not goals.progress(goal.id, reference).on_track

    goals.add_contribution(
        goal.id,
        current.id,
        savings.id,
        "20",
        (created_date + timedelta(days=20)).isoformat(),
    )
    assert goals.progress(goal.id, reference).on_track


def test_goal_validation_and_progress_listing(services):
    _db, accounts, _transactions, goals = services
    current = accounts.create_account("Current", "current_account", opening_balance="100")
    savings = accounts.create_account("Savings", "savings_account")

    with pytest.raises(ValueError, match="positive"):
        goals.create_goal("Invalid", "0")
    with pytest.raises(ValueError, match="unavailable"):
        goals.create_goal("Invalid link", "100", linked_account_id="missing")

    manual = goals.create_goal("Manual", "100")
    linked = goals.create_goal("Linked", "100", linked_account_id=savings.id)
    with pytest.raises(ValueError, match="do not use manual"):
        goals.add_contribution(
            linked.id,
            current.id,
            savings.id,
            "10",
            date.today().isoformat(),
        )

    assert [item.goal.id for item in goals.list_progress()] == [linked.id, manual.id]


def test_dashboard_prioritizes_nearest_dated_goals(services):
    db, _accounts, _transactions, goals = services
    later = goals.create_goal("Later", "1000", "2027-06-30")
    undated = goals.create_goal("Someday", "1000")
    sooner = goals.create_goal("Sooner", "1000", "2026-12-31")

    highlights = DashboardService(db).goal_highlights(date(2026, 7, 20))

    assert [item.goal.id for item in highlights] == [sooner.id, later.id, undated.id]
