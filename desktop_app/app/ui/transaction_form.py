from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QComboBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout

from app.models.account import Account
from app.ui.components import primary_button, secondary_button
from app.ui.theme import Spacing


class TransactionForm(QDialog):
    def __init__(self, accounts: list[Account]):
        super().__init__()
        self.setWindowTitle("Transaction")
        self.setMinimumWidth(480)
        self.type = QComboBox()
        self.type.addItems(["income", "expense", "transfer", "adjustment"])
        self.account = QComboBox()
        self.target_account = QComboBox()
        for account in accounts:
            self.account.addItem(account.name, account.id)
            self.target_account.addItem(account.name, account.id)
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.amount = QLineEdit()
        self.description = QLineEdit()
        self.notes = QLineEdit()

        title = QLabel("Add transaction")
        title.setProperty("role", "pageTitle")
        subtitle = QLabel("Manual income, expenses, transfers, and adjustments only.")
        subtitle.setProperty("role", "subtitle")

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.addRow("Type", self.type)
        form.addRow("Account", self.account)
        form.addRow("Transfer target", self.target_account)
        form.addRow("Date", self.date)
        form.addRow("Amount", self.amount)
        form.addRow("Description", self.description)
        form.addRow("Notes", self.notes)

        save = primary_button("Save transaction")
        cancel = secondary_button("Cancel")
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(save)
        buttons.addWidget(cancel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.PAGE, Spacing.PAGE, Spacing.PAGE, Spacing.PAGE)
        layout.setSpacing(Spacing.GAP)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(form)
        layout.addLayout(buttons)

    def values(self) -> dict:
        return {
            "type": self.type.currentText(),
            "account_id": self.account.currentData(),
            "target_account_id": self.target_account.currentData(),
            "date": self.date.date().toString("yyyy-MM-dd"),
            "amount": self.amount.text(),
            "description": self.description.text(),
            "notes": self.notes.text() or None,
        }
