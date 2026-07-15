from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QLineEdit

from app.models.account import Account
from app.models.payment_method import PaymentMethod
from app.ui.components import dialog_shell, pretty_type


class PaymentMethodForm(QDialog):
    def __init__(self, accounts: list[Account], payment_method: PaymentMethod | None = None):
        super().__init__()
        self.setWindowTitle("Payment method")
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

        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Type", self.type)
        form.addRow("Linked account", self.account)
        dialog_shell(
            self,
            "Edit payment method" if payment_method else "Add payment method",
            "Link cards, PayPal, or wallets to the account they use.",
            form,
            "Save payment method",
            "accounts",
            minimum_width=480,
        )
        self.name.setFocus()

    def values(self) -> dict:
        return {
            "name": self.name.text(),
            "account_id": self.account.currentData(),
            "payment_type": self.type.currentData(),
        }
