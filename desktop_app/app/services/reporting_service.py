from __future__ import annotations

import calendar
import sqlite3
from datetime import date, timedelta
from decimal import Decimal

from app.models.recurring_rule import RecurringRule
from app.repositories.recurring_rule_repository import RecurringRuleRepository
from app.services.dashboard_service import DashboardService
from app.utils.money import cents_to_decimal


class ReportingService:
    """Deterministic projections derived from current balances and active schedules."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.dashboard = DashboardService(db)
        self.rules = RecurringRuleRepository(db)

    def monthly_cash_flow(
        self,
        months: int = 6,
        reference_date: date | None = None,
    ) -> list[dict[str, str | Decimal]]:
        if months < 1:
            raise ValueError("Months must be at least 1")
        reference = reference_date or date.today()
        month_keys: list[str] = []
        for offset in reversed(range(months)):
            month_index = reference.year * 12 + reference.month - 1 - offset
            year, zero_based_month = divmod(month_index, 12)
            month_keys.append(f"{year:04d}-{zero_based_month + 1:02d}")

        rows = self.db.execute(
            """
            SELECT substr(date, 1, 7) AS month,
                   SUM(CASE WHEN type = 'income' THEN amount_cents ELSE 0 END)
                       AS income_cents,
                   SUM(CASE WHEN type = 'expense' THEN abs(amount_cents) ELSE 0 END)
                       AS expense_cents
            FROM transactions
            WHERE deleted_at IS NULL
              AND type IN ('income', 'expense')
              AND date >= ? AND date < ?
            GROUP BY substr(date, 1, 7)
            """,
            (f"{month_keys[0]}-01", self._month_after(month_keys[-1])),
        ).fetchall()
        by_month = {row["month"]: row for row in rows}
        result: list[dict[str, str | Decimal]] = []
        for month_key in month_keys:
            row = by_month.get(month_key)
            month_date = date.fromisoformat(f"{month_key}-01")
            result.append(
                {
                    "month": month_key,
                    "label": month_date.strftime("%b"),
                    "income": cents_to_decimal(row["income_cents"] if row else 0),
                    "expenses": cents_to_decimal(row["expense_cents"] if row else 0),
                }
            )
        return result

    def cash_forecast(
        self,
        reference_date: date | None = None,
        starting_balance: Decimal | None = None,
    ) -> dict:
        start = reference_date or date.today()
        three_month_end = self._add_months(start, 3, start.day)
        six_month_end = self._add_months(start, 6, start.day)
        current_balance = (
            starting_balance
            if starting_balance is not None
            else self.dashboard.global_snapshot()["liquidity"]
        )
        income_3 = Decimal("0")
        outgoing_3 = Decimal("0")
        income_6 = Decimal("0")
        outgoing_6 = Decimal("0")
        known_rules = 0
        unknown_rules = 0

        for rule in self.rules.list(status="active"):
            if rule.amount is None:
                unknown_rules += 1
                continue
            known_rules += 1
            occurrences = self._occurrences(rule, start, six_month_end)
            count_3 = sum(1 for due in occurrences if due <= three_month_end)
            count_6 = len(occurrences)
            if rule.transaction_type == "income":
                income_3 += rule.amount * count_3
                income_6 += rule.amount * count_6
            else:
                outgoing_3 += rule.amount * count_3
                outgoing_6 += rule.amount * count_6

        net_3 = income_3 - outgoing_3
        net_6 = income_6 - outgoing_6
        return {
            "as_of": start.isoformat(),
            "current_balance": current_balance,
            "three_month_balance": current_balance + net_3,
            "six_month_balance": current_balance + net_6,
            "three_month_change": net_3,
            "six_month_change": net_6,
            "three_month_income": income_3,
            "three_month_outgoings": outgoing_3,
            "six_month_income": income_6,
            "six_month_outgoings": outgoing_6,
            "known_schedule_count": known_rules,
            "unknown_amount_count": unknown_rules,
        }

    def _occurrences(
        self,
        rule: RecurringRule,
        start: date,
        horizon: date,
    ) -> list[date]:
        due = date.fromisoformat(rule.next_due_date)
        end = date.fromisoformat(rule.end_date) if rule.end_date else None
        anchor_day = date.fromisoformat(rule.start_date).day
        occurrences: list[date] = []

        if due < start:
            occurrences.append(start)
            while due < start:
                due = self._advance(due, rule.frequency, anchor_day)

        while due <= horizon:
            if due >= start and (end is None or due <= end):
                occurrences.append(due)
            due = self._advance(due, rule.frequency, anchor_day)
        return occurrences

    def _advance(self, value: date, frequency: str, anchor_day: int) -> date:
        if frequency == "weekly":
            return value + timedelta(days=7)
        months = {"monthly": 1, "quarterly": 3, "yearly": 12}[frequency]
        return self._add_months(value, months, anchor_day)

    @staticmethod
    def _add_months(value: date, months: int, anchor_day: int) -> date:
        month_index = value.year * 12 + value.month - 1 + months
        year, zero_based_month = divmod(month_index, 12)
        month = zero_based_month + 1
        day = min(anchor_day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    @staticmethod
    def _month_after(month_key: str) -> str:
        value = date.fromisoformat(f"{month_key}-01")
        month_index = value.year * 12 + value.month
        year, zero_based_month = divmod(month_index, 12)
        return f"{year:04d}-{zero_based_month + 1:02d}-01"
