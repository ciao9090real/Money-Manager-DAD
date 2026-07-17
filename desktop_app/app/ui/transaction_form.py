from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QWidget,
)

from app.models.account import Account
from app.models.category import Category
from app.models.payment_method import PaymentMethod
from app.models.transaction import Transaction
from app.services.category_service import CategoryService
from app.ui.category_manager import create_category_dialog
from app.ui.components import dialog_shell, ghost_button
from app.ui.date_picker import DatePicker


class TransactionForm(QDialog):
    def __init__(
        self,
        accounts: list[Account],
        categories: list[Category] | None = None,
        payment_methods: list[PaymentMethod] | None = None,
        transaction: Transaction | None = None,
        transfer_source_id: str | None = None,
        transfer_target_id: str | None = None,
        category_service: CategoryService | None = None,
    ):
        super().__init__()
        self.setWindowTitle("Transaction")
        self.categories = categories or []
        self.category_service = category_service
        self.payment_methods = payment_methods or []
        self.current_category_id = transaction.category_id if transaction else None
        self.current_payment_method_id = transaction.payment_method_id if transaction else None
        self.type = QComboBox()
        for key, label in (("income", "Income"), ("expense", "Expense"), ("transfer", "Transfer"), ("adjustment", "Adjustment")):
            self.type.addItem(label, key)
        self.account = QComboBox()
        self.target_account = QComboBox()
        for account in accounts:
            self.account.addItem(account.name, account.id)
            self.target_account.addItem(account.name, account.id)
        self.category = QComboBox()
        self.category.setEditable(True)
        self.add_category_button = ghost_button("", "plus")
        self.add_category_button.setFixedSize(42, 42)
        self.add_category_button.setToolTip("Add category")
        self.add_category_button.setVisible(category_service is not None)
        self.add_category_button.clicked.connect(self._add_category)
        self.category_row = QWidget()
        category_layout = QHBoxLayout(self.category_row)
        category_layout.setContentsMargins(0, 0, 0, 0)
        category_layout.setSpacing(7)
        category_layout.addWidget(self.category, 1)
        category_layout.addWidget(self.add_category_button)
        self.payment_method = QComboBox()
        self.date = DatePicker(QDate.currentDate())
        self.amount = QLineEdit()
        self.amount.setPlaceholderText("0.00")
        self.amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.description = QLineEdit()
        self.description.setPlaceholderText("Description")
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Optional notes")

        self.form = QFormLayout()
        self.form.addRow("Type", self.type)
        self.form.addRow("Account", self.account)
        self.form.addRow("Transfer target", self.target_account)
        self.form.addRow("Category", self.category_row)
        self.form.addRow("Payment method", self.payment_method)
        self.form.addRow("Date", self.date)
        self.form.addRow("Amount", self.amount)
        self.form.addRow("Description", self.description)
        self.form.addRow("Notes", self.notes)

        dialog_shell(
            self,
            "Edit transaction" if transaction else "Add transaction",
            "Record income, spending, transfers, or a balance adjustment.",
            self.form,
            "Save transaction" if transaction else "Add transaction",
            "transactions",
            minimum_width=540,
        )
        self.type.currentIndexChanged.connect(self._sync_type_fields)
        self.account.currentIndexChanged.connect(self._populate_payment_methods)
        if transaction:
            self._load_transaction(transaction, transfer_source_id, transfer_target_id)
        self._sync_type_fields()
        self.amount.setFocus()

    def values(self) -> dict:
        category_data = self.category.currentData()
        category_value = None
        if self.category.isVisible():
            category_text = self.category.currentText().strip()
            if category_data is not None:
                category_value = category_data
            elif category_text and category_text != "No category":
                category_value = category_text
        return {
            "type": self.type.currentData(),
            "account_id": self.account.currentData(),
            "target_account_id": self.target_account.currentData(),
            "category": category_value,
            "payment_method_id": self.payment_method.currentData(),
            "date": self.date.date().toString("yyyy-MM-dd"),
            "amount": self.amount.text(),
            "description": self.description.text(),
            "notes": self.notes.text() or None,
        }

    def _sync_type_fields(self) -> None:
        transaction_type = self.type.currentData()
        self._set_row_visible(self.target_account, transaction_type == "transfer")
        self._set_row_visible(self.category_row, transaction_type in {"income", "expense"})
        self._set_row_visible(self.payment_method, transaction_type in {"income", "expense"})
        self._populate_categories(transaction_type)
        self._populate_payment_methods()

    def _populate_categories(self, transaction_type: str) -> None:
        previous_id = self.category.currentData()
        previous_text = self.category.currentText().strip()
        if self.current_category_id is not None:
            previous_id = self.current_category_id
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem("No category", None)
        for category in self.categories:
            if category.type == transaction_type:
                self.category.addItem(category.name, category.id)
        if previous_id is not None:
            self._set_combo_by_data(self.category, previous_id)
        elif previous_text and previous_text != "No category":
            self.category.setEditText(previous_text)
        self.current_category_id = None
        self.category.blockSignals(False)

    def _add_category(self) -> None:
        transaction_type = self.type.currentData()
        if not self.category_service or transaction_type not in {"income", "expense"}:
            return
        category = create_category_dialog(self, self.category_service, transaction_type)
        if not category:
            return
        if all(existing.id != category.id for existing in self.categories):
            self.categories.append(category)
        self.current_category_id = category.id
        self._populate_categories(transaction_type)

    def _populate_payment_methods(self) -> None:
        previous_id = self.payment_method.currentData()
        if self.current_payment_method_id is not None:
            previous_id = self.current_payment_method_id
        account_id = self.account.currentData()
        self.payment_method.blockSignals(True)
        self.payment_method.clear()
        self.payment_method.addItem("No payment method", None)
        for method in self.payment_methods:
            if method.account_id == account_id and (method.is_active or method.id == previous_id):
                label = method.name if method.is_active else f"{method.name} (archived)"
                self.payment_method.addItem(label, method.id)
        if previous_id is not None:
            self._set_combo_by_data(self.payment_method, previous_id)
        self.current_payment_method_id = None
        self.payment_method.blockSignals(False)

    def _load_transaction(self, transaction: Transaction, transfer_source_id: str | None, transfer_target_id: str | None) -> None:
        transaction_type = "transfer" if transaction.type in {"transfer_out", "transfer_in"} else transaction.type
        self._set_combo_by_data(self.type, transaction_type)
        account_id = transfer_source_id if transaction_type == "transfer" and transfer_source_id is not None else transaction.account_id
        target_id = transfer_target_id if transfer_target_id is not None else transaction.account_id
        self._set_combo_by_data(self.account, account_id)
        self._set_combo_by_data(self.target_account, target_id)
        loaded_date = QDate.fromString(transaction.date, "yyyy-MM-dd")
        if loaded_date.isValid():
            self.date.setDate(loaded_date)
        amount = abs(transaction.amount) if transaction_type in {"income", "expense", "transfer"} else transaction.amount
        self.amount.setText(str(amount))
        self.description.setText(transaction.description or "")
        self.notes.setText(transaction.notes or "")

    def _set_row_visible(self, widget, visible: bool) -> None:
        label = self.form.labelForField(widget)
        if label:
            label.setVisible(visible)
        widget.setVisible(visible)

    def _set_combo_by_data(self, combo: QComboBox, data: object) -> None:
        index = combo.findData(data)
        if index >= 0:
            combo.setCurrentIndex(index)
