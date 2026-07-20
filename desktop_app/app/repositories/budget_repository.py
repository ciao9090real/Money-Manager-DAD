from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.budget import Budget
from app.utils.money import cents_to_decimal, decimal_to_cents


UTC_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def row_to_budget(row: sqlite3.Row) -> Budget:
    return Budget(
        id=row["id"],
        category_id=row["category_id"],
        period=row["period"],
        amount=cents_to_decimal(row["amount_cents"]),
        rollover=bool(row["rollover"]),
        start_date=row["start_date"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        revision=row["revision"],
    )


class BudgetRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def list(self, active_only: bool = True) -> list[Budget]:
        query = "SELECT * FROM budgets WHERE deleted_at IS NULL"
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY category_id, period"
        return [row_to_budget(row) for row in self.db.execute(query)]

    def get(self, budget_id: str) -> Budget | None:
        row = self.db.execute(
            "SELECT * FROM budgets WHERE id = ? AND deleted_at IS NULL",
            (budget_id,),
        ).fetchone()
        return row_to_budget(row) if row else None

    def get_by_category(
        self, category_id: str, period: str = "monthly"
    ) -> Budget | None:
        row = self.db.execute(
            """
            SELECT * FROM budgets
            WHERE category_id = ? AND period = ? AND deleted_at IS NULL
            """,
            (category_id, period),
        ).fetchone()
        return row_to_budget(row) if row else None

    def create(self, budget: Budget) -> Budget:
        budget_id = budget.id or str(uuid4())
        self.db.execute(
            """
            INSERT INTO budgets (
                id, category_id, period, amount_cents, rollover, start_date, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                budget_id,
                budget.category_id,
                budget.period,
                decimal_to_cents(budget.amount),
                int(budget.rollover),
                budget.start_date,
                int(budget.is_active),
            ),
        )
        created = self.get(budget_id)
        assert created is not None
        return created

    def update(self, budget: Budget) -> Budget:
        if budget.id is None:
            raise ValueError("Budget id is required")
        self.db.execute(
            f"""
            UPDATE budgets
            SET amount_cents = ?, rollover = ?, start_date = ?, is_active = ?,
                updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (
                decimal_to_cents(budget.amount),
                int(budget.rollover),
                budget.start_date,
                int(budget.is_active),
                budget.id,
            ),
        )
        updated = self.get(budget.id)
        assert updated is not None
        return updated

    def delete(self, budget_id: str) -> None:
        self.db.execute(
            f"""
            UPDATE budgets
            SET deleted_at = {UTC_NOW}, updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (budget_id,),
        )

    def spending_by_category_and_date(
        self, start_date: date, end_date: date
    ) -> dict[str, list[tuple[date, Decimal]]]:
        rows = self.db.execute(
            """
            SELECT category_id, date, COALESCE(SUM(-amount_cents), 0) AS spent_cents
            FROM transactions
            WHERE deleted_at IS NULL
              AND type = 'expense'
              AND category_id IS NOT NULL
              AND date >= ? AND date < ?
            GROUP BY category_id, date
            ORDER BY category_id, date
            """,
            (start_date.isoformat(), end_date.isoformat()),
        )
        result: dict[str, list[tuple[date, Decimal]]] = {}
        for row in rows:
            result.setdefault(row["category_id"], []).append(
                (date.fromisoformat(row["date"]), cents_to_decimal(row["spent_cents"]))
            )
        return result
