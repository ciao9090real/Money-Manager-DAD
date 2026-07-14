from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QComboBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout

from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction
from app.ui.components import primary_button, secondary_button
from app.ui.theme import Spacing


class TransactionForm(QDialog):
    def __init__(
        self,
        accounts: list[Account],
        categories: list[Category] | None = None,
        transaction: Transaction | None = None,
        transfer_source_id: int | None = None,
        transfer_target_id: int | None = None,
    ):
        super().__init__()
        self.setWindowTitle("Transaction")
        self.setMinimumWidth(480)
        self.categories = categories or []
        self.current_category_id = transaction.category_id if transaction else None
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
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.amount = QLineEdit()
        self.description = QLineEdit()
        self.notes = QLineEdit()

        title = QLabel("Edit transaction" if transaction else "Add transaction")
        title.setProperty("role", "pageTitle")
        subtitle = QLabel("Manual income, expenses, transfers, and adjustments only.")
        subtitle.setProperty("role", "subtitle")

        self.form = QFormLayout()
        self.form.setHorizontalSpacing(16)
        self.form.setVerticalSpacing(12)
        self.form.addRow("Type", self.type)
        self.form.addRow("Account", self.account)
        self.form.addRow("Transfer target", self.target_account)
        self.form.addRow("Category", self.category)
        self.form.addRow("Date", self.date)
        self.form.addRow("Amount", self.amount)
        self.form.addRow("Description", self.description)
        self.form.addRow("Notes", self.notes)

        save = primary_button("Save transaction" if transaction else "Add transaction")
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
        layout.addLayout(self.form)
        layout.addLayout(buttons)
        self.type.currentIndexChanged.connect(self._sync_type_fields)
        if transaction:
            self._load_transaction(transaction, transfer_source_id, transfer_target_id)
        self._sync_type_fields()

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
            "date": self.date.date().toString("yyyy-MM-dd"),
            "amount": self.amount.text(),
            "description": self.description.text(),
            "notes": self.notes.text() or None,
        }

    def _sync_type_fields(self) -> None:
        transaction_type = self.type.currentData()
        self._set_row_visible(self.target_account, transaction_type == "transfer")
        self._set_row_visible(self.category, transaction_type in {"income", "expense"})
        self._populate_categories(transaction_type)

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

    def _load_transaction(self, transaction: Transaction, transfer_source_id: int | None, transfer_target_id: int | None) -> None:
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
