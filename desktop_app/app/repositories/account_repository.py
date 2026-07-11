from __future__ import annotations

import sqlite3
from decimal import Decimal

from app.models.account import Account


def row_to_account(row: sqlite3.Row) -> Account:
    return Account(
        id=row["id"],
        name=row["name"],
        type=row["type"],
        parent_id=row["parent_id"],
        opening_balance=Decimal(str(row["opening_balance"])),
        is_active=bool(row["is_active"]),
        display_order=row["display_order"],
    )


class AccountRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def list(self, include_inactive: bool = False) -> list[Account]:
        query = "SELECT * FROM accounts"
        params: list[object] = []
        if not include_inactive:
            query += " WHERE is_active = 1"
        query += " ORDER BY display_order, name"
        return [row_to_account(row) for row in self.db.execute(query, params)]

    def get(self, account_id: int) -> Account | None:
        row = self.db.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        return row_to_account(row) if row else None

    def create(self, account: Account) -> Account:
        cursor = self.db.execute(
            """
            INSERT INTO accounts (name, type, parent_id, opening_balance, is_active, display_order)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                account.name,
                account.type,
                account.parent_id,
                str(account.opening_balance),
                int(account.is_active),
                account.display_order,
            ),
        )
        self.db.commit()
        created = self.get(int(cursor.lastrowid))
        assert created is not None
        return created

    def update(self, account: Account) -> Account:
        if account.id is None:
            raise ValueError("Account id is required")
        self.db.execute(
            """
            UPDATE accounts
            SET name = ?, type = ?, parent_id = ?, opening_balance = ?, is_active = ?,
                display_order = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                account.name,
                account.type,
                account.parent_id,
                str(account.opening_balance),
                int(account.is_active),
                account.display_order,
                account.id,
            ),
        )
        self.db.commit()
        updated = self.get(account.id)
        assert updated is not None
        return updated

    def deactivate(self, account_id: int) -> None:
        self.db.execute(
            "UPDATE accounts SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (account_id,),
        )
        self.db.commit()

