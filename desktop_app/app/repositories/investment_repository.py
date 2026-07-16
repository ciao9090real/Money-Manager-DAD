from __future__ import annotations

import sqlite3
from decimal import Decimal
from uuid import uuid4

from app.models.investment import Investment, InvestmentValuePoint
from app.utils.money import cents_to_decimal, decimal_to_cents


UTC_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def row_to_investment(row: sqlite3.Row) -> Investment:
    return Investment(
        id=row["id"],
        name=row["name"],
        kind=row["kind"],
        symbol=row["symbol"],
        account_id=row["account_id"],
        notes=row["notes"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        revision=row["revision"],
    )


class InvestmentRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def list(self, include_inactive: bool = False) -> list[Investment]:
        query = "SELECT * FROM investments WHERE deleted_at IS NULL"
        if not include_inactive:
            query += " AND is_active = 1"
        query += " ORDER BY name"
        return [row_to_investment(row) for row in self.db.execute(query)]

    def list_with_values(
        self, include_inactive: bool = False
    ) -> list[tuple[Investment, Decimal, Decimal]]:
        query = """
            WITH account_activity AS (
                SELECT account_id, SUM(amount_cents) AS amount_cents
                FROM transactions
                WHERE deleted_at IS NULL
                GROUP BY account_id
            ), contributions AS (
                SELECT investment_id, account_id, SUM(amount_cents) AS amount_cents
                FROM transactions
                WHERE investment_id IS NOT NULL
                  AND type = 'transfer_in'
                  AND deleted_at IS NULL
                GROUP BY investment_id, account_id
            )
            SELECT i.*,
                   a.opening_balance_cents + COALESCE(activity.amount_cents, 0)
                       AS current_value_cents,
                   COALESCE(contributions.amount_cents, 0) AS contributed_cents
            FROM investments i
            JOIN accounts a ON a.id = i.account_id AND a.deleted_at IS NULL
            LEFT JOIN account_activity activity ON activity.account_id = i.account_id
            LEFT JOIN contributions
                ON contributions.investment_id = i.id
               AND contributions.account_id = i.account_id
            WHERE i.deleted_at IS NULL
        """
        if not include_inactive:
            query += " AND i.is_active = 1"
        query += " ORDER BY i.name"
        return [
            (
                row_to_investment(row),
                cents_to_decimal(row["contributed_cents"]),
                cents_to_decimal(row["current_value_cents"]),
            )
            for row in self.db.execute(query)
        ]

    def get(self, investment_id: str) -> Investment | None:
        row = self.db.execute(
            "SELECT * FROM investments WHERE id = ? AND deleted_at IS NULL",
            (investment_id,),
        ).fetchone()
        return row_to_investment(row) if row else None

    def get_by_account(self, account_id: str) -> Investment | None:
        row = self.db.execute(
            "SELECT * FROM investments WHERE account_id = ? AND deleted_at IS NULL",
            (account_id,),
        ).fetchone()
        return row_to_investment(row) if row else None

    def create(self, investment: Investment) -> Investment:
        investment_id = investment.id or str(uuid4())
        self.db.execute(
            """
            INSERT INTO investments (id, name, kind, symbol, account_id, notes, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                investment_id,
                investment.name,
                investment.kind,
                investment.symbol,
                investment.account_id,
                investment.notes,
                int(investment.is_active),
            ),
        )
        created = self.get(investment_id)
        assert created is not None
        return created

    def update(self, investment: Investment) -> Investment:
        if investment.id is None:
            raise ValueError("Investment id is required")
        self.db.execute(
            f"""
            UPDATE investments
            SET name = ?, kind = ?, symbol = ?, notes = ?, is_active = ?,
                updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (
                investment.name,
                investment.kind,
                investment.symbol,
                investment.notes,
                int(investment.is_active),
                investment.id,
            ),
        )
        updated = self.get(investment.id)
        assert updated is not None
        return updated

    def record_value(
        self,
        investment_id: str,
        date: str,
        value: Decimal,
    ) -> InvestmentValuePoint:
        point_id = str(uuid4())
        self.db.execute(
            """
            INSERT INTO investment_value_history (
                id, investment_id, date, value_cents
            ) VALUES (?, ?, ?, ?)
            """,
            (point_id, investment_id, date, decimal_to_cents(value)),
        )
        row = self.db.execute(
            """
            SELECT id, investment_id, date, value_cents, created_at
            FROM investment_value_history
            WHERE id = ?
            """,
            (point_id,),
        ).fetchone()
        assert row is not None
        return self._value_point(row)

    def list_value_history(
        self,
        investment_id: str | None = None,
    ) -> list[InvestmentValuePoint]:
        query = """
            SELECT history.id, history.investment_id, history.date,
                   history.value_cents, history.created_at
            FROM investment_value_history history
            JOIN investments investment ON investment.id = history.investment_id
            WHERE investment.deleted_at IS NULL
        """
        params: tuple[str, ...] = ()
        if investment_id is not None:
            query += " AND history.investment_id = ?"
            params = (investment_id,)
        query += " ORDER BY history.date, history.rowid"
        return [self._value_point(row) for row in self.db.execute(query, params)]

    def list_contributions(
        self,
        investment_id: str | None = None,
    ) -> list[tuple[str, str, Decimal]]:
        query = """
            SELECT t.investment_id, t.date, t.amount_cents
            FROM transactions t
            JOIN investments i ON i.id = t.investment_id
            WHERE t.deleted_at IS NULL
              AND i.deleted_at IS NULL
              AND t.type = 'transfer_in'
              AND t.account_id = i.account_id
        """
        params: tuple[str, ...] = ()
        if investment_id is not None:
            query += " AND t.investment_id = ?"
            params = (investment_id,)
        query += " ORDER BY t.date, t.rowid"
        return [
            (
                row["investment_id"],
                row["date"],
                cents_to_decimal(row["amount_cents"]),
            )
            for row in self.db.execute(query, params)
        ]

    @staticmethod
    def _value_point(row: sqlite3.Row) -> InvestmentValuePoint:
        return InvestmentValuePoint(
            id=row["id"],
            investment_id=row["investment_id"],
            date=row["date"],
            value=cents_to_decimal(row["value_cents"]),
            recorded_at=row["created_at"],
        )
