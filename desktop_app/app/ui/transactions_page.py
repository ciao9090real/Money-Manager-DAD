from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QMessageBox, QTableWidget, QTableWidgetItem, QWidget

from app.repositories.account_repository import AccountRepository
from app.services.category_service import CategoryService
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
    secondary_button,
    style_table,
)
from app.ui.transaction_form import TransactionForm


class TransactionsPage(QWidget):
    def __init__(self, db: sqlite3.Connection, on_changed, notify=None):
        super().__init__()
        self.accounts = AccountRepository(db)
        self.categories = CategoryService(db)
        self.service = TransactionService(db)
        self.on_changed = on_changed
        self.notify = notify or (lambda _message: None)
        self.current_filter = "all"
        self.filter_buttons = {}
        self.row_transactions = []
        self.add_button = primary_button("Add transaction", "+")
        self.add_button.clicked.connect(self.add_transaction)
        self.edit_button = secondary_button("Edit")
        self.delete_button = secondary_button("Delete")
        self.edit_button.clicked.connect(self.edit_transaction)
        self.delete_button.clicked.connect(self.delete_transaction)
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "Type", "Account", "Category", "Description", "Amount"])
        style_table(self.table)
        self.table.itemSelectionChanged.connect(self._sync_selection_actions)
        layout = page_layout(self, "Transactions", "Manual income, expenses, transfers, and adjustments", self.add_button)
        card, card_layout = create_card("Transaction list")
        filters = []
        for key, label in (("all", "All"), ("income", "Income"), ("expense", "Expenses"), ("transfer", "Transfers")):
            button = chip_button(label)
            button.clicked.connect(lambda _checked=False, value=key: self.set_filter(value))
            self.filter_buttons[key] = button
            filters.append(button)
        card_layout.addWidget(actions_row(*filters))
        card_layout.addWidget(actions_row(self.edit_button, self.delete_button))
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
        categories = {category.id: category.name for category in self.categories.list_categories(include_inactive=True)}
        transactions = [tx for tx in self.service.list_transactions(limit=300) if self._matches_filter(tx.type)]
        self.row_transactions = transactions
        self.table.setRowCount(len(transactions))
        for row_index, transaction in enumerate(transactions):
            values = [
                transaction.date,
                "",
                accounts.get(transaction.account_id, "Inactive account"),
                categories.get(transaction.category_id, ""),
                transaction.description or "No description",
                "",
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self.table.setItem(row_index, col_index, item)
            self.table.setCellWidget(row_index, 1, badge(pretty_type(transaction.type), badge_tone(transaction.type)))
            self.table.setItem(row_index, 5, amount_item(transaction.amount, neutral=transaction.type in {"transfer_out", "transfer_in", "adjustment"}))
        self.empty.setVisible(not transactions)
        self.table.setVisible(bool(transactions))
        self._sync_selection_actions()

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
        form = TransactionForm(accounts, self.categories.list_categories())
        if form.exec():
            values = form.values()
            try:
                category_id = self._category_id(values)
                if values["type"] == "income":
                    self.service.add_income(
                        values["account_id"],
                        values["amount"],
                        values["date"],
                        values["description"],
                        category_id=category_id,
                        notes=values["notes"],
                    )
                elif values["type"] == "expense":
                    self.service.add_expense(
                        values["account_id"],
                        values["amount"],
                        values["date"],
                        values["description"],
                        category_id=category_id,
                        notes=values["notes"],
                    )
                elif values["type"] == "transfer":
                    self.service.add_transfer(values["account_id"], values["target_account_id"], values["amount"], values["date"], values["description"], values["notes"])
                else:
                    self.service.add_adjustment(values["account_id"], values["amount"], values["date"], values["description"], values["notes"])
                self.notify("Transaction created")
                self.on_changed()
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save transaction", str(exc))

    def edit_transaction(self) -> None:
        transaction = self._selected_transaction()
        if not transaction:
            return
        accounts = self.accounts.list(include_inactive=True)
        if not accounts:
            QMessageBox.information(self, "No accounts", "Create an account first.")
            return
        transfer_source_id = None
        transfer_target_id = None
        if transaction.type in {"transfer_out", "transfer_in"}:
            try:
                outgoing, incoming = self.service.transfer_pair(int(transaction.id))
            except ValueError as exc:
                QMessageBox.warning(self, "Could not edit transaction", str(exc))
                return
            transfer_source_id = outgoing.account_id
            transfer_target_id = incoming.account_id
        form = TransactionForm(
            accounts,
            self.categories.list_categories(),
            transaction=transaction,
            transfer_source_id=transfer_source_id,
            transfer_target_id=transfer_target_id,
        )
        if form.exec():
            values = form.values()
            try:
                category_id = self._category_id(values)
                self.service.update_transaction(
                    int(transaction.id),
                    values["type"],
                    values["account_id"],
                    values["amount"],
                    values["date"],
                    values["description"],
                    target_account_id=values["target_account_id"],
                    category_id=category_id,
                    notes=values["notes"],
                )
                self.notify("Transaction updated")
                self.on_changed()
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save transaction", str(exc))

    def delete_transaction(self) -> None:
        transaction = self._selected_transaction()
        if not transaction:
            return
        detail = "This will delete both linked transfer transactions." if transaction.type in {"transfer_out", "transfer_in"} else "This cannot be undone."
        confirm = QMessageBox.question(
            self,
            "Delete transaction",
            f"Delete the selected transaction?\n\n{detail}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_transaction(int(transaction.id))
            self.notify("Transaction deleted")
            self.on_changed()
        except ValueError as exc:
            QMessageBox.warning(self, "Could not delete transaction", str(exc))

    def _selected_transaction(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.row_transactions):
            return None
        return self.row_transactions[row]

    def _sync_selection_actions(self) -> None:
        has_selection = self._selected_transaction() is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def _category_id(self, values: dict) -> int | None:
        if values["type"] not in {"income", "expense"}:
            return None
        return self.categories.category_id_for_input(values.get("category"), values["type"])
