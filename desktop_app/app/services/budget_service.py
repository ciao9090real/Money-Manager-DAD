from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.core.database import unit_of_work
from app.models.budget import Budget, BudgetStatus
from app.repositories.budget_repository import BudgetRepository
from app.repositories.category_repository import CategoryRepository
from app.utils.dates import require_iso_date, today_iso
from app.utils.money import require_positive


class BudgetService:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.budgets = BudgetRepository(db)
        self.categories = CategoryRepository(db)

    def list_budgets(self, active_only: bool = True) -> list[Budget]:
        return self.budgets.list(active_only=active_only)

    def set_budget(
        self,
        category_id: str,
        amount: object,
        rollover: bool = False,
        *,
        start_date: str | None = None,
    ) -> Budget:
        with unit_of_work(self.db):
            category = self.categories.get(category_id)
            if not category or not category.is_active:
                raise ValueError("Category not found or inactive")
            if category.type != "expense":
                raise ValueError("Budgets can only be assigned to expense categories")
            active_from = require_iso_date(start_date or today_iso())
            existing = self.budgets.get_by_category(category_id)
            if existing:
                existing.amount = require_positive(amount)
                existing.rollover = bool(rollover)
                existing.start_date = active_from
                existing.is_active = True
                return self.budgets.update(existing)
            return self.budgets.create(
                Budget(
                    id=None,
                    category_id=category_id,
                    period="monthly",
                    amount=require_positive(amount),
                    rollover=bool(rollover),
                    start_date=active_from,
                )
            )

    def set_active(self, budget_id: str, is_active: bool) -> Budget:
        with unit_of_work(self.db):
            budget = self._budget(budget_id)
            budget.is_active = bool(is_active)
            return self.budgets.update(budget)

    def delete_budget(self, budget_id: str) -> None:
        with unit_of_work(self.db):
            self._budget(budget_id)
            self.budgets.delete(budget_id)

    def status_for_period(
        self, reference_date: date | None = None
    ) -> list[BudgetStatus]:
        reference = reference_date or date.today()
        target_month = reference.replace(day=1)
        budgets = [
            budget
            for budget in self.budgets.list(active_only=True)
            if date.fromisoformat(budget.start_date).replace(day=1) <= target_month
        ]
        if not budgets:
            return []
        period_end = self._add_months(target_month, 1)
        earliest_start = min(date.fromisoformat(budget.start_date) for budget in budgets)
        spending = self.budgets.spending_by_category_and_date(
            earliest_start, period_end
        )
        result: list[BudgetStatus] = []
        for budget in budgets:
            start = date.fromisoformat(budget.start_date)
            rollover = self._rollover_entering(
                budget, start, target_month, spending
            )
            spending_start = max(start, target_month)
            spent = self._spent(
                spending, budget.category_id, spending_start, period_end
            )
            limit = budget.amount + rollover
            remaining = limit - spent
            percent_used = (
                (spent * Decimal("100") / limit).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if limit > 0
                else Decimal("0.00")
            )
            result.append(
                BudgetStatus(
                    budget=budget,
                    period_label=target_month.strftime("%Y-%m"),
                    limit=limit,
                    spent=spent,
                    remaining=remaining,
                    percent_used=percent_used,
                    rolled_over_from_prior=rollover,
                )
            )
        return result

    def overspent(self, reference_date: date | None = None) -> list[BudgetStatus]:
        return [
            status
            for status in self.status_for_period(reference_date)
            if status.percent_used > Decimal("100")
        ]

    def _rollover_entering(
        self,
        budget: Budget,
        start: date,
        target_month: date,
        spending: dict[str, list[tuple[date, Decimal]]],
    ) -> Decimal:
        if not budget.rollover:
            return Decimal("0.00")
        carry = Decimal("0.00")
        month = start.replace(day=1)
        while month < target_month:
            next_month = self._add_months(month, 1)
            spending_start = max(start, month)
            spent = self._spent(
                spending, budget.category_id, spending_start, next_month
            )
            carry = max(budget.amount + carry - spent, Decimal("0.00"))
            month = next_month
        return carry

    @staticmethod
    def _spent(
        spending: dict[str, list[tuple[date, Decimal]]],
        category_id: str,
        start: date,
        end: date,
    ) -> Decimal:
        return sum(
            (
                amount
                for transaction_date, amount in spending.get(category_id, [])
                if start <= transaction_date < end
            ),
            Decimal("0.00"),
        )

    @staticmethod
    def _add_months(value: date, months: int) -> date:
        month_index = value.year * 12 + value.month - 1 + months
        year, zero_based_month = divmod(month_index, 12)
        return date(year, zero_based_month + 1, 1)

    def _budget(self, budget_id: str) -> Budget:
        budget = self.budgets.get(budget_id)
        if not budget:
            raise ValueError("Budget not found")
        return budget
