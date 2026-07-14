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

    def list(
        self,
        limit: int | None = None,
        *,
        transaction_type: str | None = None,
        account_id: int | None = None,
        category_id: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        search_text: str | None = None,
        cursor: tuple[str, int] | None = None,
    ) -> list[Transaction]:
        query = "SELECT * FROM transactions"
        conditions: list[str] = []
        params: list[object] = []
        if transaction_type == "transfer":
            conditions.append("type IN ('transfer_out', 'transfer_in')")
        elif transaction_type:
            conditions.append("type = ?")
            params.append(transaction_type)
        if account_id is not None:
            conditions.append("account_id = ?")
            params.append(account_id)
        if category_id is not None:
            conditions.append("category_id = ?")
            params.append(category_id)
        if start_date:
            conditions.append("date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("date < ?")
            params.append(end_date)
        if search_text and search_text.strip():
            escaped = self._escape_like(search_text.strip())
            conditions.append("(description LIKE ? ESCAPE '\\' OR COALESCE(notes, '') LIKE ? ESCAPE '\\')")
            params.extend((f"%{escaped}%", f"%{escaped}%"))
        if cursor is not None:
            cursor_date, cursor_id = cursor
            conditions.append("(date < ? OR (date = ? AND id < ?))")
            params.extend((cursor_date, cursor_date, cursor_id))
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY date DESC, id DESC"
        if limit is not None:
            if int(limit) <= 0:
                raise ValueError("Page size must be positive")
            query += " LIMIT ?"
            params.append(int(limit))
        return [row_to_transaction(row) for row in self.db.execute(query, params)]

    def monthly_totals(self, start_date: str, end_date: str) -> tuple[Decimal, Decimal]:
        row = self.db.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN -amount ELSE 0 END), 0) AS expenses
            FROM transactions
            WHERE date >= ? AND date < ?
            """,
            (start_date, end_date),
        ).fetchone()
        return Decimal(str(row["income"] or 0)), Decimal(str(row["expenses"] or 0))

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

    def list_by_transfer_group(self, transfer_group_id: str) -> list[Transaction]:
        return [
            row_to_transaction(row)
            for row in self.db.execute(
                "SELECT * FROM transactions WHERE transfer_group_id = ? ORDER BY amount",
                (transfer_group_id,),
            )
        ]

    def update(self, transaction: Transaction) -> Transaction:
        if transaction.id is None:
            raise ValueError("Transaction id is required")
        self.db.execute(
            """
            UPDATE transactions
            SET date = ?, type = ?, account_id = ?, payment_method_id = ?, amount = ?,
                description = ?, category_id = ?, transfer_group_id = ?, notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
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
                transaction.id,
            ),
        )
        updated = self.get(transaction.id)
        assert updated is not None
        return updated

    def delete(self, transaction_id: int) -> None:
        self.db.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
