from __future__ import annotations

import sqlite3

from app.models.category import Category
from app.repositories.category_repository import CategoryRepository
from app.utils.validators import require_text


class CategoryService:
    VALID_TYPES = {"income", "expense"}

    def __init__(self, db: sqlite3.Connection):
        self.categories = CategoryRepository(db)

    def list_categories(self, include_inactive: bool = False) -> list[Category]:
        return self.categories.list(include_inactive=include_inactive)

    def create_category(self, name: str, category_type: str) -> Category:
        cleaned_type = self._require_type(category_type)
        cleaned_name = require_text(name, "Category name")
        existing = self.categories.find_by_name_and_type(cleaned_name, cleaned_type)
        if existing:
            if not existing.is_active:
                raise ValueError("Category is inactive")
            return existing
        return self.categories.create(Category(id=None, name=cleaned_name, type=cleaned_type))

    def category_id_for_input(self, value: object, category_type: str) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            category = self.categories.get(value)
            if not category:
                raise ValueError("Category not found")
            if not category.is_active:
                raise ValueError("Category is inactive")
            if category.type != self._require_type(category_type):
                raise ValueError("Category type does not match transaction type")
            return category.id

        cleaned = str(value).strip()
        if not cleaned:
            return None
        category = self.create_category(cleaned, category_type)
        return category.id

    def _require_type(self, category_type: str) -> str:
        cleaned = require_text(category_type, "Category type")
        if cleaned not in self.VALID_TYPES:
            raise ValueError("Category type must be income or expense")
        return cleaned
