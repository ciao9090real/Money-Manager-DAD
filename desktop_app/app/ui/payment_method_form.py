from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout

from app.models.account import Account
from app.ui.components import primary_button, secondary_button
from app.ui.theme import Spacing


class PaymentMethodForm(QDialog):
    def __init__(self, accounts: list[Account]):
        super().__init__()
        self.setWindowTitle("Payment method")
        self.setMinimumWidth(440)
        self.name = QLineEdit()
        self.type = QComboBox()
        self.type.addItems(["debit_card", "credit_card", "paypal", "wallet", "other"])
        self.account = QComboBox()
        for account in accounts:
            self.account.addItem(account.name, account.id)

        title = QLabel("Add payment method")
        title.setProperty("role", "pageTitle")
        subtitle = QLabel("Add cards, PayPal, or other local payment methods under an account.")
        subtitle.setProperty("role", "subtitle")

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.addRow("Name", self.name)
        form.addRow("Type", self.type)
        form.addRow("Linked account", self.account)

        save = primary_button("Save payment method")
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
            "name": self.name.text(),
            "account_id": self.account.currentData(),
            "payment_type": self.type.currentText(),
        }
