from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from app.repositories.account_repository import AccountRepository
from app.services.transaction_service import TransactionService
from app.ui.transaction_form import TransactionForm
from app.utils.money import format_money


class TransactionsPage(QWidget):
    def __init__(self, db: sqlite3.Connection, on_changed):
        super().__init__()
        self.accounts = AccountRepository(db)
        self.service = TransactionService(db)
        self.on_changed = on_changed
        self.add_button = QPushButton("Add transaction")
        self.add_button.clicked.connect(self.add_transaction)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Date", "Type", "Account", "Description", "Amount"])
        layout = QVBoxLayout(self)
        layout.addWidget(self.add_button)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self) -> None:
        accounts = {account.id: account.name for account in self.accounts.list(include_inactive=True)}
        transactions = self.service.list_transactions(limit=300)
        self.table.setRowCount(len(transactions))
        for row_index, transaction in enumerate(transactions):
            values = [
                transaction.date,
                transaction.type,
                accounts.get(transaction.account_id, "Inactive account"),
                transaction.description,
                format_money(transaction.amount),
            ]
            for col_index, value in enumerate(values):
                self.table.setItem(row_index, col_index, QTableWidgetItem(str(value)))

    def add_transaction(self) -> None:
        accounts = self.accounts.list(include_inactive=False)
        if not accounts:
            QMessageBox.information(self, "No accounts", "Create an account first.")
            return
        form = TransactionForm(accounts)
        if form.exec():
            values = form.values()
            try:
                if values["type"] == "income":
                    self.service.add_income(values["account_id"], values["amount"], values["date"], values["description"], notes=values["notes"])
                elif values["type"] == "expense":
                    self.service.add_expense(values["account_id"], values["amount"], values["date"], values["description"], notes=values["notes"])
                elif values["type"] == "transfer":
                    self.service.add_transfer(values["account_id"], values["target_account_id"], values["amount"], values["date"], values["description"], values["notes"])
                else:
                    self.service.add_adjustment(values["account_id"], values["amount"], values["date"], values["description"], values["notes"])
                self.on_changed()
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save transaction", str(exc))

