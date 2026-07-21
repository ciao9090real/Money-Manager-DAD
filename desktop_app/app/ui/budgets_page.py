from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from app.core.database_security import DB_INTEGRITY_ERROR_TYPES
from app.models.budget import Budget, BudgetStatus
from app.models.category import Category
from app.services.budget_service import BudgetService
from app.services.category_service import CategoryService
from app.ui.budget_form import BudgetForm
from app.ui.components import (
    amount_item,
    badge,
    create_card,
    empty_state,
    fit_item_view_height,
    ghost_button,
    page_layout,
    primary_button,
    soft_button,
    style_table,
)
from app.ui.theme import Colors


class BudgetProgress(QWidget):
    """Compact budget progress display suitable for a table cell."""

    WARNING_AT = Decimal("80")
    OVERSPENT_AT = Decimal("100")

    def __init__(
        self,
        percent_used: Decimal,
        *,
        started: bool = True,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(9)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.label.setMinimumWidth(66)
        self.label.setProperty("role", "count")
        layout.addWidget(self.bar, 1)
        layout.addWidget(self.label)

        self.set_progress(percent_used, started=started)

    def set_progress(self, percent_used: Decimal, *, started: bool = True) -> None:
        percent = Decimal(percent_used)
        clamped = max(Decimal("0"), min(Decimal("100"), percent))
        self.bar.setValue(int(clamped))

        if not started:
            color = Colors.TEXT_MUTED
            self.label.setText("Not started")
            self.setToolTip("This budget starts in a future month")
        elif percent > self.OVERSPENT_AT:
            color = Colors.NEGATIVE
            self.label.setText(f"{self._format_percent(percent)}%")
            self.setToolTip("This budget is over its monthly limit")
        elif percent >= self.WARNING_AT:
            color = Colors.WARNING
            self.label.setText(f"{self._format_percent(percent)}%")
            self.setToolTip("This budget is close to its monthly limit")
        else:
            color = Colors.POSITIVE
            self.label.setText(f"{self._format_percent(percent)}%")
            self.setToolTip("Monthly budget used")

        self.label.setStyleSheet(f"color: {color}; font-weight: 600;")
        self.bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: {Colors.BORDER_SOFT};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background: {color};
                border-radius: 4px;
            }}
            """
        )

    @staticmethod
    def _format_percent(value: Decimal) -> str:
        if value == value.to_integral_value():
            return str(value.quantize(Decimal("1")))
        return f"{value.quantize(Decimal('0.1')):.1f}"


class BudgetsPage(QWidget):
    def __init__(self, db: sqlite3.Connection, on_changed, notify=None):
        super().__init__()
        self.service = BudgetService(db)
        self.categories = CategoryService(db)
        self.on_changed = on_changed
        self.notify = notify or (lambda _message: None)
        self._budgets_by_id: dict[str, Budget] = {}

        add_button = primary_button("Add budget", "plus")
        add_button.clicked.connect(self.add_budget)
        layout = page_layout(
            self,
            "Budgets",
            "Set monthly category limits and see where your spending stands today",
            add_button,
        )
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Category", "Limit", "Spent", "Remaining", "Used", "Rollover"]
        )
        style_table(self.table)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._sync_actions)
        self.table.itemDoubleClicked.connect(lambda _item: self.edit_budget())

        self.result_label = QLabel()
        self.result_label.setProperty("role", "count")
        self.edit_button = ghost_button("Edit", "edit")
        self.archive_button = soft_button("Archive", "archive")
        self.edit_button.setEnabled(False)
        self.archive_button.setEnabled(False)
        self.edit_button.clicked.connect(self.edit_budget)
        self.archive_button.clicked.connect(self.archive_budget)

        controls = QFrame()
        controls.setProperty("role", "toolbar")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(8, 7, 8, 7)
        controls_layout.setSpacing(7)
        controls_layout.addWidget(self.result_label)
        controls_layout.addStretch()
        controls_layout.addWidget(self.edit_button)
        controls_layout.addWidget(self.archive_button)

        card, card_layout = create_card(
            "This month's budgets",
            subtitle="Green is comfortable, amber is close to the limit, and red is over budget",
        )
        self.budget_card = card
        card_layout.addWidget(controls)
        empty_action = primary_button("Add budget", "plus")
        empty_action.clicked.connect(self.add_budget)
        self.empty = empty_state(
            "No active budgets",
            "Add a monthly limit for one of your expense categories.",
            empty_action,
        )
        card_layout.addWidget(self.empty)
        card_layout.addWidget(self.table)
        layout.addWidget(card, 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "table"):
            self.table.setColumnHidden(5, self.width() < 900)
            self.table.setColumnHidden(2, self.width() < 740)

    def refresh(self) -> None:
        selected = self._selected_budget()
        selected_id = selected.id if selected else None
        categories = {
            category.id: category
            for category in self.categories.list_categories(include_inactive=True)
        }
        budgets = self.service.list_budgets(active_only=True)
        statuses = {
            status.budget.id: status
            for status in self.service.status_for_period()
            if status.budget.id is not None
        }
        budgets.sort(
            key=lambda budget: (
                categories.get(budget.category_id).name.casefold()
                if categories.get(budget.category_id)
                else budget.category_id.casefold()
            )
        )
        self._budgets_by_id = {
            budget.id: budget for budget in budgets if budget.id is not None
        }

        self.table.setRowCount(len(budgets))
        selected_row = -1
        for row, budget in enumerate(budgets):
            category = categories.get(budget.category_id)
            status = statuses.get(budget.id)
            self._populate_row(row, budget, category, status)
            if budget.id == selected_id:
                selected_row = row

        if selected_row >= 0:
            self.table.selectRow(selected_row)
        self.result_label.setText(
            f"{len(budgets)} active budget{'s' if len(budgets) != 1 else ''}"
        )
        has_budgets = bool(budgets)
        self.empty.setVisible(not has_budgets)
        self.table.setVisible(has_budgets)
        if has_budgets and len(budgets) <= 9:
            fit_item_view_height(self.table, len(budgets), maximum_rows=9)
            self.budget_card.setMaximumHeight(175 + self.table.maximumHeight())
        elif has_budgets:
            self.table.setMaximumHeight(16777215)
            self.table.setMinimumHeight(320)
            self.budget_card.setMaximumHeight(16777215)
        else:
            self.budget_card.setMaximumHeight(310)
        self._sync_actions()

    def _populate_row(
        self,
        row: int,
        budget: Budget,
        category: Category | None,
        status: BudgetStatus | None,
    ) -> None:
        name = category.name if category else "Unknown category"
        name_item = QTableWidgetItem(name)
        name_item.setData(Qt.ItemDataRole.UserRole, budget.id)
        started = status is not None
        if not started:
            name_item.setToolTip(f"Starts {budget.start_date}")
        self.table.setItem(row, 0, name_item)

        limit = status.limit if status else budget.amount
        spent = status.spent if status else Decimal("0.00")
        remaining = status.remaining if status else budget.amount
        percent = status.percent_used if status else Decimal("0.00")
        self.table.setItem(row, 1, amount_item(limit, neutral=True))
        self.table.setItem(row, 2, amount_item(spent, neutral=True))
        self.table.setItem(row, 3, amount_item(remaining))
        self.table.setCellWidget(row, 4, BudgetProgress(percent, started=started))
        self.table.setCellWidget(
            row,
            5,
            badge("On" if budget.rollover else "Off", "info" if budget.rollover else "muted"),
        )

    def add_budget(self) -> None:
        categories = self._expense_categories()
        if not categories:
            QMessageBox.information(
                self,
                "No expense categories",
                "Create an expense category before adding a budget.",
            )
            return
        form = BudgetForm(categories, parent=self)
        if form.exec():
            try:
                self.service.set_budget(**form.values())
                self._changed("Budget saved")
            except (ValueError, *DB_INTEGRITY_ERROR_TYPES) as exc:
                QMessageBox.warning(self, "Could not save budget", str(exc))

    def edit_budget(self) -> None:
        budget = self._selected_budget()
        if not budget:
            return
        categories = [
            category
            for category in self.categories.list_categories(include_inactive=True)
            if category.type == "expense"
        ]
        form = BudgetForm(categories, budget, self)
        if form.exec():
            try:
                self.service.set_budget(**form.values())
                self._changed("Budget updated")
            except (ValueError, *DB_INTEGRITY_ERROR_TYPES) as exc:
                QMessageBox.warning(self, "Could not update budget", str(exc))

    def archive_budget(self) -> None:
        budget = self._selected_budget()
        if not budget or budget.id is None:
            return
        try:
            self.service.set_active(budget.id, False)
            self._changed("Budget archived")
        except (ValueError, *DB_INTEGRITY_ERROR_TYPES) as exc:
            QMessageBox.warning(self, "Could not archive budget", str(exc))

    def _expense_categories(self) -> list[Category]:
        return [
            category
            for category in self.categories.list_categories()
            if category.type == "expense"
        ]

    def _selected_budget(self) -> Budget | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        budget_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        return self._budgets_by_id.get(str(budget_id)) if budget_id else None

    def _sync_actions(self) -> None:
        selected = self._selected_budget() is not None
        self.edit_button.setEnabled(selected)
        self.archive_button.setEnabled(selected)

    def _changed(self, message: str) -> None:
        self.notify(message)
        self.refresh()
        self.on_changed({"budgets", "dashboard"})
