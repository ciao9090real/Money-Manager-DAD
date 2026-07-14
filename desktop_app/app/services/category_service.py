from __future__ import annotations

import sqlite3

from app.core.database import unit_of_work
from app.models.category import Category
from app.repositories.category_repository import CategoryRepository
from app.utils.validators import require_text


class CategoryService:
    VALID_TYPES = {"income", "expense"}

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.categories = CategoryRepository(db)

    def list_categories(self, include_inactive: bool = False) -> list[Category]:
        return self.categories.list(include_inactive=include_inactive)

    def create_category(self, name: str, category_type: str) -> Category:
        with unit_of_work(self.db):
            cleaned_type = self._require_type(category_type)
            cleaned_name = require_text(name, "Category name")
            existing = self.categories.find_by_name_and_type(cleaned_name, cleaned_type)
            if existing:
                if not existing.is_active:
                    raise ValueError("Category is inactive")
                return existing
            return self.categories.create(Category(id=None, name=cleaned_name, type=cleaned_type))

    def update_category(self, category_id: int, name: str, category_type: str) -> Category:
        with unit_of_work(self.db):
            category = self._require_category(category_id)
            cleaned_name = require_text(name, "Category name")
            cleaned_type = self._require_type(category_type)
            duplicate = self.categories.find_by_name_and_type(cleaned_name, cleaned_type)
            if duplicate and duplicate.id != category_id:
                raise ValueError("A category with this name and type already exists")
            category.name = cleaned_name
            category.type = cleaned_type
            return self.categories.update(category)

    def archive_category(self, category_id: int) -> None:
        with unit_of_work(self.db):
            self._require_category(category_id)
            self.categories.set_active(category_id, False)

    def restore_category(self, category_id: int) -> None:
        with unit_of_work(self.db):
            category = self._require_category(category_id)
            duplicate = self.categories.find_by_name_and_type(category.name, category.type)
            if duplicate and duplicate.id != category_id and duplicate.is_active:
                raise ValueError("An active category with this name and type already exists")
            self.categories.set_active(category_id, True)

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

    def _require_category(self, category_id: int) -> Category:
        category = self.categories.get(category_id)
        if not category:
            raise ValueError("Category not found")
        return category
