from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from app.services.account_service import AccountService
from app.services.payment_method_service import PaymentMethodService
from app.ui.account_form import AccountForm
from app.ui.payment_method_form import PaymentMethodForm
from app.utils.money import format_money


class AccountsPage(QWidget):
    def __init__(self, db: sqlite3.Connection, on_changed):
        super().__init__()
        self.service = AccountService(db)
        self.payment_methods = PaymentMethodService(db)
        self.on_changed = on_changed
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Account", "Type", "Balance", "Status"])
        add_button = QPushButton("Add account")
        add_payment_button = QPushButton("Add payment method")
        edit_button = QPushButton("Edit")
        deactivate_button = QPushButton("Deactivate")
        add_button.clicked.connect(self.add_account)
        add_payment_button.clicked.connect(self.add_payment_method)
        edit_button.clicked.connect(self.edit_account)
        deactivate_button.clicked.connect(self.deactivate_account)

        buttons = QHBoxLayout()
        buttons.addWidget(add_button)
        buttons.addWidget(add_payment_button)
        buttons.addWidget(edit_button)
        buttons.addWidget(deactivate_button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addWidget(self.tree)
        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        methods_by_account: dict[int, list] = {}
        for method in self.payment_methods.list_payment_methods(include_inactive=False):
            methods_by_account.setdefault(method.account_id, []).append(method)
        for node in self.service.account_tree(include_inactive=False):
            self._add_node(node, methods_by_account=methods_by_account)
        self.tree.expandAll()

    def _add_node(self, node: dict, parent: QTreeWidgetItem | None = None, methods_by_account: dict[int, list] | None = None) -> None:
        account = node["account"]
        item = QTreeWidgetItem([account.name, account.type, format_money(node["rollup_balance"]), "Active"])
        item.setData(0, 256, account.id)
        if parent:
            parent.addChild(item)
        else:
            self.tree.addTopLevelItem(item)
        for child in node["children"]:
            self._add_node(child, item, methods_by_account)
        for method in (methods_by_account or {}).get(account.id, []):
            child = QTreeWidgetItem([method.name, method.type, "", "Payment method"])
            child.setData(0, 256, None)
            item.addChild(child)

    def add_account(self) -> None:
        form = AccountForm(self.service.list_accounts(include_inactive=False))
        if form.exec():
            try:
                values = form.values()
                self.service.create_account(**values)
                self.on_changed()
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save account", str(exc))

    def add_payment_method(self) -> None:
        accounts = self.service.list_accounts(include_inactive=False)
        if not accounts:
            QMessageBox.information(self, "No accounts", "Create an account first.")
            return
        form = PaymentMethodForm(accounts)
        if form.exec():
            try:
                self.payment_methods.create_payment_method(**form.values())
                self.on_changed()
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save payment method", str(exc))

    def edit_account(self) -> None:
        account_id = self._selected_account_id()
        if account_id is None:
            return
        account = self.service.accounts.get(account_id)
        form = AccountForm(self.service.list_accounts(include_inactive=True), account)
        if form.exec() and account:
            try:
                values = form.values()
                self.service.update_account(account_id=account_id, display_order=account.display_order, **values)
                self.on_changed()
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save account", str(exc))

    def deactivate_account(self) -> None:
        account_id = self._selected_account_id()
        if account_id is None:
            return
        self.service.deactivate_account(account_id)
        self.on_changed()

    def _selected_account_id(self) -> int | None:
        item = self.tree.currentItem()
        value = item.data(0, 256) if item else None
        return int(value) if value else None
