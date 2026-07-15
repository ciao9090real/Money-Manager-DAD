from __future__ import annotations

import sqlite3
from decimal import Decimal
from uuid import uuid4

from app.models.account import Account
from app.utils.money import cents_to_decimal, decimal_to_cents


UTC_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def row_to_account(row: sqlite3.Row) -> Account:
    return Account(
        id=row["id"],
        name=row["name"],
        type=row["type"],
        parent_id=row["parent_id"],
        opening_balance=cents_to_decimal(row["opening_balance_cents"]),
        is_active=bool(row["is_active"]),
        display_order=row["display_order"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        revision=row["revision"],
    )


class AccountRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def list(self, include_inactive: bool = False) -> list[Account]:
        query = "SELECT * FROM accounts WHERE deleted_at IS NULL"
        params: list[object] = []
        if not include_inactive:
            query += " AND is_active = 1"
        query += " ORDER BY display_order, name"
        return [row_to_account(row) for row in self.db.execute(query, params)]

    def list_with_balances(
        self, include_inactive: bool = False
    ) -> list[tuple[Account, Decimal]]:
        query = """
            WITH transaction_balances AS (
                SELECT account_id, SUM(amount_cents) AS total_cents
                FROM transactions
                WHERE deleted_at IS NULL
                GROUP BY account_id
            )
            SELECT a.*, a.opening_balance_cents + COALESCE(b.total_cents, 0) AS balance_cents
            FROM accounts a
            LEFT JOIN transaction_balances b ON b.account_id = a.id
            WHERE a.deleted_at IS NULL
        """
        params: list[object] = []
        if not include_inactive:
            query += " AND a.is_active = 1"
        query += " ORDER BY a.display_order, a.name"
        return [
            (row_to_account(row), cents_to_decimal(row["balance_cents"]))
            for row in self.db.execute(query, params)
        ]

    def balance(self, account_id: str) -> Decimal | None:
        row = self.db.execute(
            """
            SELECT a.opening_balance_cents + COALESCE(SUM(t.amount_cents), 0) AS balance_cents
            FROM accounts a
            LEFT JOIN transactions t ON t.account_id = a.id AND t.deleted_at IS NULL
            WHERE a.id = ? AND a.deleted_at IS NULL
            GROUP BY a.id
            """,
            (account_id,),
        ).fetchone()
        return cents_to_decimal(row["balance_cents"]) if row else None

    def get(self, account_id: str) -> Account | None:
        row = self.db.execute(
            "SELECT * FROM accounts WHERE id = ? AND deleted_at IS NULL", (account_id,)
        ).fetchone()
        return row_to_account(row) if row else None

    def create(self, account: Account) -> Account:
        account_id = account.id or str(uuid4())
        self.db.execute(
            """
            INSERT INTO accounts (
                id, name, type, parent_id, opening_balance_cents, is_active, display_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                account.name,
                account.type,
                account.parent_id,
                decimal_to_cents(account.opening_balance),
                int(account.is_active),
                account.display_order,
            ),
        )
        created = self.get(account_id)
        assert created is not None
        return created

    def update(self, account: Account) -> Account:
        if account.id is None:
            raise ValueError("Account id is required")
        self.db.execute(
            f"""
            UPDATE accounts
            SET name = ?, type = ?, parent_id = ?, opening_balance_cents = ?, is_active = ?,
                display_order = ?, updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (
                account.name,
                account.type,
                account.parent_id,
                decimal_to_cents(account.opening_balance),
                int(account.is_active),
                account.display_order,
                account.id,
            ),
        )
        updated = self.get(account.id)
        assert updated is not None
        return updated

    def deactivate(self, account_id: str) -> None:
        self.db.execute(
            f"""
            UPDATE accounts
            SET is_active = 0, updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (account_id,),
        )

    def has_active_children(self, account_id: str) -> bool:
        row = self.db.execute(
            """
            SELECT 1 FROM accounts
            WHERE parent_id = ? AND is_active = 1 AND deleted_at IS NULL LIMIT 1
            """,
            (account_id,),
        ).fetchone()
        return row is not None
