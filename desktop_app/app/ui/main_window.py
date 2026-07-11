from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QHBoxLayout, QWidget

from app.ui.accounts_page import AccountsPage
from app.ui.dashboard_page import DashboardPage
from app.ui.settings_page import SettingsPage
from app.ui.sidebar import Sidebar
from app.ui.styles import app_stylesheet
from app.ui.transactions_page import TransactionsPage


class MainWindow(QMainWindow):
    def __init__(self, db: sqlite3.Connection):
        super().__init__()
        self.db = db
        self.setWindowTitle("Money Manager")
        self.resize(1100, 720)
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(app_stylesheet())

        self.stack = QStackedWidget()

        self.accounts = AccountsPage(db, on_changed=self.refresh_all, notify=self.show_status)
        self.transactions = TransactionsPage(db, on_changed=self.refresh_all, notify=self.show_status)
        self.settings = SettingsPage(db, notify=self.show_status)
        self.dashboard = DashboardPage(
            db,
            on_add_transaction=self.transactions.add_transaction,
            on_add_account=self.accounts.add_account,
            on_backup=self.settings.create_backup,
        )

        pages = (
            ("Dashboard", "\u2302", self.dashboard),
            ("Accounts", "\u20ac", self.accounts),
            ("Transactions", "\u21c4", self.transactions),
            ("Settings", "\u2699", self.settings),
        )
        for _title, _icon, page in pages:
            self.stack.addWidget(page)
        self.sidebar = Sidebar([(title, icon) for title, icon, _page in pages])
        self.sidebar.page_selected.connect(self._select_page)

        root = QWidget()
        root.setObjectName("AppRoot")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("Database stored locally")
        self._select_page(0)

    def _select_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.sidebar.set_selected(index)
        self.refresh_all()

    def refresh_all(self) -> None:
        self.dashboard.refresh()
        self.accounts.refresh()
        self.transactions.refresh()

    def show_status(self, message: str) -> None:
        self.statusBar().showMessage(message, 4500)
