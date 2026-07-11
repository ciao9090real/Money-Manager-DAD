from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout

from app.models.account import Account


class PaymentMethodForm(QDialog):
    def __init__(self, accounts: list[Account]):
        super().__init__()
        self.setWindowTitle("Payment method")
        self.name = QLineEdit()
        self.type = QComboBox()
        self.type.addItems(["debit_card", "credit_card", "paypal", "wallet", "other"])
        self.account = QComboBox()
        for account in accounts:
            self.account.addItem(account.name, account.id)

        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Type", self.type)
        form.addRow("Linked account", self.account)

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
            "account_id": self.account.currentData(),
            "payment_type": self.type.currentText(),
        }
