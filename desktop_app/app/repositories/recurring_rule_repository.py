from __future__ import annotations

import sqlite3
from uuid import uuid4

from app.models.recurring_rule import RecurringRule
from app.utils.money import cents_to_decimal, decimal_to_cents


UTC_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def row_to_recurring_rule(row: sqlite3.Row) -> RecurringRule:
    return RecurringRule(
        id=row["id"],
        name=row["name"],
        kind=row["kind"],
        amount_mode=row["amount_mode"],
        amount=(
            cents_to_decimal(row["amount_cents"])
            if row["amount_cents"] is not None
            else None
        ),
        account_id=row["account_id"],
        category_id=row["category_id"],
        payment_method_id=row["payment_method_id"],
        frequency=row["frequency"],
        start_date=row["start_date"],
        next_due_date=row["next_due_date"],
        end_date=row["end_date"],
        reminder_days=row["reminder_days"],
        status=row["status"],
        last_recorded_date=row["last_recorded_date"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        revision=row["revision"],
    )


class RecurringRuleRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def list(
        self,
        *,
        status: str | None = None,
        kind: str | None = None,
    ) -> list[RecurringRule]:
        conditions = ["deleted_at IS NULL"]
        params: list[object] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if kind:
            conditions.append("kind = ?")
            params.append(kind)
        rows = self.db.execute(
            f"""
            SELECT * FROM recurring_rules
            WHERE {" AND ".join(conditions)}
            ORDER BY
                CASE status WHEN 'active' THEN 0 WHEN 'paused' THEN 1 ELSE 2 END,
                next_due_date, name
            """,
            params,
        )
        return [row_to_recurring_rule(row) for row in rows]

    def get(self, rule_id: str) -> RecurringRule | None:
        row = self.db.execute(
            "SELECT * FROM recurring_rules WHERE id = ? AND deleted_at IS NULL",
            (rule_id,),
        ).fetchone()
        return row_to_recurring_rule(row) if row else None

    def create(self, rule: RecurringRule) -> RecurringRule:
        rule_id = rule.id or str(uuid4())
        self.db.execute(
            """
            INSERT INTO recurring_rules (
                id, name, kind, amount_mode, amount_cents, account_id, category_id,
                payment_method_id, frequency, start_date, next_due_date, end_date,
                reminder_days, status, last_recorded_date, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule_id,
                rule.name,
                rule.kind,
                rule.amount_mode,
                decimal_to_cents(rule.amount) if rule.amount is not None else None,
                rule.account_id,
                rule.category_id,
                rule.payment_method_id,
                rule.frequency,
                rule.start_date,
                rule.next_due_date,
                rule.end_date,
                rule.reminder_days,
                rule.status,
                rule.last_recorded_date,
                rule.notes,
            ),
        )
        created = self.get(rule_id)
        assert created is not None
        return created

    def update(self, rule: RecurringRule) -> RecurringRule:
        if rule.id is None:
            raise ValueError("Recurring rule id is required")
        self.db.execute(
            f"""
            UPDATE recurring_rules
            SET name = ?, kind = ?, amount_mode = ?, amount_cents = ?, account_id = ?,
                category_id = ?, payment_method_id = ?, frequency = ?, start_date = ?,
                next_due_date = ?, end_date = ?, reminder_days = ?, status = ?,
                last_recorded_date = ?, notes = ?, updated_at = {UTC_NOW},
                revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (
                rule.name,
                rule.kind,
                rule.amount_mode,
                decimal_to_cents(rule.amount) if rule.amount is not None else None,
                rule.account_id,
                rule.category_id,
                rule.payment_method_id,
                rule.frequency,
                rule.start_date,
                rule.next_due_date,
                rule.end_date,
                rule.reminder_days,
                rule.status,
                rule.last_recorded_date,
                rule.notes,
                rule.id,
            ),
        )
        updated = self.get(rule.id)
        assert updated is not None
        return updated

    def delete(self, rule_id: str) -> None:
        self.db.execute(
            f"""
            UPDATE recurring_rules
            SET deleted_at = {UTC_NOW}, updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (rule_id,),
        )
