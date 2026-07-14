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

from app.models.category import Category
from app.services.category_service import CategoryService
from app.ui.components import (
    create_card,
    ghost_button,
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
        edit_button = ghost_button("Edit", "edit")
        toggle_button = soft_button("Archive / restore", "archive")
        close_button = secondary_button("Close")
        add_button.clicked.connect(self.add_category)
        edit_button.clicked.connect(self.edit_category)
        toggle_button.clicked.connect(self.toggle_category)
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
        card_layout.addWidget(toolbar(left=[add_button], right=[edit_button, toggle_button]))
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
            values = (category.name, category.type.title(), "Active" if category.is_active else "Archived")
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(256, category.id)
                self.table.setItem(row, column, item)

    def add_category(self) -> None:
        form = CategoryForm()
        if form.exec():
            try:
                self.service.create_category(**form.values())
                self._changed("Category created")
            except (ValueError, sqlite3.IntegrityError) as exc:
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
            except (ValueError, sqlite3.IntegrityError) as exc:
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
        except (ValueError, sqlite3.IntegrityError) as exc:
            QMessageBox.warning(self, "Could not update category", str(exc))

    def _selected_category(self) -> Category | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        category_id = item.data(256) if item else None
        return self.service.categories.get(int(category_id)) if category_id else None

    def _changed(self, message: str) -> None:
        self.notify(message)
        self.refresh()
        self.on_changed({"transactions"})


class CategoryForm(QDialog):
    def __init__(self, category: Category | None = None):
        super().__init__()
        self.setWindowTitle("Category")
        self.setMinimumWidth(440)
        self.name = QLineEdit(category.name if category else "")
        self.type = QComboBox()
        self.type.addItems(["income", "expense"])
        if category:
            self.type.setCurrentText(category.type)

        title = QLabel("Edit category" if category else "New category")
        title.setProperty("role", "dialogTitle")
        subtitle = QLabel("Categories make reports and transaction lists easier to understand.")
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Type", self.type)
        save = primary_button("Save category")
        cancel = secondary_button("Cancel")
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(18)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(form)
        layout.addLayout(buttons)

    def values(self) -> dict:
        return {"name": self.name.text(), "category_type": self.type.currentText()}
