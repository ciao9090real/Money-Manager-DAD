from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QGridLayout, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from app.services.dashboard_service import DashboardService
from app.utils.money import format_money


class DashboardPage(QWidget):
    def __init__(self, db: sqlite3.Connection):
        super().__init__()
        self.service = DashboardService(db)
        self.cards: dict[str, QLabel] = {}
        layout = QVBoxLayout(self)

        grid = QGridLayout()
        for index, key in enumerate(("net_worth", "liquidity", "monthly_income", "monthly_expenses", "monthly_net_flow")):
            label = QLabel(key.replace("_", " ").title())
            value = QLabel(format_money(0))
            value.setStyleSheet("font-size: 22px; font-weight: 700;")
            self.cards[key] = value
            grid.addWidget(label, index // 3 * 2, index % 3)
            grid.addWidget(value, index // 3 * 2 + 1, index % 3)
        layout.addLayout(grid)

        layout.addWidget(QLabel("Recent transactions"))
        self.recent = QTableWidget(0, 4)
        self.recent.setHorizontalHeaderLabels(["Date", "Type", "Description", "Amount"])
        layout.addWidget(self.recent)

        layout.addWidget(QLabel("Accounts summary"))
        self.accounts = QTableWidget(0, 3)
        self.accounts.setHorizontalHeaderLabels(["Account", "Type", "Balance"])
        layout.addWidget(self.accounts)
        self.refresh()

    def refresh(self) -> None:
        data = self.service.summary()
        for key, label in self.cards.items():
            label.setText(format_money(data[key]))

        self.recent.setRowCount(len(data["recent_transactions"]))
        for row_index, transaction in enumerate(data["recent_transactions"]):
            values = [transaction.date, transaction.type, transaction.description, format_money(transaction.amount)]
            for col_index, value in enumerate(values):
                self.recent.setItem(row_index, col_index, QTableWidgetItem(str(value)))

        self.accounts.setRowCount(len(data["accounts"]))
        for row_index, account in enumerate(data["accounts"]):
            values = [account["name"], account["type"], format_money(account["balance"])]
            for col_index, value in enumerate(values):
                self.accounts.setItem(row_index, col_index, QTableWidgetItem(str(value)))

