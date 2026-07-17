from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from app.models.account import Account
from app.models.category import Category
from app.models.payment_method import PaymentMethod
from app.models.recurring_rule import RecurringRule
from app.services.category_service import CategoryService
from app.ui.category_manager import create_category_dialog
from app.ui.components import dialog_shell, ghost_button
from app.ui.date_picker import DatePicker


class RecurringRuleForm(QDialog):
    def __init__(
        self,
        accounts: list[Account],
        categories: list[Category],
        payment_methods: list[PaymentMethod],
        rule: RecurringRule | None = None,
        category_service: CategoryService | None = None,
    ):
        super().__init__()
        self.setWindowTitle("Recurring schedule")
        self.payment_methods = payment_methods
        self.categories = categories
        self.category_service = category_service
        self.current_payment_method_id = rule.payment_method_id if rule else None

        self.transaction_type = QComboBox()
        self.transaction_type.addItem("Money out", "expense")
        self.transaction_type.addItem("Money in", "income")
        self.name = QLineEdit(rule.name if rule else "")
        self.name.setPlaceholderText("Schedule name")
        self.kind = QComboBox()
        self._populate_kinds("expense")
        self.amount_mode = QComboBox()
        self.amount_mode.addItem("Fixed amount", "fixed")
        self.amount_mode.addItem("Variable amount", "variable")
        self.amount = QLineEdit()
        self.amount.setPlaceholderText("0.00")
        self.amount.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.account = QComboBox()
        for account in accounts:
            self.account.addItem(account.name, account.id)
        self.category = QComboBox()
        self.add_category_button = ghost_button("", "plus")
        self.add_category_button.setFixedSize(42, 42)
        self.add_category_button.setToolTip("Add expense category")
        self.add_category_button.setVisible(category_service is not None)
        self.add_category_button.clicked.connect(self._add_category)
        category_row = QWidget()
        category_layout = QHBoxLayout(category_row)
        category_layout.setContentsMargins(0, 0, 0, 0)
        category_layout.setSpacing(7)
        category_layout.addWidget(self.category, 1)
        category_layout.addWidget(self.add_category_button)
        self._populate_categories()
        self.payment_method = QComboBox()

        self.frequency = QComboBox()
        for key, label in (
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("yearly", "Yearly"),
        ):
            self.frequency.addItem(label, key)
        self.next_due_date = DatePicker(QDate.currentDate())

        self.end_enabled = QCheckBox("Ends")
        self.end_date = DatePicker(QDate.currentDate().addYears(1))
        self.end_date.setEnabled(False)
        end_row = QWidget()
        end_layout = QHBoxLayout(end_row)
        end_layout.setContentsMargins(0, 0, 0, 0)
        end_layout.setSpacing(10)
        end_layout.addWidget(self.end_enabled)
        end_layout.addWidget(self.end_date, 1)

        self.reminder_days = QSpinBox()
        self.reminder_days.setRange(0, 90)
        self.reminder_days.setValue(3)
        self.reminder_days.setSuffix(" days before")
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Optional notes")

        self.form = QFormLayout()
        self.form.addRow("Flow", self.transaction_type)
        self.form.addRow("Name", self.name)
        self.form.addRow("Type", self.kind)
        self.form.addRow("Amount behavior", self.amount_mode)
        self.form.addRow("Amount", self.amount)
        self.form.addRow("Pay from", self.account)
        self.form.addRow("Category", category_row)
        self.form.addRow("Payment method", self.payment_method)
        self.form.addRow("Frequency", self.frequency)
        self.form.addRow("Next due", self.next_due_date)
        self.form.addRow("Schedule", end_row)
        self.form.addRow("Reminder", self.reminder_days)
        self.form.addRow("Notes", self.notes)

        dialog_shell(
            self,
            "Edit recurring schedule" if rule else "Add recurring schedule",
            "Plan wages, subscriptions, and bills before they happen.",
            self.form,
            "Save schedule",
            "upcoming",
            minimum_width=540,
        )

        self.amount_mode.currentIndexChanged.connect(self._sync_amount_field)
        self.transaction_type.currentIndexChanged.connect(self._sync_transaction_type)
        self.account.currentIndexChanged.connect(self._populate_payment_methods)
        self.end_enabled.toggled.connect(self.end_date.setEnabled)
        if rule:
            self._load_rule(rule)
        else:
            self._populate_payment_methods()
        self._sync_transaction_type()
        self._sync_amount_field()
        self.name.setFocus()

    def values(self) -> dict:
        return {
            "name": self.name.text(),
            "transaction_type": self.transaction_type.currentData(),
            "kind": self.kind.currentData(),
            "amount_mode": self.amount_mode.currentData(),
            "amount": self.amount.text(),
            "account_id": self.account.currentData(),
            "category_id": self.category.currentData(),
            "payment_method_id": (
                self.payment_method.currentData()
                if self.transaction_type.currentData() == "expense"
                else None
            ),
            "frequency": self.frequency.currentData(),
            "next_due_date": self.next_due_date.date().toString("yyyy-MM-dd"),
            "end_date": (
                self.end_date.date().toString("yyyy-MM-dd")
                if self.end_enabled.isChecked()
                else None
            ),
            "reminder_days": self.reminder_days.value(),
            "notes": self.notes.text() or None,
        }

    def _load_rule(self, rule: RecurringRule) -> None:
        self._set_combo(self.transaction_type, rule.transaction_type)
        self._sync_transaction_type(rule.kind)
        self._set_combo(self.kind, rule.kind)
        self._set_combo(self.amount_mode, rule.amount_mode)
        self._set_combo(self.account, rule.account_id)
        self._set_combo(self.category, rule.category_id)
        self._set_combo(self.frequency, rule.frequency)
        if rule.amount is not None:
            self.amount.setText(str(rule.amount))
        due = QDate.fromString(rule.next_due_date, "yyyy-MM-dd")
        if due.isValid():
            self.next_due_date.setDate(due)
        if rule.end_date:
            end = QDate.fromString(rule.end_date, "yyyy-MM-dd")
            if end.isValid():
                self.end_date.setDate(end)
            self.end_enabled.setChecked(True)
        self.reminder_days.setValue(rule.reminder_days)
        self.notes.setText(rule.notes or "")
        self._populate_payment_methods()

    def _sync_amount_field(self) -> None:
        variable = self.amount_mode.currentData() == "variable"
        label = self.form.labelForField(self.amount)
        if label:
            label.setText("Expected amount" if variable else "Amount")
        self.amount.setPlaceholderText("Optional estimate" if variable else "0.00")

    def _sync_transaction_type(self, selected_kind: str | None = None) -> None:
        transaction_type = self.transaction_type.currentData() or "expense"
        income = transaction_type == "income"
        current_kind = selected_kind or self.kind.currentData()
        self._populate_kinds(transaction_type, current_kind)
        account_label = self.form.labelForField(self.account)
        if account_label:
            account_label.setText("Receive into" if income else "Pay from")
        self.form.setRowVisible(self.payment_method, not income)
        self.add_category_button.setToolTip(
            f"Add {transaction_type} category"
        )
        self._populate_categories()

    def _populate_payment_methods(self) -> None:
        selected = self.current_payment_method_id or self.payment_method.currentData()
        account_id = self.account.currentData()
        self.payment_method.blockSignals(True)
        self.payment_method.clear()
        self.payment_method.addItem("No payment method", None)
        for method in self.payment_methods:
            if method.account_id == account_id and (method.is_active or method.id == selected):
                label = method.name if method.is_active else f"{method.name} (archived)"
                self.payment_method.addItem(label, method.id)
        self._set_combo(self.payment_method, selected)
        self.current_payment_method_id = None
        self.payment_method.blockSignals(False)

    def _populate_categories(self, selected_id: str | None = None) -> None:
        selected = selected_id if selected_id is not None else self.category.currentData()
        self.category.clear()
        self.category.addItem("No category", None)
        transaction_type = self.transaction_type.currentData() or "expense"
        for category in self.categories:
            if category.type == transaction_type and category.is_active:
                self.category.addItem(category.name, category.id)
        self._set_combo(self.category, selected)

    def _add_category(self) -> None:
        if not self.category_service:
            return
        transaction_type = self.transaction_type.currentData() or "expense"
        category = create_category_dialog(self, self.category_service, transaction_type)
        if not category:
            return
        if all(existing.id != category.id for existing in self.categories):
            self.categories.append(category)
        self._populate_categories(category.id)

    def _populate_kinds(self, transaction_type: str, selected: str | None = None) -> None:
        self.kind.blockSignals(True)
        self.kind.clear()
        if transaction_type == "income":
            self.kind.addItem("Wage / income", "other")
        else:
            self.kind.addItem("Subscription", "subscription")
            self.kind.addItem("Bill", "bill")
            self.kind.addItem("Other recurring", "other")
        self._set_combo(self.kind, selected)
        self.kind.blockSignals(False)

    @staticmethod
    def _set_combo(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)


class RecordRecurringDialog(QDialog):
    def __init__(self, rule: RecurringRule):
        super().__init__()
        income = rule.transaction_type == "income"
        self.setWindowTitle("Record recurring income" if income else "Record recurring payment")
        self.amount = QLineEdit(str(rule.amount) if rule.amount is not None else "")
        self.amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.amount.setPlaceholderText("Actual amount")
        self.date = DatePicker(QDate.currentDate())

        form = QFormLayout()
        amount_label = "Actual amount" if rule.amount_mode == "variable" else "Amount"
        form.addRow(amount_label, self.amount)
        form.addRow("Income date" if income else "Payment date", self.date)
        dialog_shell(
            self,
            "Record income" if income else "Record payment",
            rule.name,
            form,
            "Record income" if income else "Record expense",
            "upcoming",
            minimum_width=460,
        )
        self.amount.setFocus()
        self.amount.selectAll()

    def values(self) -> dict:
        return {
            "actual_amount": self.amount.text(),
            "transaction_date": self.date.date().toString("yyyy-MM-dd"),
        }
