from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout

from app.models.account import Account


ACCOUNT_TYPES = ["bank", "current_account", "savings_account", "cash", "wallet", "benefit", "payment_method", "other"]


class AccountForm(QDialog):
    def __init__(self, accounts: list[Account], account: Account | None = None):
        super().__init__()
        self.setWindowTitle("Account")
        self.account = account
        self.name = QLineEdit(account.name if account else "")
        self.type = QComboBox()
        self.type.addItems(ACCOUNT_TYPES)
        if account and account.type in ACCOUNT_TYPES:
            self.type.setCurrentText(account.type)
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
        self.active = QCheckBox("Active")
        self.active.setChecked(account.is_active if account else True)

        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Type", self.type)
        form.addRow("Parent", self.parent)
        form.addRow("Opening balance", self.opening_balance)
        form.addRow("", self.active)

        save = QPushButton("Save")
        cancel = QPushButton("Cancel")
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(save)
        buttons.addWidget(cancel)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)

    def values(self) -> dict:
        return {
            "name": self.name.text(),
            "account_type": self.type.currentText(),
            "parent_id": self.parent.currentData(),
            "opening_balance": self.opening_balance.text(),
            "is_active": self.active.isChecked(),
        }

