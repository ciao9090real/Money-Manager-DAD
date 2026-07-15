from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.repositories.account_repository import AccountRepository
from app.services.category_service import CategoryService
from app.services.payment_method_service import PaymentMethodService
from app.services.transaction_service import TransactionService
from app.ui.components import (
    BadgeDelegate,
    badge_tone,
    chip_button,
    create_card,
    danger_button,
    empty_state,
    fit_item_view_height,
    ghost_button,
    page_layout,
    primary_button,
    style_table,
)
from app.ui.icons import icon
from app.ui.theme import Colors
from app.ui.transaction_form import TransactionForm
from app.ui.transaction_table_model import TransactionTableModel


class TransactionsPage(QWidget):
    PAGE_SIZE = 100

    def __init__(self, db: sqlite3.Connection, on_changed, notify=None):
        super().__init__()
        self.accounts = AccountRepository(db)
        self.categories = CategoryService(db)
        self.payment_methods = PaymentMethodService(db)
        self.service = TransactionService(db)
        self.on_changed = on_changed
        self.notify = notify or (lambda _message: None)
        self.current_filter = "all"
        self.filter_buttons = {}
        self.add_button = primary_button("Add transaction", "plus")
        self.add_button.clicked.connect(self.add_transaction)
        self.edit_button = ghost_button("Edit", "edit")
        self.delete_button = danger_button("Delete", "delete")
        self.edit_button.clicked.connect(self.edit_transaction)
        self.delete_button.clicked.connect(self.delete_transaction)
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.table = QTableView()
        self.table_model = TransactionTableModel()
        self.table.setModel(self.table_model)
        style_table(self.table)
        self.table.setItemDelegateForColumn(1, BadgeDelegate(badge_tone, self.table))
        self.table.doubleClicked.connect(lambda _index: self.edit_transaction())
        header = self.table.horizontalHeader()
        for column in (0, 1, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        for column, width in ((2, 180), (3, 120)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            header.resizeSection(column, width)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.selectionModel().selectionChanged.connect(self._sync_selection_actions)
        self.load_more_button = ghost_button("Load more transactions", "download")
        self.load_more_button.clicked.connect(self.load_more)
        self.load_more_button.setVisible(False)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search description or notes")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(220)
        self.search.setMaximumWidth(380)
        self.search.addAction(icon("search", Colors.TEXT_SECONDARY, 16), QLineEdit.ActionPosition.LeadingPosition)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(250)
        self.search_timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda _text: self.search_timer.start())
        self.find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.find_shortcut.activated.connect(self._focus_search)

        layout = page_layout(
            self,
            "Transactions",
            "Search and review every movement across your accounts",
            self.add_button,
        )
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        card, card_layout = create_card(
            "Activity",
            subtitle="Income, expenses, transfers, and balance adjustments",
        )
        self.activity_card = card
        filters = []
        for key, label in (("all", "All"), ("income", "Income"), ("expense", "Expenses"), ("transfer", "Transfers")):
            button = chip_button(label)
            button.clicked.connect(lambda _checked=False, value=key: self.set_filter(value))
            self.filter_buttons[key] = button
            filters.append(button)
        self.result_label = QLabel("")
        self.result_label.setProperty("role", "helper")
        controls = QFrame()
        controls.setProperty("role", "toolbar")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(8, 7, 8, 7)
        controls_layout.setSpacing(5)
        search_row = QHBoxLayout()
        search_row.setSpacing(7)
        search_row.addWidget(self.search)
        search_row.addStretch()
        search_row.addWidget(self.edit_button)
        search_row.addWidget(self.delete_button)
        filter_row = QHBoxLayout()
        filter_row.setSpacing(5)
        for button in filters:
            filter_row.addWidget(button)
        filter_row.addStretch()
        filter_row.addWidget(self.result_label)
        controls_layout.addLayout(search_row)
        controls_layout.addLayout(filter_row)
        card_layout.addWidget(controls)
        empty_action = primary_button("Add transaction", "plus")
        empty_action.clicked.connect(self.add_transaction)
        self.empty = empty_state("No transactions yet", "Add your first income, expense, or transfer.", empty_action)
        card_layout.addWidget(self.empty)
        card_layout.addWidget(self.table)
        card_layout.addWidget(self.load_more_button, 0)
        layout.addWidget(card, 1)
        self.set_filter("all", refresh=False)

    def set_filter(self, value: str, refresh: bool = True) -> None:
        self.current_filter = value
        for key, button in self.filter_buttons.items():
            selected = key == value
            button.setChecked(selected)
            button.setProperty("selected", "true" if selected else "false")
            button.style().unpolish(button)
            button.style().polish(button)
        if refresh:
            self.refresh()

    def _focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "table"):
            self.table.setColumnHidden(3, self.width() < 1050)
            self.table.setColumnHidden(2, self.width() < 1000)

    def refresh(self) -> None:
        accounts = {account.id: account.name for account in self.accounts.list(include_inactive=True)}
        categories = {category.id: category.name for category in self.categories.list_categories(include_inactive=True)}
        transaction_type = None if self.current_filter == "all" else self.current_filter
        transactions = self.service.list_transactions(
            limit=self.PAGE_SIZE,
            transaction_type=transaction_type,
            search_text=self.search.text(),
        )
        self.table_model.replace(transactions, accounts, categories)
        self.next_cursor = self._cursor_for(transactions)
        self.load_more_button.setVisible(len(transactions) == self.PAGE_SIZE)
        suffix = "+" if len(transactions) == self.PAGE_SIZE else ""
        self.result_label.setText(f"{self.table_model.rowCount()}{suffix} shown")
        self.empty.setVisible(not transactions)
        self.table.setVisible(bool(transactions))
        displayed_rows = self.table_model.rowCount()
        if transactions and displayed_rows <= 10:
            fit_item_view_height(self.table, displayed_rows, maximum_rows=10)
            self.activity_card.setMaximumHeight(190 + self.table.maximumHeight())
        elif transactions:
            self.table.setMaximumHeight(16777215)
            self.table.setMinimumHeight(320)
            self.activity_card.setMaximumHeight(16777215)
        else:
            self.activity_card.setMaximumHeight(350)
        self._sync_selection_actions()

    def load_more(self) -> None:
        if self.next_cursor is None:
            return
        transaction_type = None if self.current_filter == "all" else self.current_filter
        transactions = self.service.list_transactions(
            limit=self.PAGE_SIZE,
            transaction_type=transaction_type,
            cursor=self.next_cursor,
            search_text=self.search.text(),
        )
        self.table_model.append(transactions)
        self.next_cursor = self._cursor_for(transactions)
        self.load_more_button.setVisible(len(transactions) == self.PAGE_SIZE)
        self.result_label.setText(f"{self.table_model.rowCount()} shown")

    def add_transaction(self, initial_type: str | None = None) -> None:
        accounts = self.accounts.list(include_inactive=False)
        if not accounts:
            QMessageBox.information(self, "No accounts", "Create an account first.")
            return
        form = TransactionForm(
            accounts,
            self.categories.list_categories(),
            self.payment_methods.list_payment_methods(),
            category_service=self.categories,
        )
        if initial_type:
            index = form.type.findData(initial_type)
            if index >= 0:
                form.type.setCurrentIndex(index)
        if form.exec():
            values = form.values()
            try:
                if values["type"] == "income":
                    self.service.add_income(
                        values["account_id"],
                        values["amount"],
                        values["date"],
                        values["description"],
                        category_id=values.get("category"),
                        payment_method_id=values.get("payment_method_id"),
                        notes=values["notes"],
                    )
                elif values["type"] == "expense":
                    self.service.add_expense(
                        values["account_id"],
                        values["amount"],
                        values["date"],
                        values["description"],
                        category_id=values.get("category"),
                        payment_method_id=values.get("payment_method_id"),
                        notes=values["notes"],
                    )
                elif values["type"] == "transfer":
                    self.service.add_transfer(values["account_id"], values["target_account_id"], values["amount"], values["date"], values["description"], values["notes"])
                else:
                    self.service.add_adjustment(values["account_id"], values["amount"], values["date"], values["description"], values["notes"])
                self.notify("Transaction created")
                self.on_changed({"transactions", "accounts", "dashboard"})
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save transaction", str(exc))

    def edit_transaction(self) -> None:
        transaction = self._selected_transaction()
        if not transaction:
            return
        if transaction.investment_id:
            QMessageBox.information(
                self,
                "Investment entry",
                "Use the Investments page to change contributions or market values.",
            )
            return
        if transaction.loan_id:
            QMessageBox.information(
                self,
                "Loan entry",
                "Use the Loans page to change loan details or record repayments.",
            )
            return
        accounts = self.accounts.list(include_inactive=True)
        if not accounts:
            QMessageBox.information(self, "No accounts", "Create an account first.")
            return
        transfer_source_id = None
        transfer_target_id = None
        if transaction.type in {"transfer_out", "transfer_in"}:
            try:
                assert transaction.id is not None
                outgoing, incoming = self.service.transfer_pair(transaction.id)
            except ValueError as exc:
                QMessageBox.warning(self, "Could not edit transaction", str(exc))
                return
            transfer_source_id = outgoing.account_id
            transfer_target_id = incoming.account_id
        form = TransactionForm(
            accounts,
            self.categories.list_categories(),
            self.payment_methods.list_payment_methods(include_inactive=True),
            transaction=transaction,
            transfer_source_id=transfer_source_id,
            transfer_target_id=transfer_target_id,
            category_service=self.categories,
        )
        if form.exec():
            values = form.values()
            try:
                self.service.update_transaction(
                    transaction.id,
                    values["type"],
                    values["account_id"],
                    values["amount"],
                    values["date"],
                    values["description"],
                    target_account_id=values["target_account_id"],
                    category_id=values.get("category"),
                    payment_method_id=values.get("payment_method_id"),
                    notes=values["notes"],
                )
                self.notify("Transaction updated")
                self.on_changed({"transactions", "accounts", "dashboard"})
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
            assert transaction.id is not None
            self.service.delete_transaction(transaction.id)
            self.notify("Transaction deleted")
            self.on_changed({"transactions", "accounts", "dashboard"})
        except ValueError as exc:
            QMessageBox.warning(self, "Could not delete transaction", str(exc))

    def _selected_transaction(self):
        return self.table_model.transaction_at(self.table.currentIndex().row())

    def _sync_selection_actions(self) -> None:
        transaction = self._selected_transaction()
        editable = bool(transaction and not transaction.investment_id and not transaction.loan_id)
        self.edit_button.setEnabled(editable)
        self.delete_button.setEnabled(editable)
        protected_tip = ""
        if transaction and transaction.investment_id:
            protected_tip = "Use the Investments page for this entry"
        elif transaction and transaction.loan_id:
            protected_tip = "Use the Loans page for this entry"
        self.edit_button.setToolTip(protected_tip)
        self.delete_button.setToolTip(protected_tip)

    @staticmethod
    def _cursor_for(transactions) -> tuple[str, str] | None:
        if not transactions:
            return None
        last = transactions[-1]
        return (last.date, str(last.id))
