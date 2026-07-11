from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QMessageBox, QTableWidget, QTableWidgetItem, QWidget

from app.repositories.account_repository import AccountRepository
from app.services.transaction_service import TransactionService
from app.ui.components import (
    actions_row,
    amount_item,
    badge,
    badge_tone,
    chip_button,
    create_card,
    empty_state,
    page_layout,
    pretty_type,
    primary_button,
    style_table,
)
from app.ui.transaction_form import TransactionForm


class TransactionsPage(QWidget):
    def __init__(self, db: sqlite3.Connection, on_changed, notify=None):
        super().__init__()
        self.accounts = AccountRepository(db)
        self.service = TransactionService(db)
        self.on_changed = on_changed
        self.notify = notify or (lambda _message: None)
        self.current_filter = "all"
        self.filter_buttons = {}
        self.add_button = primary_button("Add transaction", "+")
        self.add_button.clicked.connect(self.add_transaction)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Date", "Type", "Account", "Description", "Amount"])
        style_table(self.table)
        layout = page_layout(self, "Transactions", "Manual income, expenses, transfers, and adjustments", self.add_button)
        card, card_layout = create_card("Transaction list")
        filters = []
        for key, label in (("all", "All"), ("income", "Income"), ("expense", "Expenses"), ("transfer", "Transfers")):
            button = chip_button(label)
            button.clicked.connect(lambda _checked=False, value=key: self.set_filter(value))
            self.filter_buttons[key] = button
            filters.append(button)
        card_layout.addWidget(actions_row(*filters))
        empty_action = primary_button("Add transaction", "+")
        empty_action.clicked.connect(self.add_transaction)
        self.empty = empty_state("No transactions yet", "Add your first income, expense, or transfer.", empty_action)
        card_layout.addWidget(self.empty)
        card_layout.addWidget(self.table)
        layout.addWidget(card, 1)
        self.set_filter("all")

    def set_filter(self, value: str) -> None:
        self.current_filter = value
        for key, button in self.filter_buttons.items():
            selected = key == value
            button.setChecked(selected)
            button.setProperty("selected", "true" if selected else "false")
            button.style().unpolish(button)
            button.style().polish(button)
        self.refresh()

    def refresh(self) -> None:
        accounts = {account.id: account.name for account in self.accounts.list(include_inactive=True)}
        transactions = [tx for tx in self.service.list_transactions(limit=300) if self._matches_filter(tx.type)]
        self.table.setRowCount(len(transactions))
        for row_index, transaction in enumerate(transactions):
            values = [
                transaction.date,
                "",
                accounts.get(transaction.account_id, "Inactive account"),
                transaction.description or "No description",
                "",
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self.table.setItem(row_index, col_index, item)
            self.table.setCellWidget(row_index, 1, badge(pretty_type(transaction.type), badge_tone(transaction.type)))
            self.table.setItem(row_index, 4, amount_item(transaction.amount, neutral=transaction.type in {"transfer_out", "transfer_in", "adjustment"}))
        self.empty.setVisible(not transactions)
        self.table.setVisible(bool(transactions))

    def _matches_filter(self, transaction_type: str) -> bool:
        if self.current_filter == "all":
            return True
        if self.current_filter == "transfer":
            return transaction_type in {"transfer_out", "transfer_in"}
        return transaction_type == self.current_filter

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
                self.notify("Transaction created")
                self.on_changed()
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save transaction", str(exc))
