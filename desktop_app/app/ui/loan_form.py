from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QWidget,
)

from app.models.account import Account
from app.models.loan import Loan, LoanSnapshot
from app.ui.components import dialog_shell
from app.utils.money import format_money


class LoanForm(QDialog):
    def __init__(self, accounts: list[Account], loan: Loan | None = None):
        super().__init__()
        self.loan = loan
        self.setWindowTitle("Loan")

        self.direction = QComboBox()
        self.direction.addItem("Borrowed", "borrowed")
        self.direction.addItem("Lent", "lent")
        self.name = QLineEdit(loan.name if loan else "")
        self.name.setPlaceholderText("Loan name")
        self.counterparty = QLineEdit(loan.counterparty if loan else "")
        self.counterparty.setPlaceholderText("Bank, person, or organization")
        self.account = QComboBox()
        for account in accounts:
            self.account.addItem(account.name, account.id)
        self.principal = QLineEdit(str(loan.principal) if loan else "")
        self.principal.setPlaceholderText("0.00")
        self.principal.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.interest_rate = QDoubleSpinBox()
        self.interest_rate.setRange(0, 100)
        self.interest_rate.setDecimals(2)
        self.interest_rate.setSingleStep(0.25)
        self.interest_rate.setSuffix(" %")
        self.interest_rate.setToolTip(
            "Reference only. Outstanding balances and payments track principal, not accrued interest."
        )
        self.start_date = QDateEdit(QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd MMM yyyy")
        self.due_enabled = QCheckBox("Has due date")
        self.due_date = QDateEdit(QDate.currentDate().addYears(1))
        self.due_date.setCalendarPopup(True)
        self.due_date.setDisplayFormat("dd MMM yyyy")
        self.due_date.setEnabled(False)
        due_row = QWidget()
        due_layout = QHBoxLayout(due_row)
        due_layout.setContentsMargins(0, 0, 0, 0)
        due_layout.setSpacing(10)
        due_layout.addWidget(self.due_enabled)
        due_layout.addWidget(self.due_date, 1)
        self.notes = QLineEdit(loan.notes if loan else "")
        self.notes.setPlaceholderText("Optional notes")

        self.form = QFormLayout()
        self.form.addRow("Direction", self.direction)
        self.form.addRow("Name", self.name)
        self.form.addRow("Lender", self.counterparty)
        self.form.addRow("Receive into", self.account)
        self.form.addRow("Principal", self.principal)
        self.form.addRow("Reference rate", self.interest_rate)
        self.form.addRow("Start date", self.start_date)
        self.form.addRow("Due", due_row)
        self.form.addRow("Notes", self.notes)

        dialog_shell(
            self,
            "Edit loan" if loan else "Add loan",
            "Principal-only tracking. The reference rate is informational and is not accrued.",
            self.form,
            "Save loan" if loan else "Add loan",
            "loans",
            minimum_width=540,
        )

        self.direction.currentIndexChanged.connect(self._sync_direction)
        self.due_enabled.toggled.connect(self.due_date.setEnabled)
        if loan:
            self._load_loan(loan)
            for field in (self.direction, self.account, self.principal, self.start_date):
                field.setEnabled(False)
        self._sync_direction()
        self.name.setFocus()

    def create_values(self) -> dict:
        return {
            "direction": self.direction.currentData(),
            "name": self.name.text(),
            "counterparty": self.counterparty.text(),
            "account_id": self.account.currentData(),
            "principal": self.principal.text(),
            "interest_rate": self.interest_rate.value(),
            "start_date": self.start_date.date().toString("yyyy-MM-dd"),
            "due_date": self._due_value(),
            "notes": self.notes.text() or None,
        }

    def edit_values(self) -> dict:
        return {
            "name": self.name.text(),
            "counterparty": self.counterparty.text(),
            "interest_rate": self.interest_rate.value(),
            "due_date": self._due_value(),
            "notes": self.notes.text() or None,
        }

    def _load_loan(self, loan: Loan) -> None:
        self._set_combo(self.direction, loan.direction)
        self._set_combo(self.account, loan.account_id)
        self.interest_rate.setValue(float(loan.interest_rate))
        started = QDate.fromString(loan.start_date, "yyyy-MM-dd")
        if started.isValid():
            self.start_date.setDate(started)
        if loan.due_date:
            due = QDate.fromString(loan.due_date, "yyyy-MM-dd")
            if due.isValid():
                self.due_date.setDate(due)
            self.due_enabled.setChecked(True)

    def _sync_direction(self) -> None:
        borrowed = self.direction.currentData() == "borrowed"
        counterparty_label = self.form.labelForField(self.counterparty)
        account_label = self.form.labelForField(self.account)
        if counterparty_label:
            counterparty_label.setText("Lender" if borrowed else "Borrower")
        if account_label:
            account_label.setText("Receive into" if borrowed else "Pay from")

    def _due_value(self) -> str | None:
        return self.due_date.date().toString("yyyy-MM-dd") if self.due_enabled.isChecked() else None

    @staticmethod
    def _set_combo(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)


class LoanPaymentDialog(QDialog):
    def __init__(self, snapshot: LoanSnapshot, accounts: list[Account]):
        super().__init__()
        self.setWindowTitle("Record loan payment")
        loan = snapshot.loan
        self.account = QComboBox()
        for account in accounts:
            self.account.addItem(account.name, account.id)
        self.amount = QLineEdit()
        self.amount.setPlaceholderText(format_money(snapshot.outstanding))
        self.amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd MMM yyyy")
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Optional notes")

        form = QFormLayout()
        form.addRow("Pay from" if loan.direction == "borrowed" else "Receive into", self.account)
        form.addRow("Principal payment", self.amount)
        form.addRow("Date", self.date)
        form.addRow("Notes", self.notes)
        dialog_shell(
            self,
            "Record repayment",
            f"{loan.name}  ·  {format_money(snapshot.outstanding)} remaining",
            form,
            "Record payment",
            "loans",
            minimum_width=480,
        )
        self.amount.setFocus()

    def values(self) -> dict:
        return {
            "account_id": self.account.currentData(),
            "amount": self.amount.text(),
            "date": self.date.date().toString("yyyy-MM-dd"),
            "notes": self.notes.text() or None,
        }
