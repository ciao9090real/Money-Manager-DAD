from __future__ import annotations

import sqlite3
from datetime import date
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
    _migrate_v6,
    _run_migration,
)
from app.services.account_service import AccountService
from app.services.category_service import CategoryService
from app.services.recurring_service import RecurringService


@pytest.fixture()
def services(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        yield db, AccountService(db), RecurringService(db)
    finally:
        db.close()


def test_fixed_payment_records_expense_and_keeps_month_end_anchor(services):
    db, accounts, recurring = services
    account = accounts.create_account("Current", "current_account", opening_balance="100")
    category = CategoryService(db).create_category("Subscriptions", "expense")
    rule = recurring.create_rule(
        "Cloud storage",
        "subscription",
        "fixed",
        account.id,
        "monthly",
        "2027-01-31",
        amount="25",
        category_id=category.id,
    )

    transaction = recurring.record_payment(rule.id, transaction_date="2027-01-30")

    assert transaction.amount == Decimal("-25.00")
    assert transaction.recurring_rule_id == rule.id
    assert accounts.account_balance(account.id) == Decimal("75.00")
    advanced = recurring.get_rule(rule.id)
    assert advanced.next_due_date == "2027-02-28"
    assert advanced.last_recorded_date == "2027-01-30"

    recurring.record_payment(rule.id, transaction_date="2027-02-28")
    assert recurring.get_rule(rule.id).next_due_date == "2027-03-31"


def test_variable_bill_requires_confirmed_amount_before_posting(services):
    _db, accounts, recurring = services
    account = accounts.create_account("Current", "current_account", opening_balance="200")
    rule = recurring.create_rule(
        "Electricity",
        "bill",
        "variable",
        account.id,
        "monthly",
        "2027-02-10",
        amount="80",
    )

    with pytest.raises(ValueError, match="Actual amount"):
        recurring.record_payment(rule.id)

    assert recurring.get_rule(rule.id).next_due_date == "2027-02-10"
    assert recurring.transactions.list_transactions() == []

    transaction = recurring.record_payment(
        rule.id, actual_amount="92.30", transaction_date="2027-02-09"
    )
    assert transaction.amount == Decimal("-92.30")
    assert accounts.account_balance(account.id) == Decimal("107.70")
    assert recurring.get_rule(rule.id).amount == Decimal("80.00")


def test_recording_rolls_back_transaction_if_schedule_update_fails(services, monkeypatch):
    _db, accounts, recurring = services
    account = accounts.create_account("Current", "current_account", opening_balance="100")
    rule = recurring.create_rule(
        "Membership",
        "subscription",
        "fixed",
        account.id,
        "monthly",
        "2027-02-10",
        amount="15",
    )

    def fail_update(_rule):
        raise RuntimeError("schedule update failed")

    monkeypatch.setattr(recurring.rules, "update", fail_update)
    with pytest.raises(RuntimeError, match="schedule update failed"):
        recurring.record_payment(rule.id, transaction_date="2027-02-10")

    assert recurring.transactions.list_transactions() == []
    assert accounts.account_balance(account.id) == Decimal("100.00")
    assert recurring.get_rule(rule.id).next_due_date == "2027-02-10"


def test_pause_skip_completion_and_summary(services):
    _db, accounts, recurring = services
    account = accounts.create_account("Current", "current_account")
    rule = recurring.create_rule(
        "Short plan",
        "other",
        "fixed",
        account.id,
        "weekly",
        "2027-01-01",
        amount="10",
        end_date="2027-01-08",
    )

    recurring.set_paused(rule.id, True)
    with pytest.raises(ValueError, match="not active"):
        recurring.record_payment(rule.id)
    recurring.set_paused(rule.id, False)

    first_skip = recurring.skip_occurrence(rule.id)
    assert first_skip.next_due_date == "2027-01-08"
    assert first_skip.status == "active"
    second_skip = recurring.skip_occurrence(rule.id)
    assert second_skip.next_due_date == "2027-01-15"
    assert second_skip.status == "completed"

    recurring.create_rule(
        "Overdue bill",
        "bill",
        "variable",
        account.id,
        "monthly",
        "2027-01-05",
    )
    recurring.create_rule(
        "Upcoming subscription",
        "subscription",
        "fixed",
        account.id,
        "monthly",
        "2027-01-20",
        amount="12.50",
    )
    summary = recurring.summary(date(2027, 1, 10))
    assert summary == {
        "overdue_count": 1,
        "due_soon_count": 1,
        "expected_30_days": Decimal("12.50"),
        "expected_income_30_days": Decimal("0"),
        "expected_outgoings_30_days": Decimal("12.50"),
        "variable_count": 1,
    }


def test_recurring_wage_records_income(services):
    db, accounts, recurring = services
    account = accounts.create_account("Current", "current_account", opening_balance="100")
    category = CategoryService(db).create_category("Salary", "income")
    wage = recurring.create_rule(
        "Monthly wage",
        "other",
        "fixed",
        account.id,
        "monthly",
        "2027-02-01",
        amount="2000",
        category_id=category.id,
        transaction_type="income",
    )

    transaction = recurring.record_payment(wage.id, transaction_date="2027-02-01")

    assert transaction.type == "income"
    assert transaction.amount == Decimal("2000.00")
    assert accounts.account_balance(account.id) == Decimal("2100.00")
    assert recurring.get_rule(wage.id).next_due_date == "2027-03-01"


def test_recurring_rules_are_revisioned_and_soft_deleted(services):
    db, accounts, recurring = services
    account = accounts.create_account("Current", "current_account")
    rule = recurring.create_rule(
        "Membership",
        "subscription",
        "fixed",
        account.id,
        "yearly",
        "2027-04-01",
        amount="50",
    )

    recurring.delete_rule(rule.id)

    assert recurring.get_rule(rule.id) is None
    tombstone = db.execute(
        "SELECT revision FROM tombstones WHERE entity_type = 'recurring_rules' AND entity_id = ?",
        (rule.id,),
    ).fetchone()
    assert tombstone["revision"] == 2
    operations = db.execute(
        """
        SELECT operation FROM change_log
        WHERE entity_type = 'recurring_rules' AND entity_id = ?
        ORDER BY revision
        """,
        (rule.id,),
    ).fetchall()
    assert [row["operation"] for row in operations] == ["insert", "delete"]
    with pytest.raises(sqlite3.IntegrityError, match="hard delete"):
        db.execute("DELETE FROM recurring_rules WHERE id = ?", (rule.id,))


def test_existing_v3_database_upgrades_to_recurring_schema(tmp_path, monkeypatch):
    source = tmp_path / "version-3.db"
    legacy = sqlite3.connect(source)
    legacy.row_factory = sqlite3.Row
    legacy.execute("PRAGMA foreign_keys = ON")
    _run_migration(legacy, 1, _create_initial_schema)
    _run_migration(legacy, 2, _migrate_v2)
    legacy.execute("PRAGMA foreign_keys = OFF")
    _run_migration(legacy, 3, _migrate_v3)
    legacy.execute("PRAGMA foreign_keys = ON")
    legacy.close()

    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path / "app-data"))
    upgraded = connect(source)
    try:
        assert upgraded.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert upgraded.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'recurring_rules'"
        ).fetchone()
        transaction_columns = {
            row["name"] for row in upgraded.execute("PRAGMA table_info(transactions)")
        }
        assert "recurring_rule_id" in transaction_columns
    finally:
        upgraded.close()


def test_existing_v6_recurring_rules_default_to_expense(tmp_path, monkeypatch):
    source = tmp_path / "version-6.db"
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
    _run_migration(legacy, 6, _migrate_v6)
    account_id = str(uuid4())
    rule_id = str(uuid4())
    legacy.execute(
        "INSERT INTO accounts (id, name, type) VALUES (?, 'Current', 'current_account')",
        (account_id,),
    )
    legacy.execute(
        """
        INSERT INTO recurring_rules (
            id, name, kind, amount_mode, amount_cents, account_id,
            frequency, start_date, next_due_date
        ) VALUES (?, 'Existing bill', 'bill', 'fixed', 2500, ?, 'monthly',
                  '2027-01-01', '2027-02-01')
        """,
        (rule_id, account_id),
    )
    legacy.commit()
    legacy.close()

    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path / "app-data"))
    upgraded = connect(source)
    try:
        assert upgraded.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        row = upgraded.execute(
            "SELECT transaction_type FROM recurring_rules WHERE id = ?", (rule_id,)
        ).fetchone()
        assert row["transaction_type"] == "expense"
    finally:
        upgraded.close()
