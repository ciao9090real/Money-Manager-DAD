from __future__ import annotations

import sqlite3
from uuid import uuid4

from app.models.payment_method import PaymentMethod


UTC_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def row_to_payment_method(row: sqlite3.Row) -> PaymentMethod:
    return PaymentMethod(
        id=row["id"],
        name=row["name"],
        account_id=row["account_id"],
        type=row["type"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        revision=row["revision"],
    )


class PaymentMethodRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def list(self, include_inactive: bool = False) -> list[PaymentMethod]:
        query = "SELECT * FROM payment_methods WHERE deleted_at IS NULL"
        if not include_inactive:
            query += " AND is_active = 1"
        query += " ORDER BY name"
        return [row_to_payment_method(row) for row in self.db.execute(query)]

    def get(self, payment_method_id: str) -> PaymentMethod | None:
        row = self.db.execute(
            "SELECT * FROM payment_methods WHERE id = ? AND deleted_at IS NULL",
            (payment_method_id,),
        ).fetchone()
        return row_to_payment_method(row) if row else None

    def find_by_account_and_name(self, account_id: str, name: str) -> PaymentMethod | None:
        row = self.db.execute(
            """
            SELECT * FROM payment_methods
            WHERE account_id = ? AND lower(name) = lower(?) AND deleted_at IS NULL
            ORDER BY is_active DESC, id
            LIMIT 1
            """,
            (account_id, name),
        ).fetchone()
        return row_to_payment_method(row) if row else None

    def create(self, payment_method: PaymentMethod) -> PaymentMethod:
        method_id = payment_method.id or str(uuid4())
        self.db.execute(
            """
            INSERT INTO payment_methods (id, name, account_id, type, is_active)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                method_id,
                payment_method.name,
                payment_method.account_id,
                payment_method.type,
                int(payment_method.is_active),
            ),
        )
        created = self.get(method_id)
        assert created is not None
        return created

    def update(self, payment_method: PaymentMethod) -> PaymentMethod:
        if payment_method.id is None:
            raise ValueError("Payment method id is required")
        self.db.execute(
            f"""
            UPDATE payment_methods
            SET name = ?, account_id = ?, type = ?, is_active = ?,
                updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
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

    def set_active(self, payment_method_id: str, is_active: bool) -> None:
        self.db.execute(
            f"""
            UPDATE payment_methods
            SET is_active = ?, updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (int(is_active), payment_method_id),
        )
