from __future__ import annotations

import sqlite3

from app.models.payment_method import PaymentMethod


def row_to_payment_method(row: sqlite3.Row) -> PaymentMethod:
    return PaymentMethod(
        id=row["id"],
        name=row["name"],
        account_id=row["account_id"],
        type=row["type"],
        is_active=bool(row["is_active"]),
    )


class PaymentMethodRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def list(self, include_inactive: bool = False) -> list[PaymentMethod]:
        query = "SELECT * FROM payment_methods"
        if not include_inactive:
            query += " WHERE is_active = 1"
        query += " ORDER BY name"
        return [row_to_payment_method(row) for row in self.db.execute(query)]

    def get(self, payment_method_id: int) -> PaymentMethod | None:
        row = self.db.execute(
            "SELECT * FROM payment_methods WHERE id = ?", (payment_method_id,)
        ).fetchone()
        return row_to_payment_method(row) if row else None

    def find_by_account_and_name(self, account_id: int, name: str) -> PaymentMethod | None:
        row = self.db.execute(
            """
            SELECT * FROM payment_methods
            WHERE account_id = ? AND lower(name) = lower(?)
            ORDER BY is_active DESC, id
            LIMIT 1
            """,
            (account_id, name),
        ).fetchone()
        return row_to_payment_method(row) if row else None

    def create(self, payment_method: PaymentMethod) -> PaymentMethod:
        cursor = self.db.execute(
            "INSERT INTO payment_methods (name, account_id, type, is_active) VALUES (?, ?, ?, ?)",
            (payment_method.name, payment_method.account_id, payment_method.type, int(payment_method.is_active)),
        )
        created = self.get(int(cursor.lastrowid))
        assert created is not None
        return created

    def update(self, payment_method: PaymentMethod) -> PaymentMethod:
        if payment_method.id is None:
            raise ValueError("Payment method id is required")
        self.db.execute(
            """
            UPDATE payment_methods
            SET name = ?, account_id = ?, type = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                payment_method.name,
                payment_method.account_id,
                payment_method.type,
                int(payment_method.is_active),
                payment_method.id,
            ),
        )
        updated = self.get(payment_method.id)
        assert updated is not None
        return updated

    def set_active(self, payment_method_id: int, is_active: bool) -> None:
        self.db.execute(
            """
            UPDATE payment_methods
            SET is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (int(is_active), payment_method_id),
        )
