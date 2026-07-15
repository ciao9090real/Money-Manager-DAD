from __future__ import annotations

import sqlite3
from uuid import uuid4

from app.models.category import Category


UTC_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def row_to_category(row: sqlite3.Row) -> Category:
    return Category(
        id=row["id"],
        name=row["name"],
        type=row["type"],
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        revision=row["revision"],
    )


class CategoryRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def list(self, include_inactive: bool = False) -> list[Category]:
        query = "SELECT * FROM categories WHERE deleted_at IS NULL"
        if not include_inactive:
            query += " AND is_active = 1"
        query += " ORDER BY type, name"
        return [row_to_category(row) for row in self.db.execute(query)]

    def create(self, category: Category) -> Category:
        category_id = category.id or str(uuid4())
        self.db.execute(
            "INSERT INTO categories (id, name, type, is_active) VALUES (?, ?, ?, ?)",
            (category_id, category.name, category.type, int(category.is_active)),
        )
        created = self.get(category_id)
        assert created is not None
        return created

    def get(self, category_id: str) -> Category | None:
        row = self.db.execute(
            "SELECT * FROM categories WHERE id = ? AND deleted_at IS NULL", (category_id,)
        ).fetchone()
        return row_to_category(row) if row else None

    def find_by_name_and_type(self, name: str, category_type: str) -> Category | None:
        row = self.db.execute(
            """
            SELECT * FROM categories
            WHERE lower(name) = lower(?) AND type = ? AND deleted_at IS NULL
            ORDER BY is_active DESC, id
            LIMIT 1
            """,
            (name, category_type),
        ).fetchone()
        return row_to_category(row) if row else None

    def update(self, category: Category) -> Category:
        if category.id is None:
            raise ValueError("Category id is required")
        self.db.execute(
            f"""
            UPDATE categories
            SET name = ?, type = ?, is_active = ?, updated_at = {UTC_NOW},
                revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (category.name, category.type, int(category.is_active), category.id),
        )
        updated = self.get(category.id)
        assert updated is not None
        return updated

    def set_active(self, category_id: str, is_active: bool) -> None:
        self.db.execute(
            f"""
            UPDATE categories
            SET is_active = ?, updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (int(is_active), category_id),
        )
