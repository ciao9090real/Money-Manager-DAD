from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFormLayout, QLabel, QLineEdit, QHBoxLayout, QVBoxLayout

from app.models.account import Account
from app.ui.components import pretty_type, primary_button, secondary_button


ACCOUNT_TYPES = [
    "bank",
    "current_account",
    "savings_account",
    "cash",
    "wallet",
    "benefit",
    "investment",
    "property",
    "credit_card",
    "loan",
    "mortgage",
    "liability",
    "other",
]


class AccountForm(QDialog):
    def __init__(self, accounts: list[Account], account: Account | None = None):
        super().__init__()
        self.setWindowTitle("Account")
        self.setMinimumWidth(500)
        self.account = account
        self.name = QLineEdit(account.name if account else "")
        self.name.setPlaceholderText("Account name")
        self.type = QComboBox()
        for account_type in ACCOUNT_TYPES:
            self.type.addItem(pretty_type(account_type), account_type)
        if account:
            type_index = self.type.findData(account.type)
            if type_index < 0:
                self.type.addItem(pretty_type(account.type), account.type)
                type_index = self.type.count() - 1
            self.type.setCurrentIndex(type_index)
        self.parent = QComboBox()
        self.parent.addItem("No parent", None)
        for item in accounts:
            if account and item.id == account.id:
                continue
            self.parent.addItem(item.name, item.id)
        if account and account.parent_id:
            index = self.parent.findData(account.parent_id)
            if index >= 0:
                self.parent.setCurrentIndex(index)
        self.opening_balance = QLineEdit(str(account.opening_balance if account else "0"))
        self.opening_balance.setPlaceholderText("0.00")
        self.opening_balance.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.active = QCheckBox("Active")
        self.active.setChecked(account.is_active if account else True)

        title = QLabel("Edit account" if account else "Add account")
        title.setProperty("role", "dialogTitle")
        subtitle = QLabel("Create a clear structure for banks, wallets, savings, assets, and liabilities.")
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)

        form = QFormLayout()
        form.setLabelAlignment(form.labelAlignment())
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.addRow("Name", self.name)
        form.addRow("Type", self.type)
        form.addRow("Parent", self.parent)
        form.addRow("Opening balance", self.opening_balance)
        form.addRow("", self.active)

        save = primary_button("Save account")
        save.setDefault(True)
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
        self.name.setFocus()

    def values(self) -> dict:
        return {
            "name": self.name.text(),
            "account_type": self.type.currentData(),
            "parent_id": self.parent.currentData(),
            "opening_balance": self.opening_balance.text(),
            "is_active": self.active.isChecked(),
        }
