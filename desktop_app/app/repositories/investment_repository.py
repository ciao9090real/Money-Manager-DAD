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

    def delete(self, investment_id: str) -> None:
        self.db.execute(
            f"""
            UPDATE investments
            SET is_active = 0, deleted_at = {UTC_NOW}, updated_at = {UTC_NOW},
                revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (investment_id,),
        )

    def record_value(
        self,
        investment_id: str,
        date: str,
        value: Decimal,
    ) -> InvestmentValuePoint:
        point_id = str(uuid4())
        contributed = self.total_contributed(investment_id)
        self.db.execute(
            """
            INSERT INTO investment_value_history (
                id, investment_id, date, value_cents, contributed_cents
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                point_id,
                investment_id,
                date,
                decimal_to_cents(value),
                decimal_to_cents(contributed),
            ),
        )
        row = self.db.execute(
            """
            SELECT id, investment_id, date, value_cents,
                   contributed_cents, created_at
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
                   history.value_cents, history.contributed_cents,
                   history.created_at
            FROM investment_value_history history
            JOIN investments investment ON investment.id = history.investment_id
            WHERE investment.deleted_at IS NULL
              AND history.deleted_at IS NULL
        """
        params: tuple[str, ...] = ()
        if investment_id is not None:
            query += " AND history.investment_id = ?"
            params = (investment_id,)
        query += " ORDER BY history.date, history.rowid"
        return [self._value_point(row) for row in self.db.execute(query, params)]

    def get_value_point(
        self,
        investment_id: str,
        point_id: str,
    ) -> InvestmentValuePoint | None:
        row = self.db.execute(
            """
            SELECT id, investment_id, date, value_cents,
                   contributed_cents, created_at
            FROM investment_value_history
            WHERE id = ? AND investment_id = ? AND deleted_at IS NULL
            """,
            (point_id, investment_id),
        ).fetchone()
        return self._value_point(row) if row else None

    def update_value_point(
        self,
        investment_id: str,
        point_id: str,
        value: Decimal,
    ) -> InvestmentValuePoint:
        self.db.execute(
            f"""
            UPDATE investment_value_history
            SET value_cents = ?, updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND investment_id = ? AND deleted_at IS NULL
            """,
            (decimal_to_cents(value), point_id, investment_id),
        )
        updated = self.get_value_point(investment_id, point_id)
        if not updated:
            raise ValueError("Value log not found")
        return updated

    def delete_value_point(self, investment_id: str, point_id: str) -> None:
        cursor = self.db.execute(
            f"""
            UPDATE investment_value_history
            SET deleted_at = {UTC_NOW}, updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND investment_id = ? AND deleted_at IS NULL
            """,
            (point_id, investment_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("Value log not found")

    def delete_all_value_points(self, investment_id: str) -> int:
        cursor = self.db.execute(
            f"""
            UPDATE investment_value_history
            SET deleted_at = {UTC_NOW}, updated_at = {UTC_NOW}, revision = revision + 1
            WHERE investment_id = ? AND deleted_at IS NULL
            """,
            (investment_id,),
        )
        return cursor.rowcount

    def total_contributed(self, investment_id: str) -> Decimal:
        row = self.db.execute(
            """
            SELECT COALESCE(SUM(t.amount_cents), 0) AS amount_cents
            FROM transactions AS t
            JOIN investments AS i ON i.id = t.investment_id
            WHERE t.investment_id = ?
              AND t.account_id = i.account_id
              AND t.type = 'transfer_in'
              AND t.deleted_at IS NULL
              AND i.deleted_at IS NULL
            """,
            (investment_id,),
        ).fetchone()
        return cents_to_decimal(row["amount_cents"])

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

    def list_funding_sources(
        self,
        investment_id: str,
    ) -> list[tuple[str, Decimal]]:
        rows = self.db.execute(
            """
            SELECT outgoing.account_id AS source_account_id,
                   SUM(incoming.amount_cents) AS contributed_cents
            FROM transactions AS incoming
            JOIN investments AS investment
              ON investment.id = incoming.investment_id
            JOIN transactions AS outgoing
              ON outgoing.transfer_group_id = incoming.transfer_group_id
             AND outgoing.type = 'transfer_out'
             AND outgoing.deleted_at IS NULL
            WHERE incoming.investment_id = ?
              AND incoming.account_id = investment.account_id
              AND incoming.type = 'transfer_in'
              AND incoming.deleted_at IS NULL
              AND investment.deleted_at IS NULL
            GROUP BY outgoing.account_id
            ORDER BY outgoing.account_id
            """,
            (investment_id,),
        ).fetchall()
        return [
            (row["source_account_id"], cents_to_decimal(row["contributed_cents"]))
            for row in rows
        ]

    @staticmethod
    def _value_point(row: sqlite3.Row) -> InvestmentValuePoint:
        return InvestmentValuePoint(
            id=row["id"],
            investment_id=row["investment_id"],
            date=row["date"],
            value=cents_to_decimal(row["value_cents"]),
            contributed=cents_to_decimal(row["contributed_cents"]),
            recorded_at=row["created_at"],
        )
