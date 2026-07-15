from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout

from app.models.account import Account
from app.models.payment_method import PaymentMethod
from app.ui.components import pretty_type, primary_button, secondary_button


class PaymentMethodForm(QDialog):
    def __init__(self, accounts: list[Account], payment_method: PaymentMethod | None = None):
        super().__init__()
        self.setWindowTitle("Payment method")
        self.setMinimumWidth(500)
        self.name = QLineEdit(payment_method.name if payment_method else "")
        self.name.setPlaceholderText("Payment method name")
        self.type = QComboBox()
        for payment_type in ("debit_card", "credit_card", "paypal", "wallet", "other"):
            self.type.addItem(pretty_type(payment_type), payment_type)
        if payment_method:
            type_index = self.type.findData(payment_method.type)
            if type_index < 0:
                self.type.addItem(pretty_type(payment_method.type), payment_method.type)
                type_index = self.type.count() - 1
            self.type.setCurrentIndex(type_index)
        self.account = QComboBox()
        for account in accounts:
            self.account.addItem(account.name, account.id)
        if payment_method:
            index = self.account.findData(payment_method.account_id)
            if index >= 0:
                self.account.setCurrentIndex(index)

        title = QLabel("Edit payment method" if payment_method else "Add payment method")
        title.setProperty("role", "dialogTitle")
        subtitle = QLabel("Add cards, PayPal, or other local payment methods under an account.")
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.addRow("Name", self.name)
        form.addRow("Type", self.type)
        form.addRow("Linked account", self.account)

        save = primary_button("Save payment method")
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
            "account_id": self.account.currentData(),
            "payment_type": self.type.currentData(),
        }
