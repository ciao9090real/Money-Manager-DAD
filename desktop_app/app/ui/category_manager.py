from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.core.database_security import DB_INTEGRITY_ERROR_TYPES
from app.models.category import Category
from app.services.category_service import CategoryService
from app.ui.components import (
    badge,
    badge_tone,
    create_card,
    dialog_shell,
    ghost_button,
    pretty_type,
    primary_button,
    secondary_button,
    soft_button,
    style_table,
    toolbar,
)


class CategoryManagerDialog(QDialog):
    def __init__(self, db: sqlite3.Connection, on_changed, notify=None):
        super().__init__()
        self.setWindowTitle("Manage categories")
        self.resize(700, 520)
        self.service = CategoryService(db)
        self.on_changed = on_changed
        self.notify = notify or (lambda _message: None)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Status"])
        style_table(self.table)

        add_button = primary_button("Add category", "plus")
        self.edit_button = ghost_button("Edit", "edit")
        self.toggle_button = soft_button("Archive / restore", "archive")
        self.edit_button.setEnabled(False)
        self.toggle_button.setEnabled(False)
        close_button = secondary_button("Close")
        add_button.clicked.connect(self.add_category)
        self.edit_button.clicked.connect(self.edit_category)
        self.toggle_button.clicked.connect(self.toggle_category)
        self.table.itemSelectionChanged.connect(self._sync_actions)
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(18)
        title = QLabel("Categories")
        title.setProperty("role", "dialogTitle")
        subtitle = QLabel("Keep income and expense labels tidy without losing historical links.")
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        card, card_layout = create_card()
        card_layout.addWidget(
            toolbar(left=[add_button], right=[self.edit_button, self.toggle_button])
        )
        card_layout.addWidget(self.table, 1)
        layout.addWidget(card, 1)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(close_button)
        layout.addLayout(footer)
        self.refresh()

    def refresh(self) -> None:
        categories = self.service.list_categories(include_inactive=True)
        self.table.setRowCount(len(categories))
        for row, category in enumerate(categories):
            name = QTableWidgetItem(category.name)
            name.setData(256, category.id)
            self.table.setItem(row, 0, name)
            self.table.setCellWidget(
                row, 1, badge(pretty_type(category.type), badge_tone(category.type))
            )
            status = "Active" if category.is_active else "Archived"
            self.table.setCellWidget(
                row, 2, badge(status, "positive" if category.is_active else "muted")
            )
        self._sync_actions()

    def _sync_actions(self) -> None:
        selected = self._selected_category() is not None
        self.edit_button.setEnabled(selected)
        self.toggle_button.setEnabled(selected)

    def add_category(self) -> None:
        form = CategoryForm()
        if form.exec():
            try:
                self.service.create_category(**form.values())
                self._changed("Category created")
            except (ValueError, *DB_INTEGRITY_ERROR_TYPES) as exc:
                QMessageBox.warning(self, "Could not save category", str(exc))

    def edit_category(self) -> None:
        category = self._selected_category()
        if not category:
            return
        form = CategoryForm(category)
        if form.exec():
            try:
                self.service.update_category(category.id, **form.values())
                self._changed("Category updated")
            except (ValueError, *DB_INTEGRITY_ERROR_TYPES) as exc:
                QMessageBox.warning(self, "Could not save category", str(exc))

    def toggle_category(self) -> None:
        category = self._selected_category()
        if not category:
            return
        try:
            if category.is_active:
                self.service.archive_category(category.id)
                self._changed("Category archived")
            else:
                self.service.restore_category(category.id)
                self._changed("Category restored")
        except (ValueError, *DB_INTEGRITY_ERROR_TYPES) as exc:
            QMessageBox.warning(self, "Could not update category", str(exc))

    def _selected_category(self) -> Category | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        category_id = item.data(256) if item else None
        return self.service.categories.get(int(category_id)) if category_id else None

    def _changed(self, message: str) -> None:
        self.notify(message)
        self.refresh()
        self.on_changed({"transactions", "upcoming"})


class CategoryForm(QDialog):
    def __init__(
        self,
        category: Category | None = None,
        category_type: str | None = None,
        lock_type: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Category")
        self.name = QLineEdit(category.name if category else "")
        self.name.setPlaceholderText("Category name")
        self.type = QComboBox()
        self.type.addItem("Income", "income")
        self.type.addItem("Expense", "expense")
        if category:
            self.type.setCurrentIndex(self.type.findData(category.type))
        elif category_type:
            self.type.setCurrentIndex(self.type.findData(category_type))
        self.type.setEnabled(not lock_type)

        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Type", self.type)
        dialog_shell(
            self,
            "Edit category" if category else "New category",
            "Keep transaction groups consistent and easy to scan.",
            form,
            "Save category",
            "tag",
            minimum_width=440,
        )
        self.name.setFocus()

    def values(self) -> dict:
        return {"name": self.name.text(), "category_type": self.type.currentData()}


def create_category_dialog(
    parent,
    service: CategoryService,
    category_type: str,
) -> Category | None:
    form = CategoryForm(category_type=category_type, lock_type=True, parent=parent)
    if not form.exec():
        return None
    try:
        return service.create_category(**form.values())
    except (ValueError, *DB_INTEGRITY_ERROR_TYPES) as exc:
        QMessageBox.warning(parent, "Could not save category", str(exc))
        return None
