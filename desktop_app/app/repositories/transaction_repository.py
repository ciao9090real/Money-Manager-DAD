from __future__ import annotations

import sqlite3
from decimal import Decimal
from uuid import uuid4

from app.models.transaction import Transaction
from app.utils.money import cents_to_decimal, decimal_to_cents


UTC_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def row_to_transaction(row: sqlite3.Row) -> Transaction:
    return Transaction(
        id=row["id"],
        date=row["date"],
        type=row["type"],
        account_id=row["account_id"],
        payment_method_id=row["payment_method_id"],
        amount=cents_to_decimal(row["amount_cents"]),
        description=row["description"],
        category_id=row["category_id"],
        transfer_group_id=row["transfer_group_id"],
        recurring_rule_id=row["recurring_rule_id"],
        investment_id=row["investment_id"],
        loan_id=row["loan_id"],
        notes=row["notes"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        revision=row["revision"],
    )


class TransactionRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def list(
        self,
        limit: int | None = None,
        *,
        transaction_type: str | None = None,
        account_id: str | None = None,
        account_ids: list[str] | tuple[str, ...] | set[str] | None = None,
        category_id: str | None = None,
        recurring_rule_id: str | None = None,
        investment_id: str | None = None,
        loan_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        search_text: str | None = None,
        cursor: tuple[str, str] | None = None,
        exclude_investment_adjustments: bool = False,
        exclude_adjustments: bool = False,
    ) -> list[Transaction]:
        query = "SELECT * FROM transactions"
        conditions: list[str] = ["deleted_at IS NULL"]
        params: list[object] = []
        if transaction_type == "transfer":
            conditions.append("type IN ('transfer_out', 'transfer_in')")
        elif transaction_type:
            conditions.append("type = ?")
            params.append(transaction_type)
        if account_id is not None:
            conditions.append("account_id = ?")
            params.append(account_id)
        if account_ids is not None:
            ids = list(account_ids)
            if not ids:
                return []
            placeholders = ", ".join("?" for _ in ids)
            conditions.append(f"account_id IN ({placeholders})")
            params.extend(ids)
        if category_id is not None:
            conditions.append("category_id = ?")
            params.append(category_id)
        if recurring_rule_id is not None:
            conditions.append("recurring_rule_id = ?")
            params.append(recurring_rule_id)
        if investment_id is not None:
            conditions.append("investment_id = ?")
            params.append(investment_id)
        if loan_id is not None:
            conditions.append("loan_id = ?")
            params.append(loan_id)
        if exclude_investment_adjustments:
            conditions.append(
                "NOT (type = 'adjustment' AND investment_id IS NOT NULL)"
            )
        if exclude_adjustments:
            conditions.append("type <> 'adjustment'")
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
        query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY date DESC, id DESC"
        if limit is not None:
            if int(limit) <= 0:
                raise ValueError("Page size must be positive")
            query += " LIMIT ?"
            params.append(int(limit))
        return [row_to_transaction(row) for row in self.db.execute(query, params)]

    def monthly_totals(
        self,
        start_date: str,
        end_date: str,
        account_ids: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> tuple[Decimal, Decimal]:
        conditions = ["date >= ?", "date < ?", "deleted_at IS NULL"]
        params: list[object] = [start_date, end_date]
        if account_ids is not None:
            ids = list(account_ids)
            if not ids:
                return Decimal("0"), Decimal("0")
            placeholders = ", ".join("?" for _ in ids)
            conditions.append(f"account_id IN ({placeholders})")
            params.extend(ids)
        row = self.db.execute(
            f"""
            SELECT
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount_cents ELSE 0 END), 0) AS income_cents,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN -amount_cents ELSE 0 END), 0) AS expense_cents
            FROM transactions
            WHERE {" AND ".join(conditions)}
            """,
            params,
        ).fetchone()
        return cents_to_decimal(row["income_cents"]), cents_to_decimal(row["expense_cents"])

    def create(self, transaction: Transaction) -> Transaction:
        transaction_id = transaction.id or str(uuid4())
        self.db.execute(
            """
            INSERT INTO transactions (
                id, date, type, account_id, payment_method_id, amount_cents,
                description, category_id, transfer_group_id, recurring_rule_id,
                investment_id, loan_id, notes, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transaction_id,
                transaction.date,
                transaction.type,
                transaction.account_id,
                transaction.payment_method_id,
                decimal_to_cents(transaction.amount),
                transaction.description,
                transaction.category_id,
                transaction.transfer_group_id,
                transaction.recurring_rule_id,
                transaction.investment_id,
                transaction.loan_id,
                transaction.notes,
                transaction.status,
            ),
        )
        created = self.get(transaction_id)
        assert created is not None
        return created

    def get(self, transaction_id: str) -> Transaction | None:
        row = self.db.execute(
            "SELECT * FROM transactions WHERE id = ? AND deleted_at IS NULL",
            (transaction_id,),
        ).fetchone()
        return row_to_transaction(row) if row else None

    def list_by_transfer_group(self, transfer_group_id: str) -> list[Transaction]:
        return [
            row_to_transaction(row)
            for row in self.db.execute(
                """
                SELECT * FROM transactions
                WHERE transfer_group_id = ? AND deleted_at IS NULL
                ORDER BY amount_cents
                """,
                (transfer_group_id,),
            )
        ]

    def update(self, transaction: Transaction) -> Transaction:
        if transaction.id is None:
            raise ValueError("Transaction id is required")
        self.db.execute(
            f"""
            UPDATE transactions
            SET date = ?, type = ?, account_id = ?, payment_method_id = ?, amount_cents = ?,
                description = ?, category_id = ?, transfer_group_id = ?, recurring_rule_id = ?,
                investment_id = ?, loan_id = ?, notes = ?, status = ?,
                updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (
                transaction.date,
                transaction.type,
                transaction.account_id,
                transaction.payment_method_id,
                decimal_to_cents(transaction.amount),
                transaction.description,
                transaction.category_id,
                transaction.transfer_group_id,
                transaction.recurring_rule_id,
                transaction.investment_id,
                transaction.loan_id,
                transaction.notes,
                transaction.status,
                transaction.id,
            ),
        )
        updated = self.get(transaction.id)
        assert updated is not None
        return updated

    def delete(self, transaction_id: str) -> None:
        self.db.execute(
            f"""
            UPDATE transactions
            SET deleted_at = {UTC_NOW}, updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (transaction_id,),
        )

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
