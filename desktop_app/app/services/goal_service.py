from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, ROUND_UP

from app.core.database import unit_of_work
from app.models.goal import GoalProgress, SavingsGoal
from app.repositories.account_repository import AccountRepository
from app.repositories.goal_repository import GoalRepository
from app.services.transaction_service import TransactionService
from app.utils.dates import require_iso_date
from app.utils.money import CENT, require_positive
from app.utils.validators import require_text


class GoalService:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.goals = GoalRepository(db)
        self.accounts = AccountRepository(db)
        self.transactions = TransactionService(db)

    def create_goal(
        self,
        name: str,
        target_amount: object,
        target_date: str | None = None,
        linked_account_id: str | None = None,
        is_active: bool = True,
    ) -> SavingsGoal:
        with unit_of_work(self.db):
            self._validate_linked_account(linked_account_id)
            return self.goals.create(
                SavingsGoal(
                    id=None,
                    name=require_text(name, "Goal name"),
                    target_amount=require_positive(target_amount),
                    target_date=self._target_date(target_date),
                    linked_account_id=linked_account_id,
                    is_active=is_active,
                )
            )

    def update_goal(
        self,
        goal_id: str,
        name: str,
        target_amount: object,
        target_date: str | None = None,
        linked_account_id: str | None = None,
        is_active: bool = True,
    ) -> SavingsGoal:
        with unit_of_work(self.db):
            goal = self._goal(goal_id)
            self._validate_linked_account(linked_account_id)
            goal.name = require_text(name, "Goal name")
            goal.target_amount = require_positive(target_amount)
            goal.target_date = self._target_date(target_date)
            goal.linked_account_id = linked_account_id
            goal.is_active = bool(is_active)
            return self.goals.update(goal)

    def list_goals(self, include_inactive: bool = False) -> list[SavingsGoal]:
        return self.goals.list(include_inactive=include_inactive)

    def set_active(self, goal_id: str, is_active: bool) -> SavingsGoal:
        with unit_of_work(self.db):
            goal = self._goal(goal_id)
            goal.is_active = bool(is_active)
            return self.goals.update(goal)

    def delete_goal(self, goal_id: str) -> None:
        with unit_of_work(self.db):
            self._goal(goal_id)
            self.goals.delete(goal_id)

    def progress(
        self,
        goal_id: str,
        reference_date: date | None = None,
    ) -> GoalProgress:
        goal = self._goal(goal_id)
        reference = reference_date or date.today()
        if goal.linked_account_id is not None:
            account = self.accounts.get(goal.linked_account_id)
            if not account:
                raise ValueError("Linked account is unavailable")
            balance = self.accounts.balance(goal.linked_account_id)
            if balance is None:
                raise ValueError("Linked account is unavailable")
            current = max(balance, Decimal("0"))
        else:
            current = self.goals.manual_contributed(goal_id, reference)

        percent = (current / goal.target_amount * Decimal("100")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        required = self._required_monthly(goal, current, reference)
        on_track = self._on_track(goal, current, reference)
        return GoalProgress(
            goal=goal,
            current_amount=current,
            percent_complete=percent,
            on_track=on_track,
            required_monthly_contribution=required,
        )

    def list_progress(
        self,
        reference_date: date | None = None,
    ) -> list[GoalProgress]:
        return [
            self.progress(goal.id, reference_date)
            for goal in self.list_goals()
            if goal.id is not None
        ]

    def add_contribution(
        self,
        goal_id: str,
        source_account_id: str,
        target_account_id: str,
        amount: object,
        contribution_date: str,
        notes: str | None = None,
    ):
        with unit_of_work(self.db):
            goal = self._goal(goal_id)
            if not goal.is_active:
                raise ValueError("Contributions require an active goal")
            if goal.linked_account_id is not None:
                raise ValueError("Linked-account goals do not use manual contributions")
            return self.transactions.add_transfer(
                source_account_id,
                target_account_id,
                require_positive(amount),
                require_iso_date(contribution_date),
                f"Contribution to {goal.name}",
                notes,
                savings_goal_id=goal_id,
            )

    def _goal(self, goal_id: str) -> SavingsGoal:
        goal = self.goals.get(goal_id)
        if not goal:
            raise ValueError("Goal not found")
        return goal

    def _validate_linked_account(self, account_id: str | None) -> None:
        if account_id is None:
            return
        account = self.accounts.get(account_id)
        if not account or not account.is_active:
            raise ValueError("Linked account is unavailable")

    @staticmethod
    def _target_date(value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        return require_iso_date(value)

    @staticmethod
    def _required_monthly(
        goal: SavingsGoal,
        current: Decimal,
        reference: date,
    ) -> Decimal | None:
        if goal.target_date is None:
            return None
        remaining = max(goal.target_amount - current, Decimal("0"))
        if remaining == 0:
            return Decimal("0.00")
        target = date.fromisoformat(goal.target_date)
        if target < reference:
            return None
        months = (target.year - reference.year) * 12 + target.month - reference.month
        if target.day > reference.day:
            months += 1
        months = max(months, 1)
        return (remaining / Decimal(months)).quantize(CENT, rounding=ROUND_UP)

    @staticmethod
    def _on_track(
        goal: SavingsGoal,
        current: Decimal,
        reference: date,
    ) -> bool | None:
        if goal.target_date is None:
            return None
        target = date.fromisoformat(goal.target_date)
        created = (
            date.fromisoformat(goal.created_at[:10])
            if goal.created_at
            else reference
        )
        if target <= created or reference >= target:
            return current >= goal.target_amount
        if reference <= created:
            return True
        total_days = (target - created).days
        elapsed_days = min((reference - created).days, total_days)
        expected = (
            goal.target_amount
            * Decimal(elapsed_days)
            / Decimal(total_days)
        )
        return current >= expected
