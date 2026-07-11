from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QMainWindow, QStackedWidget, QWidget

from app.ui.accounts_page import AccountsPage
from app.ui.dashboard_page import DashboardPage
from app.ui.settings_page import SettingsPage
from app.ui.transactions_page import TransactionsPage


class MainWindow(QMainWindow):
    def __init__(self, db: sqlite3.Connection):
        super().__init__()
        self.db = db
        self.setWindowTitle("Money Manager DAD")
        self.resize(1100, 720)

        self.nav = QListWidget()
        self.nav.setMaximumWidth(190)
        self.stack = QStackedWidget()

        self.dashboard = DashboardPage(db)
        self.accounts = AccountsPage(db, on_changed=self.refresh_all)
        self.transactions = TransactionsPage(db, on_changed=self.refresh_all)
        self.settings = SettingsPage(db)

        for title, page in (
            ("Dashboard", self.dashboard),
            ("Accounts", self.accounts),
            ("Transactions", self.transactions),
            ("Settings", self.settings),
        ):
            self.nav.addItem(QListWidgetItem(title))
            self.stack.addWidget(page)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.currentRowChanged.connect(lambda _row: self.refresh_all())
        self.nav.setCurrentRow(0)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.addWidget(self.nav)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

    def refresh_all(self) -> None:
        self.dashboard.refresh()
        self.accounts.refresh()
        self.transactions.refresh()

