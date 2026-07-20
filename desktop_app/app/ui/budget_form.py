from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFormLayout, QLineEdit

from app.models.budget import Budget
from app.models.category import Category
from app.ui.components import dialog_shell
from app.ui.date_picker import DatePicker


class BudgetForm(QDialog):
    def __init__(
        self,
        categories: list[Category],
        budget: Budget | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.budget = budget
        self.setWindowTitle("Budget")

        self.category = QComboBox()
        for category in categories:
            label = category.name if category.is_active else f"{category.name} (archived)"
            self.category.addItem(label, category.id)

        self.amount = QLineEdit(str(budget.amount) if budget else "")
        self.amount.setPlaceholderText("0.00")
        self.amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.rollover = QCheckBox("Carry unused money into the next month")
        self.rollover.setChecked(bool(budget and budget.rollover))
        self.start_date = DatePicker(QDate.currentDate())

        if budget:
            category_index = self.category.findData(budget.category_id)
            if category_index >= 0:
                self.category.setCurrentIndex(category_index)
            started = QDate.fromString(budget.start_date, "yyyy-MM-dd")
            if started.isValid():
                self.start_date.setDate(started)
            # A budget is unique per category. Changing its category would create
            # a different budget rather than editing the selected one.
            self.category.setEnabled(False)

        form = QFormLayout()
        form.addRow("Expense category", self.category)
        form.addRow("Monthly limit", self.amount)
        form.addRow("Starts", self.start_date)
        form.addRow("", self.rollover)
        dialog_shell(
            self,
            "Edit budget" if budget else "Add budget",
            "Set a monthly spending limit and optionally carry unused money forward.",
            form,
            "Save budget",
            "transactions",
            minimum_width=500,
        )
        self.amount.setFocus()
        if budget:
            self.amount.selectAll()

    def values(self) -> dict:
        return {
            "category_id": self.category.currentData(),
            "amount": self.amount.text(),
            "rollover": self.rollover.isChecked(),
            "start_date": self.start_date.date().toString("yyyy-MM-dd"),
        }
