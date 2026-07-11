from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QTableWidget, QTableWidgetItem, QWidget

from app.repositories.account_repository import AccountRepository
from app.services.dashboard_service import DashboardService
from app.ui.components import (
    actions_row,
    amount_item,
    badge,
    badge_tone,
    clear_layout,
    create_card,
    empty_state,
    metric_card,
    page_layout,
    pretty_type,
    primary_button,
    secondary_button,
    style_table,
)
from app.utils.money import format_money


class DashboardPage(QWidget):
    def __init__(self, db: sqlite3.Connection, on_add_transaction=None, on_add_account=None, on_backup=None):
        super().__init__()
        self.service = DashboardService(db)
        self.account_repo = AccountRepository(db)
        self.cards: dict[str, QLabel] = {}
        self.metric_widgets = []
        layout = page_layout(self, "Dashboard", "Overview of your local finances")

        self.metric_grid = QGridLayout()
        self.metric_grid.setSpacing(16)
        metadata = {
            "net_worth": ("Net Worth", "All active local accounts", None),
            "liquidity": ("Liquidity", "Available account balances", None),
            "monthly_income": ("Monthly Income", "Income this month", "positive"),
            "monthly_expenses": ("Monthly Expenses", "Expenses this month", "negative"),
            "monthly_net_flow": ("Monthly Net Flow", "Income minus expenses", None),
        }
        for index, key in enumerate(("net_worth", "liquidity", "monthly_income", "monthly_expenses", "monthly_net_flow")):
            label, helper, tone = metadata[key]
            card, value = metric_card(label, format_money(0), helper, tone)
            self.cards[key] = value
            self.metric_widgets.append(card)
        layout.addLayout(self.metric_grid)
        self._layout_metric_cards()

        add_transaction = primary_button("Add transaction", "+")
        add_account = secondary_button("Add account", "+")
        backup = secondary_button("Create backup", "\u21bb")
        add_transaction.clicked.connect(on_add_transaction or (lambda: None))
        add_account.clicked.connect(on_add_account or (lambda: None))
        backup.clicked.connect(on_backup or (lambda: None))
        layout.addWidget(actions_row(add_transaction, add_account, backup))

        recent_card, recent_layout = create_card("Recent transactions", max_height=360)
        self.recent_empty = empty_state("No transactions yet", "Add your first income, expense, or transfer.")
        self.recent = QTableWidget(0, 5)
        self.recent.setHorizontalHeaderLabels(["Date", "Type", "Description", "Account", "Amount"])
        style_table(self.recent, visible_rows=7)
        recent_layout.addWidget(self.recent_empty)
        recent_layout.addWidget(self.recent)
        layout.addWidget(recent_card)

        accounts_card, accounts_layout = create_card("Accounts summary", max_height=260)
        self.accounts_empty = empty_state("No accounts yet", "Add your first bank, wallet, or cash account.")
        self.accounts = QTableWidget(0, 3)
        self.accounts.setHorizontalHeaderLabels(["Account", "Type", "Balance"])
        style_table(self.accounts, visible_rows=4)
        accounts_layout.addWidget(self.accounts_empty)
        accounts_layout.addWidget(self.accounts)
        layout.addWidget(accounts_card)
        self.refresh()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_metric_cards()

    def _layout_metric_cards(self) -> None:
        if not hasattr(self, "metric_grid"):
            return
        width = max(1, self.width())
        columns = 3 if width >= 1120 else 2 if width >= 720 else 1
        clear_layout(self.metric_grid)
        for index, card in enumerate(self.metric_widgets):
            self.metric_grid.addWidget(card, index // columns, index % columns)
            self.metric_grid.setColumnStretch(index % columns, 1)

    def refresh(self) -> None:
        data = self.service.summary()
        for key, label in self.cards.items():
            label.setText(format_money(data[key]))
            if key == "monthly_net_flow":
                tone = "positive" if data[key] >= 0 else "negative"
                label.setProperty("tone", tone)
                label.style().unpolish(label)
                label.style().polish(label)

        account_names = {account.id: account.name for account in self.account_repo.list(include_inactive=True)}
        self.recent.setRowCount(len(data["recent_transactions"]))
        for row_index, transaction in enumerate(data["recent_transactions"]):
            values = [
                transaction.date,
                "",
                transaction.description or "No description",
                account_names.get(transaction.account_id, "Inactive account"),
                "",
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self.recent.setItem(row_index, col_index, item)
            type_badge = badge(pretty_type(transaction.type), badge_tone(transaction.type))
            self.recent.setCellWidget(row_index, 1, type_badge)
            self.recent.setItem(row_index, 4, amount_item(transaction.amount, neutral=transaction.type in {"transfer_out", "transfer_in", "adjustment"}))
        self.recent.setVisible(bool(data["recent_transactions"]))
        self.recent_empty.setVisible(not data["recent_transactions"])

        self.accounts.setRowCount(len(data["accounts"]))
        for row_index, account in enumerate(data["accounts"]):
            values = [account["name"], "", format_money(account["balance"])]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col_index == 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.accounts.setItem(row_index, col_index, item)
            self.accounts.setCellWidget(row_index, 1, badge(pretty_type(account["type"]), "neutral"))
        self.accounts.setVisible(bool(data["accounts"]))
        self.accounts_empty.setVisible(not data["accounts"])
