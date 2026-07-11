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
        self.db.commit()
        row = self.db.execute("SELECT * FROM categories WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return row_to_category(row)

