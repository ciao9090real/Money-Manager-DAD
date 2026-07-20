from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QWidget,
)

from app.models.account import Account
from app.models.goal import SavingsGoal
from app.ui.components import dialog_shell
from app.ui.date_picker import DatePicker


class GoalForm(QDialog):
    def __init__(
        self,
        accounts: list[Account],
        goal: SavingsGoal | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.goal = goal
        self.setWindowTitle("Savings goal")

        self.name = QLineEdit(goal.name if goal else "")
        self.name.setPlaceholderText("Goal name")
        self.target_amount = QLineEdit(str(goal.target_amount) if goal else "")
        self.target_amount.setPlaceholderText("0.00")
        self.target_amount.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.linked_account = QComboBox()
        self.linked_account.addItem("Manual contribution tracking", None)
        for account in accounts:
            self.linked_account.addItem(account.name, account.id)

        self.target_date_enabled = QCheckBox("Has target date")
        self.target_date = DatePicker(QDate.currentDate().addYears(1))
        self.target_date.setEnabled(False)
        date_row = QWidget()
        date_layout = QHBoxLayout(date_row)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(10)
        date_layout.addWidget(self.target_date_enabled)
        date_layout.addWidget(self.target_date, 1)

        if goal:
            account_index = self.linked_account.findData(goal.linked_account_id)
            if account_index >= 0:
                self.linked_account.setCurrentIndex(account_index)
            if goal.target_date:
                target = QDate.fromString(goal.target_date, "yyyy-MM-dd")
                if target.isValid():
                    self.target_date.setDate(target)
                self.target_date_enabled.setChecked(True)

        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Target amount", self.target_amount)
        form.addRow("Track from", self.linked_account)
        form.addRow("Target date", date_row)
        dialog_shell(
            self,
            "Edit savings goal" if goal else "Add savings goal",
            "Track an account balance or build progress with recorded contributions.",
            form,
            "Save goal",
            "investments",
            minimum_width=520,
        )
        self.target_date_enabled.toggled.connect(self.target_date.setEnabled)
        self.target_date.setEnabled(self.target_date_enabled.isChecked())
        self.name.setFocus()

    def values(self) -> dict:
        return {
            "name": self.name.text(),
            "target_amount": self.target_amount.text(),
            "target_date": (
                self.target_date.date().toString("yyyy-MM-dd")
                if self.target_date_enabled.isChecked()
                else None
            ),
            "linked_account_id": self.linked_account.currentData(),
        }


class GoalContributionDialog(QDialog):
    def __init__(
        self,
        goal: SavingsGoal,
        accounts: list[Account],
        parent=None,
    ):
        super().__init__(parent)
        self.goal = goal
        self.setWindowTitle("Add goal contribution")

        self.source_account = QComboBox()
        self.target_account = QComboBox()
        for account in accounts:
            self.target_account.addItem(account.name, account.id)
            if not goal.linked_account_id or account.id != goal.linked_account_id:
                self.source_account.addItem(account.name, account.id)

        if goal.linked_account_id:
            target_index = self.target_account.findData(goal.linked_account_id)
            if target_index >= 0:
                self.target_account.setCurrentIndex(target_index)
            self.target_account.setEnabled(False)
        else:
            self.source_account.currentIndexChanged.connect(self._avoid_same_account)
            self._avoid_same_account()

        self.amount = QLineEdit()
        self.amount.setPlaceholderText("0.00")
        self.amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.contribution_date = DatePicker(QDate.currentDate())
        self.contribution_date.setMaximumDate(QDate.currentDate())
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Optional notes")

        form = QFormLayout()
        form.addRow("Move from", self.source_account)
        form.addRow("Save into", self.target_account)
        form.addRow("Amount", self.amount)
        form.addRow("Date", self.contribution_date)
        form.addRow("Notes", self.notes)
        dialog_shell(
            self,
            "Add contribution",
            goal.name,
            form,
            "Record contribution",
            "transactions",
            minimum_width=500,
        )
        self.amount.setFocus()

    def values(self) -> dict:
        return {
            "source_account_id": self.source_account.currentData(),
            "target_account_id": self.target_account.currentData(),
            "amount": self.amount.text(),
            "contribution_date": self.contribution_date.date().toString("yyyy-MM-dd"),
            "notes": self.notes.text() or None,
        }

    def _avoid_same_account(self) -> None:
        source_id = self.source_account.currentData()
        if source_id is None or self.target_account.currentData() != source_id:
            return
        for index in range(self.target_account.count()):
            if self.target_account.itemData(index) != source_id:
                self.target_account.setCurrentIndex(index)
                return
