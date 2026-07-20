from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from app.core.app_info import WINDOW_TITLE
from app.core.database import unit_of_work
from app.repositories.settings_repository import SettingsRepository
from app.ui.accounts_page import AccountsPage
from app.ui.budgets_page import BudgetsPage
from app.ui.dashboard_page import DashboardPage
from app.ui.investments_page import InvestmentsPage
from app.ui.loans_page import LoansPage
from app.ui.settings_page import SettingsPage
from app.ui.sidebar import Sidebar
from app.ui.styles import app_stylesheet
from app.ui.theme import Colors
from app.ui.transactions_page import TransactionsPage
from app.ui.upcoming_page import UpcomingPage
from app.ui.icons import icon


class MainWindow(QMainWindow):
    SIDEBAR_SETTING = "ui.sidebar_collapsed"
    SIDEBAR_AUTO_COLLAPSE_WIDTH = 1120

    def __init__(self, db: sqlite3.Connection):
        super().__init__()
        self.db = db
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(icon("accounts", Colors.PRIMARY, 32))
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
        self.budgets = BudgetsPage(db, on_changed=self.invalidate, notify=self.show_status)
        self.investments = InvestmentsPage(db, on_changed=self.invalidate, notify=self.show_status)
        self.loans = LoansPage(db, on_changed=self.invalidate, notify=self.show_status)
        self.upcoming = UpcomingPage(db, on_changed=self.invalidate, notify=self.show_status)
        self.settings = SettingsPage(db, notify=self.show_status, on_changed=self.invalidate)
        self.dashboard = DashboardPage(
            db,
            on_add_transaction=self.transactions.add_transaction,
            on_add_transfer=lambda: self.transactions.add_transaction("transfer"),
            on_add_account=self.accounts.add_account,
            on_add_investment=self.investments.add_investment,
            on_add_loan=self.loans.add_loan,
            on_add_recurring=self.upcoming.add_rule,
            on_backup=self.settings.create_backup,
            on_open_cash_flow_month=self._open_transactions_month,
        )

        pages = (
            ("Dashboard", "dashboard", self.dashboard),
            ("Accounts", "accounts", self.accounts),
            ("Transactions", "transactions", self.transactions),
            ("Budgets", "transactions", self.budgets),
            ("Investments", "investments", self.investments),
            ("Loans", "loans", self.loans),
            ("Upcoming", "upcoming", self.upcoming),
            ("Settings", "settings", self.settings),
        )
        for _title, _icon, page in pages:
            self.stack.addWidget(page)
        self.page_keys = (
            "dashboard",
            "accounts",
            "transactions",
            "budgets",
            "investments",
            "loans",
            "upcoming",
            "settings",
        )
        self.dirty_pages = {
            "dashboard",
            "accounts",
            "transactions",
            "budgets",
            "investments",
            "loans",
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
        self._build_status_toast(root)
        saved_sidebar_state = self.settings_repository.get(self.SIDEBAR_SETTING, "")
        self._sidebar_auto_mode = saved_sidebar_state == ""
        initial_collapsed = (
            self.width() < self.SIDEBAR_AUTO_COLLAPSE_WIDTH
            if self._sidebar_auto_mode
            else saved_sidebar_state == "1"
        )
        self.sidebar.set_collapsed(initial_collapsed, animate=False)
        self._select_page(0)

    def _build_status_toast(self, parent: QWidget) -> None:
        self.status_toast = QFrame(parent)
        self.status_toast.setProperty("role", "toast")
        self.status_toast.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        toast_layout = QHBoxLayout(self.status_toast)
        toast_layout.setContentsMargins(13, 10, 14, 10)
        toast_layout.setSpacing(9)

        status_dot = QFrame()
        status_dot.setProperty("role", "toastDot")
        status_dot.setFixedSize(8, 8)
        self.status_toast_label = QLabel()
        self.status_toast_label.setProperty("role", "toastText")
        self.status_toast_label.setMaximumWidth(380)
        toast_layout.addWidget(status_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        toast_layout.addWidget(self.status_toast_label)

        self.status_toast.hide()
        self.status_toast_timer = QTimer(self)
        self.status_toast_timer.setSingleShot(True)
        self.status_toast_timer.timeout.connect(self.status_toast.hide)

    def _select_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.sidebar.set_selected(index)
        self._refresh_selected_if_dirty()

    def _open_transactions_month(self, month_key: str, transaction_type: str) -> None:
        self.transactions.set_month_filter(month_key, transaction_type)
        self.dirty_pages.discard("transactions")
        self._select_page(self.page_keys.index("transactions"))

    def invalidate(self, tags: set[str]) -> None:
        self.dirty_pages.update(
            tags & {"dashboard", "accounts", "transactions", "budgets", "investments", "loans", "upcoming"}
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
        message = message.strip()
        if not message:
            return
        self.status_toast_label.setText(message)
        self.status_toast.adjustSize()
        self._position_status_toast()
        self.status_toast.show()
        self.status_toast.raise_()
        self.status_toast_timer.start(3500)

    def _position_status_toast(self) -> None:
        if not hasattr(self, "status_toast"):
            return
        self.status_toast.adjustSize()
        parent = self.status_toast.parentWidget()
        margin = 18
        x = max(margin, parent.width() - self.status_toast.width() - margin)
        y = max(margin, parent.height() - self.status_toast.height() - margin)
        self.status_toast.move(x, y)

    def _sidebar_state_changed(self, collapsed: bool, user_initiated: bool) -> None:
        if not user_initiated:
            return
        self._sidebar_auto_mode = False
        with unit_of_work(self.db):
            self.settings_repository.set(self.SIDEBAR_SETTING, "1" if collapsed else "0")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_status_toast()
        if hasattr(self, "sidebar") and getattr(self, "_sidebar_auto_mode", False):
            self.sidebar.set_collapsed(
                self.width() < self.SIDEBAR_AUTO_COLLAPSE_WIDTH,
                animate=True,
            )

    def closeEvent(self, event) -> None:
        self.settings.shutdown_sync()
        super().closeEvent(event)
