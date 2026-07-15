from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from app.models.account import Account
from app.models.investment import Investment, InvestmentSnapshot
from app.ui.components import primary_button, secondary_button


class InvestmentForm(QDialog):
    def __init__(
        self,
        funding_accounts: list[Account],
        investment: Investment | None = None,
    ):
        super().__init__()
        self.investment = investment
        self.setWindowTitle("Investment")
        self.setMinimumWidth(540)

        self.name = QLineEdit(investment.name if investment else "")
        self.name.setPlaceholderText("Investment name")
        self.kind = QComboBox()
        for key, label in (
            ("fund", "Managed fund"),
            ("etf", "ETF"),
            ("stock", "Stock"),
            ("bond", "Bond"),
            ("crypto", "Crypto"),
            ("other", "Other"),
        ):
            self.kind.addItem(label, key)
        self.symbol = QLineEdit(investment.symbol if investment else "")
        self.symbol.setPlaceholderText("Optional ticker or reference")
        self.notes = QLineEdit(investment.notes if investment else "")
        self.notes.setPlaceholderText("Optional notes")

        self.source_account = QComboBox()
        for account in funding_accounts:
            self.source_account.addItem(account.name, account.id)
        self.amount = QLineEdit()
        self.amount.setPlaceholderText("0.00")
        self.amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.current_value = QLineEdit()
        self.current_value.setPlaceholderText("Same as amount invested")
        self.current_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd MMM yyyy")

        title = QLabel("Edit investment" if investment else "Add investment")
        title.setProperty("role", "dialogTitle")
        subtitle = QLabel(
            "Keep the portfolio name and reference tidy."
            if investment
            else "Move money into a tracked investment and set its current value."
        )
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(11)
        form.addRow("Name", self.name)
        form.addRow("Type", self.kind)
        form.addRow("Ticker / reference", self.symbol)
        if not investment:
            form.addRow("Fund from", self.source_account)
            form.addRow("Amount invested", self.amount)
            form.addRow("Current value", self.current_value)
            form.addRow("Date", self.date)
        form.addRow("Notes", self.notes)

        save = primary_button("Save investment" if investment else "Add investment")
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
        layout.setSpacing(17)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(form)
        layout.addLayout(buttons)

        if investment:
            index = self.kind.findData(investment.kind)
            if index >= 0:
                self.kind.setCurrentIndex(index)
        self.name.setFocus()

    def create_values(self) -> dict:
        return {
            "name": self.name.text(),
            "kind": self.kind.currentData(),
            "symbol": self.symbol.text(),
            "source_account_id": self.source_account.currentData(),
            "amount": self.amount.text(),
            "current_value": self.current_value.text(),
            "date": self.date.date().toString("yyyy-MM-dd"),
            "notes": self.notes.text(),
        }

    def edit_values(self) -> dict:
        return {
            "name": self.name.text(),
            "kind": self.kind.currentData(),
            "symbol": self.symbol.text(),
            "notes": self.notes.text(),
        }


class AddInvestmentFundsDialog(QDialog):
    def __init__(self, snapshot: InvestmentSnapshot, funding_accounts: list[Account]):
        super().__init__()
        self.setWindowTitle("Add investment funds")
        self.setMinimumWidth(460)
        self.source_account = QComboBox()
        for account in funding_accounts:
            self.source_account.addItem(account.name, account.id)
        self.amount = QLineEdit()
        self.amount.setPlaceholderText("0.00")
        self.amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd MMM yyyy")
        self._build(
            "Add funds",
            snapshot.investment.name,
            (("Fund from", self.source_account), ("Amount", self.amount), ("Date", self.date)),
            "Add funds",
        )
        self.amount.setFocus()

    def _build(self, title_text, subtitle_text, rows, save_text) -> None:
        title = QLabel(title_text)
        title.setProperty("role", "dialogTitle")
        subtitle = QLabel(subtitle_text)
        subtitle.setProperty("role", "subtitle")
        form = QFormLayout()
        form.setVerticalSpacing(12)
        for label, field in rows:
            form.addRow(label, field)
        save = primary_button(save_text)
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

    def values(self) -> dict:
        return {
            "source_account_id": self.source_account.currentData(),
            "amount": self.amount.text(),
            "date": self.date.date().toString("yyyy-MM-dd"),
        }


class UpdateInvestmentValueDialog(QDialog):
    def __init__(self, snapshot: InvestmentSnapshot):
        super().__init__()
        self.setWindowTitle("Update investment value")
        self.setMinimumWidth(460)
        self.current_value = QLineEdit(str(snapshot.current_value))
        self.current_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd MMM yyyy")

        title = QLabel("Update value")
        title.setProperty("role", "dialogTitle")
        subtitle = QLabel(snapshot.investment.name)
        subtitle.setProperty("role", "subtitle")
        form = QFormLayout()
        form.setVerticalSpacing(12)
        form.addRow("Current value", self.current_value)
        form.addRow("Valuation date", self.date)
        save = primary_button("Update value")
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
        self.current_value.setFocus()
        self.current_value.selectAll()

    def values(self) -> dict:
        return {
            "current_value": self.current_value.text(),
            "date": self.date.date().toString("yyyy-MM-dd"),
        }
