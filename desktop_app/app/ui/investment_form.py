from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
)

from app.models.account import Account
from app.models.investment import Investment, InvestmentSnapshot, InvestmentValuePoint
from app.ui.components import dialog_shell
from app.ui.date_picker import DatePicker
from app.utils.dates import format_display_date
from app.utils.money import format_money


class InvestmentForm(QDialog):
    def __init__(
        self,
        funding_accounts: list[Account],
        investment: Investment | None = None,
    ):
        super().__init__()
        self.investment = investment
        self.setWindowTitle("Investment")

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
        self.date = DatePicker(QDate.currentDate())
        self.date.setMaximumDate(QDate.currentDate())

        subtitle = (
            "Keep the portfolio name and reference tidy."
            if investment
            else "Move money into a tracked investment and set its current value."
        )

        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Type", self.kind)
        form.addRow("Ticker / reference", self.symbol)
        if not investment:
            form.addRow("Fund from", self.source_account)
            form.addRow("Amount invested", self.amount)
            form.addRow("Current value", self.current_value)
            form.addRow("Date", self.date)
        form.addRow("Notes", self.notes)

        dialog_shell(
            self,
            "Edit investment" if investment else "Add investment",
            subtitle,
            form,
            "Save investment" if investment else "Add investment",
            "investments",
            minimum_width=520,
        )

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
        self.source_account = QComboBox()
        for account in funding_accounts:
            self.source_account.addItem(account.name, account.id)
        self.amount = QLineEdit()
        self.amount.setPlaceholderText("0.00")
        self.amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.date = DatePicker(QDate.currentDate())
        self.date.setMaximumDate(QDate.currentDate())
        self._build(
            "Add funds",
            snapshot.investment.name,
            (("Fund from", self.source_account), ("Amount", self.amount), ("Date", self.date)),
            "Add funds",
        )
        self.amount.setFocus()

    def _build(self, title_text, subtitle_text, rows, save_text) -> None:
        form = QFormLayout()
        for label, field in rows:
            form.addRow(label, field)
        dialog_shell(
            self,
            title_text,
            subtitle_text,
            form,
            save_text,
            "investments",
            minimum_width=460,
        )

    def values(self) -> dict:
        return {
            "source_account_id": self.source_account.currentData(),
            "amount": self.amount.text(),
            "date": self.date.date().toString("yyyy-MM-dd"),
        }


class WithdrawInvestmentFundsDialog(QDialog):
    def __init__(self, snapshot: InvestmentSnapshot, funding_accounts: list[Account]):
        super().__init__()
        self.setWindowTitle("Withdraw investment funds")
        self.destination_account = QComboBox()
        for account in funding_accounts:
            self.destination_account.addItem(account.name, account.id)
        available = QLineEdit(format_money(snapshot.current_value))
        available.setReadOnly(True)
        available.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.amount = QLineEdit()
        self.amount.setPlaceholderText("0.00")
        self.amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.date = DatePicker(QDate.currentDate())
        self.date.setMaximumDate(QDate.currentDate())

        form = QFormLayout()
        form.addRow("Available value", available)
        form.addRow("Send to", self.destination_account)
        form.addRow("Amount", self.amount)
        form.addRow("Date", self.date)
        dialog_shell(
            self,
            "Withdraw funds",
            snapshot.investment.name,
            form,
            "Withdraw",
            "transactions",
            minimum_width=460,
        )
        self.amount.setFocus()

    def values(self) -> dict:
        return {
            "destination_account_id": self.destination_account.currentData(),
            "amount": self.amount.text(),
            "date": self.date.date().toString("yyyy-MM-dd"),
        }


class UpdateInvestmentValueDialog(QDialog):
    def __init__(self, snapshot: InvestmentSnapshot):
        super().__init__()
        self.setWindowTitle("Update investment value")
        self.current_value = QLineEdit(str(snapshot.current_value))
        self.current_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.date = DatePicker(QDate.currentDate())
        self.date.setMaximumDate(QDate.currentDate())

        form = QFormLayout()
        form.addRow("Current value", self.current_value)
        form.addRow("Valuation date", self.date)
        dialog_shell(
            self,
            "Update value",
            snapshot.investment.name,
            form,
            "Update value",
            "investments",
            minimum_width=460,
        )
        self.current_value.setFocus()
        self.current_value.selectAll()

    def values(self) -> dict:
        return {
            "current_value": self.current_value.text(),
            "date": self.date.date().toString("yyyy-MM-dd"),
        }


class EditInvestmentValueDialog(QDialog):
    def __init__(self, investment_name: str, point: InvestmentValuePoint):
        super().__init__()
        self.setWindowTitle("Edit value log")
        valuation_date = QLineEdit(format_display_date(point.date))
        valuation_date.setReadOnly(True)
        invested = QLineEdit(format_money(point.contributed))
        invested.setReadOnly(True)
        self.current_value = QLineEdit(str(point.value))
        self.current_value.setAlignment(Qt.AlignmentFlag.AlignRight)

        form = QFormLayout()
        form.addRow("Valuation date", valuation_date)
        form.addRow("Invested", invested)
        form.addRow("Market value", self.current_value)
        dialog_shell(
            self,
            "Edit value log",
            investment_name,
            form,
            "Save log",
            "edit",
            minimum_width=460,
        )
        self.current_value.setFocus()
        self.current_value.selectAll()

    def value(self) -> str:
        return self.current_value.text()
