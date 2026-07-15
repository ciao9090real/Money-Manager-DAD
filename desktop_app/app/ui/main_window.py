from __future__ import annotations

import sqlite3

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QHBoxLayout, QWidget

from app.core.database import unit_of_work
from app.repositories.settings_repository import SettingsRepository
from app.ui.accounts_page import AccountsPage
from app.ui.dashboard_page import DashboardPage
from app.ui.investments_page import InvestmentsPage
from app.ui.settings_page import SettingsPage
from app.ui.sidebar import Sidebar
from app.ui.styles import app_stylesheet
from app.ui.transactions_page import TransactionsPage
from app.ui.upcoming_page import UpcomingPage
from app.ui.icons import icon


class MainWindow(QMainWindow):
    SIDEBAR_SETTING = "ui.sidebar_collapsed"
    SIDEBAR_AUTO_COLLAPSE_WIDTH = 1120

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
        self.investments = InvestmentsPage(db, on_changed=self.invalidate, notify=self.show_status)
        self.upcoming = UpcomingPage(db, on_changed=self.invalidate, notify=self.show_status)
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
            ("Investments", "investments", self.investments),
            ("Upcoming", "upcoming", self.upcoming),
            ("Settings", "settings", self.settings),
        )
        for _title, _icon, page in pages:
            self.stack.addWidget(page)
        self.page_keys = (
            "dashboard",
            "accounts",
            "transactions",
            "investments",
            "upcoming",
            "settings",
        )
        self.dirty_pages = {
            "dashboard",
            "accounts",
            "transactions",
            "investments",
            "upcoming",
        }
        self.settings_repository = SettingsRepository(db)
        self.sidebar = Sidebar([(title, icon) for title, icon, _page in pages])
        self.sidebar.page_selected.connect(self._select_page)
        self.sidebar.state_changed.connect(self._sidebar_state_changed)
        self.sidebar_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        self.sidebar_shortcut.activated.connect(self.sidebar.toggle)

        root = QWidget()
        root.setObjectName("AppRoot")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        saved_sidebar_state = self.settings_repository.get(self.SIDEBAR_SETTING, "")
        self._sidebar_auto_mode = saved_sidebar_state == ""
        initial_collapsed = (
            self.width() < self.SIDEBAR_AUTO_COLLAPSE_WIDTH
            if self._sidebar_auto_mode
            else saved_sidebar_state == "1"
        )
        self.sidebar.set_collapsed(initial_collapsed, animate=False)
        self.statusBar().showMessage("Local database protected · Offline ready")
        self._select_page(0)

    def _select_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.sidebar.set_selected(index)
        self._refresh_selected_if_dirty()

    def invalidate(self, tags: set[str]) -> None:
        self.dirty_pages.update(
            tags & {"dashboard", "accounts", "transactions", "investments", "upcoming"}
        )
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

    def _sidebar_state_changed(self, collapsed: bool, user_initiated: bool) -> None:
        if not user_initiated:
            return
        self._sidebar_auto_mode = False
        with unit_of_work(self.db):
            self.settings_repository.set(self.SIDEBAR_SETTING, "1" if collapsed else "0")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "sidebar") and getattr(self, "_sidebar_auto_mode", False):
            self.sidebar.set_collapsed(
                self.width() < self.SIDEBAR_AUTO_COLLAPSE_WIDTH,
                animate=True,
            )
