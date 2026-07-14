from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QHBoxLayout, QWidget

from app.ui.accounts_page import AccountsPage
from app.ui.dashboard_page import DashboardPage
from app.ui.settings_page import SettingsPage
from app.ui.sidebar import Sidebar
from app.ui.styles import app_stylesheet
from app.ui.transactions_page import TransactionsPage
from app.ui.icons import icon


class MainWindow(QMainWindow):
    def __init__(self, db: sqlite3.Connection):
        super().__init__()
        self.db = db
        self.setWindowTitle("Money Manager — Private Finance")
        self.setWindowIcon(icon("accounts", "#5b5ce2", 32))
        self.resize(1280, 820)
        self.setMinimumSize(980, 680)
        application = QApplication.instance()
        if application:
            application.setStyleSheet(app_stylesheet())
        else:
            self.setStyleSheet(app_stylesheet())

        self.stack = QStackedWidget()

        self.accounts = AccountsPage(db, on_changed=self.invalidate, notify=self.show_status)
        self.transactions = TransactionsPage(db, on_changed=self.invalidate, notify=self.show_status)
        self.settings = SettingsPage(db, notify=self.show_status, on_changed=self.invalidate)
        self.dashboard = DashboardPage(
            db,
            on_add_transaction=self.transactions.add_transaction,
            on_add_account=self.accounts.add_account,
            on_backup=self.settings.create_backup,
        )

        pages = (
            ("Dashboard", "dashboard", self.dashboard),
            ("Accounts", "accounts", self.accounts),
            ("Transactions", "transactions", self.transactions),
            ("Settings", "settings", self.settings),
        )
        for _title, _icon, page in pages:
            self.stack.addWidget(page)
        self.page_keys = ("dashboard", "accounts", "transactions", "settings")
        self.dirty_pages = {"dashboard", "accounts", "transactions"}
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
        self.statusBar().showMessage("Local database protected · Offline ready")
        self._select_page(0)

    def _select_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.sidebar.set_selected(index)
        self._refresh_selected_if_dirty()

    def invalidate(self, tags: set[str]) -> None:
        self.dirty_pages.update(tags & {"dashboard", "accounts", "transactions"})
        self._refresh_selected_if_dirty()

    def _refresh_selected_if_dirty(self) -> None:
        index = self.stack.currentIndex()
        if index < 0:
            return
        key = self.page_keys[index]
        if key not in self.dirty_pages:
            return
        page = self.stack.currentWidget()
        refresh = getattr(page, "refresh", None)
        if refresh:
            refresh()
        self.dirty_pages.discard(key)

    def show_status(self, message: str) -> None:
        self.statusBar().showMessage(message, 4500)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "sidebar") and self.width() < 1120 and not self.sidebar.collapsed:
            self.sidebar.toggle()
