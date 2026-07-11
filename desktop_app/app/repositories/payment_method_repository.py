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

    def create(self, payment_method: PaymentMethod) -> PaymentMethod:
        cursor = self.db.execute(
            "INSERT INTO payment_methods (name, account_id, type, is_active) VALUES (?, ?, ?, ?)",
            (payment_method.name, payment_method.account_id, payment_method.type, int(payment_method.is_active)),
        )
        self.db.commit()
        row = self.db.execute("SELECT * FROM payment_methods WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return row_to_payment_method(row)

