from __future__ import annotations

import sqlite3
from decimal import Decimal

from app.models.transaction import Transaction


def row_to_transaction(row: sqlite3.Row) -> Transaction:
    return Transaction(
        id=row["id"],
        date=row["date"],
        type=row["type"],
        account_id=row["account_id"],
        payment_method_id=row["payment_method_id"],
        amount=Decimal(str(row["amount"])),
        description=row["description"],
        category_id=row["category_id"],
        transfer_group_id=row["transfer_group_id"],
        notes=row["notes"],
    )


class TransactionRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def list(self, limit: int | None = None) -> list[Transaction]:
        query = "SELECT * FROM transactions ORDER BY date DESC, id DESC"
        if limit:
            query += f" LIMIT {int(limit)}"
        return [row_to_transaction(row) for row in self.db.execute(query)]

    def list_for_month(self, month: str) -> list[Transaction]:
        return [
            row_to_transaction(row)
            for row in self.db.execute(
                "SELECT * FROM transactions WHERE date LIKE ? ORDER BY date DESC, id DESC",
                (f"{month}-%",),
            )
        ]

    def create(self, transaction: Transaction) -> Transaction:
        cursor = self.db.execute(
            """
            INSERT INTO transactions
                (date, type, account_id, payment_method_id, amount, description, category_id, transfer_group_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transaction.date,
                transaction.type,
                transaction.account_id,
                transaction.payment_method_id,
                str(transaction.amount),
                transaction.description,
                transaction.category_id,
                transaction.transfer_group_id,
                transaction.notes,
            ),
        )
        created = self.get(int(cursor.lastrowid))
        assert created is not None
        return created

    def get(self, transaction_id: int) -> Transaction | None:
        row = self.db.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
        return row_to_transaction(row) if row else None

