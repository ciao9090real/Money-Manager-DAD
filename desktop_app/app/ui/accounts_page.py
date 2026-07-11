from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QMessageBox, QPushButton, QTreeWidget, QTreeWidgetItem, QWidget

from app.services.account_service import AccountService
from app.services.payment_method_service import PaymentMethodService
from app.ui.components import actions_row, badge, badge_tone, create_card, empty_state, page_layout, pretty_type, primary_button, secondary_button, style_tree
from app.ui.account_form import AccountForm
from app.ui.payment_method_form import PaymentMethodForm
from app.utils.money import format_money


class AccountsPage(QWidget):
    def __init__(self, db: sqlite3.Connection, on_changed, notify=None):
        super().__init__()
        self.service = AccountService(db)
        self.payment_methods = PaymentMethodService(db)
        self.on_changed = on_changed
        self.notify = notify or (lambda _message: None)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Account", "Type", "Balance", "Status"])
        style_tree(self.tree, visible_rows=10)
        add_button = primary_button("Add account", "+")
        add_payment_button = secondary_button("Add payment method", "+")
        edit_button = secondary_button("Edit")
        deactivate_button = secondary_button("Deactivate")
        add_button.clicked.connect(self.add_account)
        add_payment_button.clicked.connect(self.add_payment_method)
        edit_button.clicked.connect(self.edit_account)
        deactivate_button.clicked.connect(self.deactivate_account)

        layout = page_layout(self, "Accounts", "Organize banks, accounts, wallets, and payment methods", add_button)
        card, card_layout = create_card("Account hierarchy")
        card_layout.addWidget(actions_row(add_payment_button, edit_button, deactivate_button))
        empty_action = primary_button("Add account", "+")
        empty_action.clicked.connect(self.add_account)
        self.empty = empty_state("No accounts yet", "Add your first bank, wallet, or cash account.", empty_action)
        card_layout.addWidget(self.empty)
        card_layout.addWidget(self.tree)
        layout.addWidget(card, 1)
        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        methods_by_account: dict[int, list] = {}
        for method in self.payment_methods.list_payment_methods(include_inactive=False):
            methods_by_account.setdefault(method.account_id, []).append(method)
        tree = self.service.account_tree(include_inactive=False)
        for node in tree:
            self._add_node(node, methods_by_account=methods_by_account)
        self.tree.expandAll()
        self.empty.setVisible(not tree)
        self.tree.setVisible(bool(tree))

    def _add_node(self, node: dict, parent: QTreeWidgetItem | None = None, methods_by_account: dict[int, list] | None = None) -> None:
        account = node["account"]
        item = QTreeWidgetItem([account.name, "", format_money(node["rollup_balance"]), ""])
        item.setData(0, 256, account.id)
        item.setTextAlignment(2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if parent is None:
            font = QFont()
            font.setBold(True)
            item.setFont(0, font)
        if parent:
            parent.addChild(item)
        else:
            self.tree.addTopLevelItem(item)
        self.tree.setItemWidget(item, 1, badge(pretty_type(account.type), "neutral"))
        self.tree.setItemWidget(item, 3, badge("Active", badge_tone("active")))
        for child in node["children"]:
            self._add_node(child, item, methods_by_account)
        for method in (methods_by_account or {}).get(account.id, []):
            child = QTreeWidgetItem([method.name, "", "", ""])
            child.setData(0, 256, None)
            item.addChild(child)
            self.tree.setItemWidget(child, 1, badge(pretty_type(method.type), "neutral"))
            self.tree.setItemWidget(child, 3, badge("Payment method", "info"))

    def add_account(self) -> None:
        form = AccountForm(self.service.list_accounts(include_inactive=False))
        if form.exec():
            try:
                values = form.values()
                self.service.create_account(**values)
                self.notify("Account created")
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
                self.notify("Payment method created")
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
                self.notify("Account updated")
                self.on_changed()
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save account", str(exc))

    def deactivate_account(self) -> None:
        account_id = self._selected_account_id()
        if account_id is None:
            return
        self.service.deactivate_account(account_id)
        self.notify("Account deactivated")
        self.on_changed()

    def _selected_account_id(self) -> int | None:
        item = self.tree.currentItem()
        value = item.data(0, 256) if item else None
        return int(value) if value else None
