from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.goal import SavingsGoal
from app.utils.money import cents_to_decimal, decimal_to_cents


UTC_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def row_to_goal(row: sqlite3.Row) -> SavingsGoal:
    return SavingsGoal(
        id=row["id"],
        name=row["name"],
        target_amount=cents_to_decimal(row["target_amount_cents"]),
        target_date=row["target_date"],
        linked_account_id=row["linked_account_id"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        revision=row["revision"],
    )


class GoalRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def list(self, include_inactive: bool = False) -> list[SavingsGoal]:
        query = "SELECT * FROM savings_goals WHERE deleted_at IS NULL"
        if not include_inactive:
            query += " AND is_active = 1"
        query += " ORDER BY is_active DESC, COALESCE(target_date, '9999-12-31'), name"
        return [row_to_goal(row) for row in self.db.execute(query)]

    def get(self, goal_id: str) -> SavingsGoal | None:
        row = self.db.execute(
            "SELECT * FROM savings_goals WHERE id = ? AND deleted_at IS NULL",
            (goal_id,),
        ).fetchone()
        return row_to_goal(row) if row else None

    def create(self, goal: SavingsGoal) -> SavingsGoal:
        goal_id = goal.id or str(uuid4())
        self.db.execute(
            """
            INSERT INTO savings_goals (
                id, name, target_amount_cents, target_date,
                linked_account_id, is_active
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                goal_id,
                goal.name,
                decimal_to_cents(goal.target_amount),
                goal.target_date,
                goal.linked_account_id,
                int(goal.is_active),
            ),
        )
        created = self.get(goal_id)
        assert created is not None
        return created

    def update(self, goal: SavingsGoal) -> SavingsGoal:
        if goal.id is None:
            raise ValueError("Goal id is required")
        self.db.execute(
            f"""
            UPDATE savings_goals
            SET name = ?, target_amount_cents = ?, target_date = ?,
                linked_account_id = ?, is_active = ?,
                updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (
                goal.name,
                decimal_to_cents(goal.target_amount),
                goal.target_date,
                goal.linked_account_id,
                int(goal.is_active),
                goal.id,
            ),
        )
        updated = self.get(goal.id)
        if not updated:
            raise ValueError("Goal not found")
        return updated

    def delete(self, goal_id: str) -> None:
        cursor = self.db.execute(
            f"""
            UPDATE savings_goals
            SET is_active = 0, deleted_at = {UTC_NOW}, updated_at = {UTC_NOW},
                revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (goal_id,),
        )
        if cursor.rowcount != 1:
            raise ValueError("Goal not found")

    def manual_contributed(
        self,
        goal_id: str,
        reference_date: date | None = None,
    ) -> Decimal:
        conditions = [
            "savings_goal_id = ?",
            "type = 'transfer_in'",
            "deleted_at IS NULL",
        ]
        params: list[object] = [goal_id]
        if reference_date is not None:
            conditions.append("date <= ?")
            params.append(reference_date.isoformat())
        row = self.db.execute(
            f"""
            SELECT COALESCE(SUM(amount_cents), 0) AS contributed_cents
            FROM transactions
            WHERE {" AND ".join(conditions)}
            """,
            params,
        ).fetchone()
        return cents_to_decimal(row["contributed_cents"])
