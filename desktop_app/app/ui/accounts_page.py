from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from app.repositories.investment_repository import InvestmentRepository
from app.services.account_service import AccountService
from app.services.payment_method_service import PaymentMethodService
from app.ui.components import (
    badge,
    badge_tone,
    create_card,
    danger_button,
    empty_state,
    fit_item_view_height,
    ghost_button,
    page_layout,
    pretty_type,
    primary_button,
    soft_button,
    style_tree,
    toolbar,
)
from app.ui.account_form import AccountForm
from app.ui.payment_method_form import PaymentMethodForm
from app.utils.money import format_money


class AccountsPage(QWidget):
    def __init__(self, db: sqlite3.Connection, on_changed, notify=None):
        super().__init__()
        self.service = AccountService(db)
        self.investments = InvestmentRepository(db)
        self.payment_methods = PaymentMethodService(db)
        self.on_changed = on_changed
        self.notify = notify or (lambda _message: None)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Account", "Type", "Balance", "Status"])
        style_tree(self.tree, visible_rows=8)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        add_button = primary_button("Add account", "plus")
        add_payment_button = soft_button("Add payment method", "plus")
        add_payment_button.setMaximumWidth(190)
        self.count_label = QLabel("")
        self.count_label.setProperty("role", "count")
        self.selection_label = QLabel("")
        self.selection_label.setProperty("role", "count")
        self.selection_label.setVisible(False)
        self.edit_payment_button = ghost_button("", "edit")
        self.edit_payment_button.setToolTip("Edit selected payment method")
        self.edit_payment_button.setFixedSize(40, 40)
        self.toggle_payment_button = ghost_button("", "archive")
        self.toggle_payment_button.setToolTip("Archive or restore selected payment method")
        self.toggle_payment_button.setFixedSize(40, 40)
        self.edit_button = ghost_button("Edit account", "edit")
        self.edit_button.setMaximumWidth(130)
        self.deactivate_button = danger_button("Deactivate", "archive")
        self.deactivate_button.setMaximumWidth(125)
        add_button.clicked.connect(self.add_account)
        add_payment_button.clicked.connect(self.add_payment_method)
        self.edit_payment_button.clicked.connect(self.edit_payment_method)
        self.toggle_payment_button.clicked.connect(self.toggle_payment_method)
        self.edit_button.clicked.connect(self.edit_account)
        self.deactivate_button.clicked.connect(self.deactivate_account)
        for button in (
            self.edit_payment_button,
            self.toggle_payment_button,
            self.edit_button,
            self.deactivate_button,
        ):
            button.setEnabled(False)
            button.setVisible(False)
        self.tree.itemSelectionChanged.connect(self._sync_actions)

        layout = page_layout(
            self,
            "Accounts",
            "A structured view of your banks, wallets, savings, and payment methods",
            add_button,
        )
        card, card_layout = create_card(
            "Account structure",
            subtitle="Select an account or payment method to manage it",
        )
        card_layout.addWidget(
            toolbar(
                left=[add_payment_button, self.count_label],
                right=[
                    self.selection_label,
                    self.edit_payment_button,
                    self.toggle_payment_button,
                    self.edit_button,
                    self.deactivate_button,
                ],
            )
        )
        empty_action = primary_button("Add account", "plus")
        empty_action.clicked.connect(self.add_account)
        self.empty = empty_state("No accounts yet", "Add your first bank, wallet, or cash account.", empty_action)
        card_layout.addWidget(self.empty)
        card_layout.addWidget(self.tree)
        layout.addWidget(card)
        layout.addStretch()

    def refresh(self) -> None:
        self.tree.clear()
        methods_by_account: dict[str, list] = {}
        for method in self.payment_methods.list_payment_methods(include_inactive=True):
            methods_by_account.setdefault(method.account_id, []).append(method)
        tree = self.service.account_tree(include_inactive=False)
        for node in tree:
            self._add_node(node, methods_by_account=methods_by_account)
        self.tree.expandAll()
        account_count = self._account_count(tree)
        method_count = sum(
            len(methods_by_account.get(account.id, []))
            for account in self.service.list_accounts(include_inactive=False)
        )
        account_word = "account" if account_count == 1 else "accounts"
        method_word = "method" if method_count == 1 else "methods"
        self.count_label.setText(
            f"{account_count} {account_word} · {method_count} {method_word}"
        )
        fit_item_view_height(
            self.tree,
            account_count + method_count,
            minimum_rows=1,
            maximum_rows=10,
        )
        self.empty.setVisible(not tree)
        self.tree.setVisible(bool(tree))
        self._sync_actions()

    def _add_node(self, node: dict, parent: QTreeWidgetItem | None = None, methods_by_account: dict[str, list] | None = None) -> None:
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
            child.setData(0, 257, method.id)
            item.addChild(child)
            self.tree.setItemWidget(child, 1, badge(pretty_type(method.type), "neutral"))
            status = "Active" if method.is_active else "Archived"
            tone = "positive" if method.is_active else "muted"
            self.tree.setItemWidget(child, 3, badge(status, tone))

    @staticmethod
    def _account_count(nodes: list[dict]) -> int:
        return sum(1 + AccountsPage._account_count(node["children"]) for node in nodes)

    def add_account(self) -> None:
        form = AccountForm(self.service.list_accounts(include_inactive=False))
        if form.exec():
            try:
                values = form.values()
                self.service.create_account(**values)
                self.notify("Account created")
                self.on_changed({"accounts", "dashboard", "transactions", "upcoming"})
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
                self.on_changed({"accounts", "upcoming"})
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save payment method", str(exc))

    def edit_account(self) -> None:
        account_id = self._selected_account_id()
        if account_id is None:
            return
        account = self.service.accounts.get(account_id)
        if account and self.investments.get_by_account(account_id):
            QMessageBox.information(
                self,
                "Investment account",
                "Use the Investments page to edit this managed account.",
            )
            return
        form = AccountForm(self.service.list_accounts(include_inactive=True), account)
        if form.exec() and account:
            try:
                values = form.values()
                self.service.update_account(account_id=account_id, display_order=account.display_order, **values)
                self.notify("Account updated")
                self.on_changed({"accounts", "dashboard", "transactions", "upcoming"})
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save account", str(exc))

    def edit_payment_method(self) -> None:
        method_id = self._selected_payment_method_id()
        if method_id is None:
            return
        method = self.payment_methods.payment_methods.get(method_id)
        if not method:
            return
        form = PaymentMethodForm(self.service.list_accounts(include_inactive=False), method)
        if form.exec():
            try:
                self.payment_methods.update_payment_method(
                    payment_method_id=method_id, **form.values()
                )
                self.notify("Payment method updated")
                self.on_changed({"accounts", "upcoming"})
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save payment method", str(exc))

    def toggle_payment_method(self) -> None:
        method_id = self._selected_payment_method_id()
        if method_id is None:
            return
        method = self.payment_methods.payment_methods.get(method_id)
        if not method:
            return
        try:
            if method.is_active:
                self.payment_methods.archive_payment_method(method_id)
                self.notify("Payment method archived")
            else:
                self.payment_methods.restore_payment_method(method_id)
                self.notify("Payment method restored")
            self.on_changed({"accounts", "upcoming"})
        except ValueError as exc:
            QMessageBox.warning(self, "Could not update payment method", str(exc))

    def deactivate_account(self) -> None:
        account_id = self._selected_account_id()
        if account_id is None:
            return
        if self.investments.get_by_account(account_id):
            QMessageBox.information(
                self,
                "Investment account",
                "Managed investment accounts stay active while the investment is tracked.",
            )
            return
        try:
            self.service.deactivate_account(account_id)
            self.notify("Account deactivated")
            self.on_changed({"accounts", "dashboard", "transactions", "upcoming"})
        except ValueError as exc:
            QMessageBox.warning(self, "Could not deactivate account", str(exc))

    def _selected_account_id(self) -> str | None:
        item = self.tree.currentItem()
        value = item.data(0, 256) if item else None
        return str(value) if value else None

    def _selected_payment_method_id(self) -> str | None:
        item = self.tree.currentItem()
        value = item.data(0, 257) if item else None
        return str(value) if value else None

    def _sync_actions(self) -> None:
        account_id = self._selected_account_id()
        has_account = account_id is not None
        managed_investment = bool(account_id and self.investments.get_by_account(account_id))
        has_method = self._selected_payment_method_id() is not None
        selected = self.tree.currentItem()
        self.selection_label.setText(selected.text(0) if selected else "")
        self.selection_label.setVisible(selected is not None)
        self.edit_button.setEnabled(has_account and not managed_investment)
        self.deactivate_button.setEnabled(has_account and not managed_investment)
        self.edit_payment_button.setEnabled(has_method)
        self.toggle_payment_button.setEnabled(has_method)
        self.edit_button.setVisible(has_account and not managed_investment)
        self.deactivate_button.setVisible(has_account and not managed_investment)
        self.edit_payment_button.setVisible(has_method)
        self.toggle_payment_button.setVisible(has_method)
