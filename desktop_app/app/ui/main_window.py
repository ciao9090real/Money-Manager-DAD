from __future__ import annotations

import sqlite3

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.app_info import WINDOW_TITLE
from app.core.database import unit_of_work
from app.repositories.settings_repository import SettingsRepository
from app.services.auth_service import AuthService
from app.ui.accounts_page import AccountsPage
from app.ui.budgets_page import BudgetsPage
from app.ui.goals_page import GoalsPage
from app.ui.home_page import HomePage
from app.ui.investments_page import InvestmentsPage
from app.ui.loans_page import LoansPage
from app.ui.settings_page import SettingsPage
from app.ui.sidebar import Sidebar
from app.ui.styles import app_stylesheet
from app.ui.theme import Colors
from app.ui.transactions_page import TransactionsPage
from app.ui.upcoming_page import UpcomingPage
from app.ui.icons import icon
from app.ui.fonts import load_app_fonts
from app.ui.workspace import WorkspaceBar, WorkspaceRoute, WorkspaceSection
from app.ui.workspace_pages import (
    ActivityImportPage,
    CashForecastPage,
    NetWorthHistoryPage,
    PositionOverviewPage,
    ReconciliationPage,
)


class MainWindow(QMainWindow):
    SIDEBAR_SETTING = "ui.sidebar_collapsed"
    SIDEBAR_AUTO_COLLAPSE_WIDTH = 1160

    def __init__(
        self,
        db: sqlite3.Connection,
        *,
        auth_service: AuthService | None = None,
        on_lock_requested=None,
    ):
        super().__init__()
        self.db = db
        self.auth_service = auth_service or AuthService(db)
        self.on_lock_requested = on_lock_requested
        self._lock_pending = False
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(icon("accounts", Colors.PRIMARY, 32))
        self.resize(1280, 820)
        self.setMinimumSize(980, 680)
        application = QApplication.instance()
        load_app_fonts()
        if application:
            application.setStyleSheet(app_stylesheet())
        else:
            self.setStyleSheet(app_stylesheet())

        self.accounts = AccountsPage(db, on_changed=self.invalidate, notify=self.show_status)
        self.transactions = TransactionsPage(db, on_changed=self.invalidate, notify=self.show_status)
        self.budgets = BudgetsPage(db, on_changed=self.invalidate, notify=self.show_status)
        self.goals = GoalsPage(db, on_changed=self.invalidate, notify=self.show_status)
        self.investments = InvestmentsPage(db, on_changed=self.invalidate, notify=self.show_status)
        self.loans = LoansPage(db, on_changed=self.invalidate, notify=self.show_status)
        self.upcoming = UpcomingPage(db, on_changed=self.invalidate, notify=self.show_status)
        self.settings = SettingsPage(
            db,
            notify=self.show_status,
            on_changed=self.invalidate,
            auth_service=self.auth_service,
            on_lock_requested=self.request_lock,
        )
        self.home = HomePage(
            db, on_add_transaction=self.transactions.add_transaction
        )
        self.home.route_requested.connect(self.navigate)
        self.import_page = ActivityImportPage(
            db,
            on_import_statement=self.settings.import_card_statement,
            on_import_csv=self.settings.import_transactions,
            on_before_post=self.settings.create_local_recovery_backup,
            on_changed=self.invalidate,
            notify=self.show_status,
        )
        self.reconciliation = ReconciliationPage(
            db,
            on_import_statement=self.settings.import_card_statement
        )
        self.cash_forecast = CashForecastPage(
            db,
            on_add_recurring=self.upcoming.add_rule,
            on_open_cash_flow_month=self._open_transactions_month,
        )
        # Kept as a compatibility alias for integrations that previously opened
        # the dashboard cash-flow chart directly.
        self.dashboard = self.cash_forecast
        self.debt_payoff = LoansPage(
            db, on_changed=self.invalidate, notify=self.show_status
        )
        self.position = PositionOverviewPage(
            db, on_add_account=self.accounts.add_account
        )
        self.net_worth_history = NetWorthHistoryPage(db)

        pages = (
            ("home", self.home),
            ("transactions", self.transactions),
            ("import", self.import_page),
            ("reconciliation", self.reconciliation),
            ("upcoming", self.upcoming),
            ("budgets", self.budgets),
            ("dashboard", self.cash_forecast),
            ("goals", self.goals),
            ("debt_payoff", self.debt_payoff),
            ("position", self.position),
            ("accounts", self.accounts),
            ("investments", self.investments),
            ("loans", self.loans),
            ("net_worth_history", self.net_worth_history),
            ("settings", self.settings),
        )
        self.stack = QStackedWidget()
        for _key, page in pages:
            self.stack.addWidget(page)
        self.page_keys = tuple(key for key, _page in pages)
        self.page_by_key = dict(pages)
        self.workspace_keys = ("home", "activity", "plan", "position", "settings")
        self.workspace_sections = {
            "activity": (
                WorkspaceSection("transactions", "Transactions"),
                WorkspaceSection("import", "Import"),
                WorkspaceSection("reconciliation", "Reconciliation"),
                WorkspaceSection("recurring", "Recurring"),
            ),
            "plan": (
                WorkspaceSection("monthly", "Monthly plan"),
                WorkspaceSection("forecast", "Cash forecast"),
                WorkspaceSection("goals", "Goals"),
                WorkspaceSection("debt", "Debt payoff"),
            ),
            "position": (
                WorkspaceSection("overview", "Overview"),
                WorkspaceSection("accounts", "Accounts"),
                WorkspaceSection("investments", "Investments"),
                WorkspaceSection("loans", "Loans"),
                WorkspaceSection("history", "Net-worth history"),
            ),
        }
        self.workspace_defaults = {
            "home": WorkspaceRoute("home", "home"),
            "activity": WorkspaceRoute("activity", "transactions"),
            "plan": WorkspaceRoute("plan", "monthly"),
            "position": WorkspaceRoute("position", "overview"),
            "settings": WorkspaceRoute("settings", "settings"),
        }
        self.route_pages = {
            ("home", "home"): "home",
            ("activity", "transactions"): "transactions",
            ("activity", "import"): "import",
            ("activity", "reconciliation"): "reconciliation",
            ("activity", "recurring"): "upcoming",
            ("plan", "monthly"): "budgets",
            ("plan", "forecast"): "dashboard",
            ("plan", "goals"): "goals",
            ("plan", "debt"): "debt_payoff",
            ("position", "overview"): "position",
            ("position", "accounts"): "accounts",
            ("position", "investments"): "investments",
            ("position", "loans"): "loans",
            ("position", "history"): "net_worth_history",
            ("settings", "settings"): "settings",
        }
        self.page_routes = {
            page_key: WorkspaceRoute(workspace, section)
            for (workspace, section), page_key in self.route_pages.items()
        }
        self.dirty_pages = set(self.page_keys) - {"settings"}

        sidebar_items = [
            (
                "Home",
                "dashboard",
                "Attention · Safe to spend · Upcoming · Recent",
            ),
            (
                "Activity",
                "transactions",
                "Transactions · Import · Reconciliation · Recurring",
            ),
            (
                "Plan",
                "upcoming",
                "Monthly plan · Cash forecast · Goals · Debt payoff",
            ),
            (
                "Position",
                "investments",
                "Overview · Accounts · Investments · Loans · History",
            ),
            ("Settings", "settings", ""),
        ]
        self.settings_repository = SettingsRepository(db)
        self.sidebar = Sidebar(sidebar_items)
        self.sidebar.page_selected.connect(self._select_workspace)
        self.sidebar.state_changed.connect(self._sidebar_state_changed)
        self.sidebar_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        self.sidebar_shortcut.activated.connect(self.sidebar.toggle)

        self.workspace_bar = WorkspaceBar()
        self.workspace_bar.route_requested.connect(self.navigate)
        content_shell = QWidget()
        content_shell.setObjectName("ContentRoot")
        content_layout = QVBoxLayout(content_shell)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.workspace_bar)
        content_layout.addWidget(self.stack, 1)

        root = QWidget()
        root.setObjectName("AppRoot")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(content_shell, 1)
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
        self.navigate(self.workspace_defaults["home"])

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

    def _select_workspace(self, index: int) -> None:
        if not 0 <= index < len(self.workspace_keys):
            return
        self.navigate(self.workspace_defaults[self.workspace_keys[index]])

    def _select_page(self, index: int) -> None:
        """Select a concrete page, retained for older integrations and tests."""

        if not 0 <= index < len(self.page_keys):
            return
        key = self.page_keys[index]
        self.navigate(self.page_routes[key])

    def navigate(self, route: WorkspaceRoute) -> None:
        page_key = self.route_pages.get((route.workspace, route.section))
        if page_key is None:
            return
        self.current_route = route
        self.stack.setCurrentWidget(self.page_by_key[page_key])
        self.sidebar.set_selected(self.workspace_keys.index(route.workspace))
        sections = self.workspace_sections.get(route.workspace)
        self.workspace_bar.setVisible(bool(sections))
        if sections:
            self.workspace_bar.configure(route.workspace, sections, route.section)
        self._refresh_selected_if_dirty()
        QTimer.singleShot(0, lambda: self._apply_route_target(route))

    def _apply_route_target(self, route: WorkspaceRoute) -> None:
        page = self.stack.currentWidget()
        if route.action == "add":
            action = getattr(
                page,
                {
                    "accounts": "add_account",
                    "transactions": "add_transaction",
                }.get(route.section, ""),
                None,
            )
            if action:
                action()
                return
        if route.entity_id:
            selector = getattr(page, "select_entity", None)
            if selector:
                selector(route.entity_id)

    def _open_transactions_month(self, month_key: str, transaction_type: str) -> None:
        self.transactions.set_month_filter(month_key, transaction_type)
        self.dirty_pages.discard("transactions")
        self.navigate(WorkspaceRoute("activity", "transactions"))

    def invalidate(self, tags: set[str]) -> None:
        expanded_tags = set(tags)
        if "transactions" in tags:
            expanded_tags.update({"budgets", "goals"})
        if tags & {"accounts", "investments", "loans"}:
            expanded_tags.add("goals")
        tag_pages = {
            "accounts": {"accounts", "position", "dashboard", "home"},
            "transactions": {
                "transactions",
                "position",
                "dashboard",
                "budgets",
                "goals",
                "home",
                "net_worth_history",
            },
            "budgets": {"budgets", "home"},
            "goals": {"goals", "home"},
            "investments": {
                "investments",
                "position",
                "home",
                "net_worth_history",
            },
            "loans": {
                "loans",
                "debt_payoff",
                "position",
                "home",
                "net_worth_history",
            },
            "upcoming": {"upcoming", "dashboard", "home"},
            "dashboard": {
                "home",
                "position",
                "dashboard",
                "net_worth_history",
            },
            "imports": {"import", "reconciliation", "home"},
        }
        for tag in expanded_tags:
            self.dirty_pages.update(tag_pages.get(tag, {tag}))
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

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if (
            event.type() == QEvent.Type.WindowStateChange
            and self.isMinimized()
            and self.on_lock_requested is not None
        ):
            QTimer.singleShot(0, self.request_lock)

    def request_lock(self) -> None:
        if self._lock_pending or self.on_lock_requested is None:
            return
        self._lock_pending = True
        try:
            self.on_lock_requested()
        finally:
            self._lock_pending = False

    def closeEvent(self, event) -> None:
        self.settings.shutdown_sync()
        super().closeEvent(event)
