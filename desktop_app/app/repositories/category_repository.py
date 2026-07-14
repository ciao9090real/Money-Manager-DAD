from __future__ import annotations

import sqlite3

from app.models.category import Category


def row_to_category(row: sqlite3.Row) -> Category:
    return Category(id=row["id"], name=row["name"], type=row["type"], is_active=bool(row["is_active"]))


class CategoryRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def list(self, include_inactive: bool = False) -> list[Category]:
        query = "SELECT * FROM categories"
        if not include_inactive:
            query += " WHERE is_active = 1"
        query += " ORDER BY type, name"
        return [row_to_category(row) for row in self.db.execute(query)]

    def create(self, category: Category) -> Category:
        cursor = self.db.execute(
            "INSERT INTO categories (name, type, is_active) VALUES (?, ?, ?)",
            (category.name, category.type, int(category.is_active)),
        )
        created = self.get(int(cursor.lastrowid))
        assert created is not None
        return created

    def get(self, category_id: int) -> Category | None:
        row = self.db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        return row_to_category(row) if row else None

    def find_by_name_and_type(self, name: str, category_type: str) -> Category | None:
        row = self.db.execute(
            """
            SELECT * FROM categories
            WHERE lower(name) = lower(?) AND type = ?
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
            "UPDATE categories SET name = ?, type = ?, is_active = ? WHERE id = ?",
            (category.name, category.type, int(category.is_active), category.id),
        )
        updated = self.get(category.id)
        assert updated is not None
        return updated

    def set_active(self, category_id: int, is_active: bool) -> None:
        self.db.execute(
            "UPDATE categories SET is_active = ? WHERE id = ?",
            (int(is_active), category_id),
        )
