from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.repositories.account_repository import AccountRepository
from app.services.dashboard_service import DashboardService
from app.services.net_worth_service import NetWorthService
from app.services.reporting_service import ReportingService
from app.ui.charts import CashFlowChart, NetWorthChart
from app.ui.components import (
    FittedLabel,
    amount_item,
    badge,
    badge_tone,
    clear_layout,
    compact_money,
    create_card,
    empty_state,
    fit_item_view_height,
    metric_card,
    page_layout,
    pretty_type,
    primary_button,
    secondary_button,
    section_heading,
    soft_button,
    style_table,
)
from app.ui.transaction_table_model import group_transaction_rows
from app.ui.theme import Colors
from app.utils.money import format_money
from app.utils.dates import format_display_date


class DashboardPage(QWidget):
    def __init__(
        self,
        db: sqlite3.Connection,
        on_add_transaction=None,
        on_add_transfer=None,
        on_add_account=None,
        on_add_investment=None,
        on_add_loan=None,
        on_add_recurring=None,
        on_backup=None,
        on_open_cash_flow_month=None,
    ):
        super().__init__()
        self.service = DashboardService(db)
        self.net_worth_service = NetWorthService(db)
        self.reporting = ReportingService(db)
        self.account_repo = AccountRepository(db)
        self.global_cards: dict[str, QLabel] = {}
        self.global_metric_cards: dict[str, QFrame] = {}
        self.scope_cards: dict[str, QLabel] = {}
        self.current_scope_id = "all"

        today = date.today().strftime("%A, %d %B")
        add_transaction = primary_button("Add transaction", "plus")
        add_transaction.clicked.connect(on_add_transaction or (lambda: None))
        layout = page_layout(
            self,
            "Dashboard",
            f"{today}  ·  A clear view of your money",
            add_transaction,
        )

        self.overview_grid = QGridLayout()
        self.overview_grid.setContentsMargins(0, 0, 0, 0)
        self.overview_grid.setSpacing(14)
        self.hero = self._build_hero()
        layout.addLayout(self.overview_grid)

        self.quick_actions = self._build_quick_actions(
            on_add_transfer,
            on_add_account,
            on_add_investment,
            on_add_loan,
            on_add_recurring,
        )
        layout.addWidget(self.quick_actions)

        layout.addWidget(
            section_heading(
                "Financial position",
                "The numbers that define your position today",
            )
        )

        self.global_metric_grid = QGridLayout()
        self.global_metric_grid.setContentsMargins(0, 0, 0, 0)
        self.global_metric_grid.setSpacing(14)
        self.global_metric_widgets: list[QWidget] = []
        global_metadata = {
            "total_assets": ("Total assets", "Assets and money lent", None),
            "liquidity": ("Available liquidity", "Cash and ready balances", None),
            "bank_overdraft": ("Bank overdraft", "Negative cash balances", "negative"),
            "investments_property": ("Investments & property", "Longer-term assets", None),
            "total_debt": ("Total debt", "Overdrafts, loans and liabilities", "negative"),
            "monthly_net_flow": ("Monthly net cash flow", "Income minus spending", None),
            "savings_rate": ("Savings rate", "Income kept after spending", None),
            "emergency_fund_coverage": (
                "Emergency-fund coverage",
                "Months of average spending covered",
                None,
            ),
        }
        for key in (
            "total_assets",
            "liquidity",
            "bank_overdraft",
            "total_debt",
            "investments_property",
            "monthly_net_flow",
            "savings_rate",
            "emergency_fund_coverage",
        ):
            label, helper, tone = global_metadata[key]
            initial_value = (
                "0.0%"
                if key == "savings_rate"
                else "0.0 months"
                if key == "emergency_fund_coverage"
                else format_money(0)
            )
            card, value = metric_card(
                label,
                initial_value,
                helper,
                tone,
                compact=key in {"savings_rate", "emergency_fund_coverage"},
            )
            self.global_cards[key] = value
            self.global_metric_cards[key] = card
            self.global_metric_widgets.append(card)
        layout.addLayout(self.global_metric_grid)

        self.forecast_card = self._build_forecast()
        layout.addWidget(self.forecast_card)

        self.budgets_card = self._build_budgets_card()
        layout.addWidget(self.budgets_card)

        self.scope_selector_card = self._build_scope_selector()
        layout.addWidget(self.scope_selector_card)

        self.scope_grid = QGridLayout()
        self.scope_grid.setContentsMargins(0, 0, 0, 0)
        self.scope_grid.setSpacing(14)
        self.scope_widgets: list[QWidget] = []
        scope_metadata = {
            "selected_balance": ("Selected balance", "Balance in this scope", None),
            "liquidity": ("Available liquidity", "Liquid balances in scope", None),
            "monthly_income": ("Income this month", "Money in for this scope", "positive"),
            "monthly_expenses": ("Spent this month", "Money out for this scope", "negative"),
            "monthly_net_flow": ("Net cash flow", "Income minus spending", None),
            "scope_children": ("Accounts & methods", "Child accounts / payment methods", None),
        }
        for key in ("selected_balance", "liquidity", "monthly_income", "monthly_expenses", "monthly_net_flow", "scope_children"):
            label, helper, tone = scope_metadata[key]
            card, value = metric_card(
                label,
                "0" if key == "scope_children" else format_money(0),
                helper,
                tone,
                compact=True,
            )
            self.scope_cards[key] = value
            self.scope_widgets.append(card)
        layout.addLayout(self.scope_grid)

        net_worth_card, net_worth_layout = create_card(
            "Net worth history",
            subtitle="Assets, liabilities, and your overall position over the last year",
        )
        self.net_worth_chart = NetWorthChart()
        net_worth_layout.addWidget(self.net_worth_chart)
        layout.addWidget(net_worth_card)

        cash_flow_card, cash_flow_layout = create_card(
            "Six-month cash flow",
            subtitle="Recorded income and expenses; transfers are excluded",
        )
        self.cash_flow_chart = CashFlowChart()
        self.cash_flow_chart.period_selected.connect(
            on_open_cash_flow_month or (lambda _month, _kind: None)
        )
        cash_flow_layout.addWidget(self.cash_flow_chart)
        layout.addWidget(cash_flow_card)

        add_account = secondary_button("Add account", "plus")
        add_account.clicked.connect(on_add_account or (lambda: None))
        recent_card, recent_layout = create_card(
            "Recent activity",
            subtitle="Your latest income, spending, and transfers",
        )
        self.recent_empty = empty_state(
            "No transactions yet", "Add your first income, expense, or transfer."
        )
        self.recent = QTableWidget(0, 5)
        self.recent.setHorizontalHeaderLabels(["Date", "Type", "Description", "Account", "Amount"])
        style_table(self.recent, visible_rows=6)
        recent_layout.addWidget(self.recent_empty)
        recent_layout.addWidget(self.recent)

        accounts_card, accounts_layout = create_card(
            "Your accounts",
            subtitle="Live balances across active accounts",
            action=add_account,
        )
        self.accounts_empty = empty_state(
            "No accounts yet", "Add your first bank, wallet, or cash account."
        )
        self.accounts = QTableWidget(0, 3)
        self.accounts.setHorizontalHeaderLabels(["Account", "Type", "Balance"])
        style_table(self.accounts, visible_rows=6)
        accounts_layout.addWidget(self.accounts_empty)
        accounts_layout.addWidget(self.accounts)

        self.content_grid = QGridLayout()
        self.content_grid.setContentsMargins(0, 0, 0, 0)
        self.content_grid.setSpacing(14)
        self.recent_card = recent_card
        self.accounts_card = accounts_card
        layout.addLayout(self.content_grid)
        layout.addStretch()
        self._layout_dashboard()

    def _build_hero(self) -> QFrame:
        hero = QFrame()
        hero.setProperty("role", "heroCard")
        hero.setMinimumHeight(152)
        hero.setMaximumHeight(166)
        layout = QVBoxLayout(hero)
        layout.setContentsMargins(26, 22, 26, 20)
        layout.setSpacing(6)
        label = QLabel("TOTAL NET WORTH")
        label.setProperty("role", "heroLabel")
        value = FittedLabel(format_money(0), maximum_size=38, minimum_size=18)
        value.setProperty("role", "heroValue")
        self.global_cards["net_worth"] = value
        self.hero_helper = QLabel("Across all banks, assets, and liabilities")
        self.hero_helper.setProperty("role", "heroHelper")
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 8, 0, 0)
        updated = QLabel("Stored locally  |  Updated just now")
        updated.setProperty("role", "heroHelper")
        bottom.addWidget(updated)
        bottom.addStretch()
        layout.addWidget(label)
        layout.addWidget(value)
        layout.addWidget(self.hero_helper)
        layout.addLayout(bottom)
        return hero

    def _build_quick_actions(
        self,
        on_add_transfer,
        on_add_account,
        on_add_investment,
        on_add_loan,
        on_add_recurring,
    ) -> QFrame:
        container = QFrame()
        container.setProperty("role", "quickActions")
        self.quick_action_layout = QGridLayout(container)
        self.quick_action_layout.setContentsMargins(0, 0, 0, 0)
        self.quick_action_layout.setSpacing(8)
        label = QLabel("CREATE")
        label.setProperty("role", "metricLabel")
        add_transfer = soft_button("Transfer", "transactions")
        add_account = secondary_button("Account", "plus")
        add_investment = secondary_button("Investment", "investments")
        add_loan = secondary_button("Loan", "loans")
        add_recurring = secondary_button("Schedule", "upcoming")
        add_transfer.setToolTip("Record a transfer")
        add_account.setToolTip("Add account")
        add_investment.setToolTip("Add investment")
        add_loan.setToolTip("Add borrowed or lent money")
        add_recurring.setToolTip("Add a recurring wage or payment")
        for button in (
            add_transfer,
            add_account,
            add_investment,
            add_loan,
            add_recurring,
        ):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        add_transfer.clicked.connect(on_add_transfer or (lambda: None))
        add_account.clicked.connect(on_add_account or (lambda: None))
        add_investment.clicked.connect(on_add_investment or (lambda: None))
        add_loan.clicked.connect(on_add_loan or (lambda: None))
        add_recurring.clicked.connect(on_add_recurring or (lambda: None))
        self.quick_action_label = label
        self.quick_action_buttons = (
            add_transfer,
            add_account,
            add_investment,
            add_loan,
            add_recurring,
        )
        return container

    def _build_scope_selector(self) -> QFrame:
        card = QFrame()
        card.setProperty("role", "scopeBar")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        self.scope_title = QLabel("Viewing: All accounts")
        self.scope_title.setProperty("role", "sectionTitle")
        self.scope_combo = QComboBox()
        self.scope_combo.setMinimumWidth(260)
        self.scope_combo.currentIndexChanged.connect(self._scope_changed)
        row.addWidget(self.scope_title)
        row.addStretch()
        row.addWidget(self.scope_combo)

        self.scope_caption = QLabel("Included: all active accounts")
        self.scope_caption.setProperty("role", "sectionSubtitle")
        self.scope_caption.setWordWrap(True)
        layout.addLayout(row)
        layout.addWidget(self.scope_caption)
        return card

    def _build_forecast(self) -> QFrame:
        card, layout = create_card(
            "Cash forecast",
            subtitle="Projected available liquidity from active recurring income and payments",
            role="forecastCard",
        )
        self.forecast_grid = QGridLayout()
        self.forecast_grid.setContentsMargins(0, 2, 0, 0)
        self.forecast_grid.setHorizontalSpacing(24)
        self.forecast_grid.setVerticalSpacing(14)

        self.forecast_status = QWidget()
        self.forecast_status.setProperty("role", "forecastStatus")
        status_layout = QVBoxLayout(self.forecast_status)
        status_layout.setContentsMargins(14, 8, 14, 8)
        status_layout.setSpacing(5)
        status_eyebrow = QLabel("6-MONTH DIRECTION")
        status_eyebrow.setProperty("role", "eyebrow")
        self.forecast_message = QLabel("No scheduled movement yet")
        self.forecast_message.setProperty("role", "forecastMessage")
        self.forecast_message.setWordWrap(True)
        self.forecast_detail = QLabel()
        self.forecast_detail.setProperty("role", "sectionSubtitle")
        self.forecast_detail.setWordWrap(True)
        status_layout.addWidget(status_eyebrow)
        status_layout.addWidget(self.forecast_message)
        status_layout.addWidget(self.forecast_detail)
        status_layout.addStretch()

        self.forecast_three, self.forecast_three_value, self.forecast_three_helper = (
            self._forecast_metric("IN 3 MONTHS")
        )
        self.forecast_six, self.forecast_six_value, self.forecast_six_helper = (
            self._forecast_metric("IN 6 MONTHS")
        )
        layout.addLayout(self.forecast_grid)
        return card

    def _build_budgets_card(self) -> QFrame:
        card, layout = create_card(
            "Budgets this month",
            subtitle="The categories closest to or beyond their monthly limit",
        )
        self.budgets_empty = empty_state(
            "No budgets yet", "Set a monthly category limit from the Budgets page."
        )
        self.budgets_table = QTableWidget(0, 4)
        self.budgets_table.setHorizontalHeaderLabels(
            ["Category", "Spent", "Limit", "Used"]
        )
        style_table(self.budgets_table, visible_rows=3)
        layout.addWidget(self.budgets_empty)
        layout.addWidget(self.budgets_table)
        return card

    @staticmethod
    def _forecast_metric(title: str) -> tuple[QWidget, QLabel, QLabel]:
        container = QWidget()
        container.setProperty("role", "forecastMetric")
        metric_layout = QVBoxLayout(container)
        metric_layout.setContentsMargins(8, 8, 8, 8)
        metric_layout.setSpacing(5)
        title_label = QLabel(title)
        title_label.setProperty("role", "metricLabel")
        value = FittedLabel(format_money(0), maximum_size=27, minimum_size=14)
        value.setProperty("role", "metricValue")
        value.setMinimumHeight(34)
        helper = QLabel("Scheduled change €0.00")
        helper.setProperty("role", "helper")
        metric_layout.addWidget(title_label)
        metric_layout.addWidget(value)
        metric_layout.addWidget(helper)
        metric_layout.addStretch()
        return container, value, helper

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_dashboard()

    def _layout_dashboard(self) -> None:
        if not hasattr(self, "overview_grid"):
            return
        width = max(1, self.width())
        self._layout_quick_actions(width)
        self._layout_forecast(width)
        clear_layout(self.overview_grid)
        for column in range(2):
            self.overview_grid.setColumnStretch(column, 0)
        self.overview_grid.addWidget(self.hero, 0, 0)
        self.overview_grid.setColumnStretch(0, 1)

        clear_layout(self.global_metric_grid)
        global_columns = 3 if width >= 1000 else 2 if width >= 620 else 1
        for column in range(global_columns):
            self.global_metric_grid.setColumnStretch(column, 1)
        for index, card in enumerate(self.global_metric_widgets):
            self.global_metric_grid.addWidget(card, index // global_columns, index % global_columns)

        clear_layout(self.scope_grid)
        scope_columns = 3 if width >= 1050 else 2 if width >= 620 else 1
        for column in range(scope_columns):
            self.scope_grid.setColumnStretch(column, 1)
        for index, card in enumerate(self.scope_widgets):
            self.scope_grid.addWidget(card, index // scope_columns, index % scope_columns)

        clear_layout(self.content_grid)
        for column in range(2):
            self.content_grid.setColumnStretch(column, 0)
        if width >= 1160:
            self.content_grid.addWidget(self.recent_card, 0, 0)
            self.content_grid.addWidget(self.accounts_card, 0, 1)
            self.content_grid.setColumnStretch(0, 2)
            self.content_grid.setColumnStretch(1, 1)
        else:
            self.content_grid.addWidget(self.recent_card, 0, 0)
            self.content_grid.addWidget(self.accounts_card, 1, 0)
            self.content_grid.setColumnStretch(0, 1)

    def _layout_forecast(self, width: int) -> None:
        if not hasattr(self, "forecast_grid"):
            return
        compact = width < 900
        if getattr(self, "_forecast_compact", None) == compact:
            return
        self._forecast_compact = compact
        clear_layout(self.forecast_grid)
        if compact:
            self.forecast_grid.addWidget(self.forecast_status, 0, 0, 1, 2)
            self.forecast_grid.addWidget(self.forecast_three, 1, 0)
            self.forecast_grid.addWidget(self.forecast_six, 1, 1)
            self.forecast_grid.setColumnStretch(0, 1)
            self.forecast_grid.setColumnStretch(1, 1)
        else:
            self.forecast_grid.addWidget(self.forecast_status, 0, 0)
            self.forecast_grid.addWidget(self.forecast_three, 0, 1)
            self.forecast_grid.addWidget(self.forecast_six, 0, 2)
            self.forecast_grid.setColumnStretch(0, 2)
            self.forecast_grid.setColumnStretch(1, 1)
            self.forecast_grid.setColumnStretch(2, 1)

    def _layout_quick_actions(self, width: int) -> None:
        if not hasattr(self, "quick_action_layout"):
            return
        compact = width < 1050
        if getattr(self, "_quick_actions_compact", None) == compact:
            return
        self._quick_actions_compact = compact
        clear_layout(self.quick_action_layout)
        if compact:
            self.quick_action_layout.addWidget(self.quick_action_label, 0, 0, 1, 3)
            for index, button in enumerate(self.quick_action_buttons):
                self.quick_action_layout.addWidget(button, 1 + index // 3, index % 3)
            for column in range(3):
                self.quick_action_layout.setColumnStretch(column, 1)
        else:
            self.quick_action_layout.addWidget(self.quick_action_label, 0, 0)
            for index, button in enumerate(self.quick_action_buttons, start=1):
                self.quick_action_layout.addWidget(button, 0, index)
                self.quick_action_layout.setColumnStretch(index, 1)

    def refresh(self) -> None:
        global_data = self.service.global_snapshot()
        self._populate_scope_selector()
        for key, label in self.global_cards.items():
            value = global_data[key]
            if key == "savings_rate":
                percentage = value * Decimal("100")
                label.setText(f"{percentage:.1f}%")
                label.setToolTip(f"Savings rate: {percentage:.2f}%")
                self._set_global_metric_tone(
                    key,
                    "positive" if value > 0 else "negative" if value < 0 else "neutral",
                )
                continue
            if key == "emergency_fund_coverage":
                label.setText(f"{value:.1f} months")
                label.setToolTip(f"Emergency-fund coverage: {value:.2f} months")
                if value < self.service.EMERGENCY_FUND_WARNING_MONTHS:
                    tone = "negative"
                elif value < self.service.EMERGENCY_FUND_HEALTHY_MONTHS:
                    tone = "warning"
                else:
                    tone = "positive"
                self._set_global_metric_tone(key, tone)
                continue
            full_value = format_money(value)
            label.setText(full_value if key == "net_worth" else compact_money(value))
            label.setToolTip(full_value)
            if key == "monthly_net_flow":
                tone = "positive" if value >= 0 else "negative"
                label.setProperty("tone", tone)
                label.style().unpolish(label)
                label.style().polish(label)
            if key == "liquidity":
                tone = "negative" if value < 0 else "neutral"
                label.setProperty("tone", tone)
                label.style().unpolish(label)
                label.style().polish(label)
            if key in {"bank_overdraft", "total_debt"}:
                tone = "negative" if value > 0 else "neutral"
                label.setProperty("tone", tone)
                label.style().unpolish(label)
                label.style().polish(label)
        self.hero_helper.setText(
            f"Across {len(global_data['accounts'])} active account{'s' if len(global_data['accounts']) != 1 else ''}, assets, and liabilities"
        )
        self._refresh_forecast(
            self.reporting.cash_forecast(starting_balance=global_data["liquidity"])
        )
        self._refresh_budgets(global_data["budget_statuses"])
        cash_flow = self.reporting.monthly_cash_flow()
        self.net_worth_chart.set_data(self.net_worth_service.history())
        self.cash_flow_chart.set_data(
            [
                (
                    item["month"],
                    item["label"],
                    item["income"],
                    item["expenses"],
                )
                for item in cash_flow
            ]
        )
        scoped_data = self.service.scope_summary(self.current_scope_id)
        self._refresh_scope(scoped_data)

    def _set_global_metric_tone(self, key: str, tone: str) -> None:
        label = self.global_cards[key]
        card = self.global_metric_cards[key]
        color = {
            "positive": Colors.POSITIVE,
            "negative": Colors.NEGATIVE,
            "warning": Colors.WARNING,
            "neutral": Colors.BORDER,
        }[tone]
        card.setProperty("tone", tone)
        label.setProperty("tone", tone)
        card.setStyleSheet(
            f'QFrame[role="metricCard"] {{ border-top: 3px solid {color}; }}'
        )
        label.setStyleSheet(
            f"color: {Colors.TEXT if tone == 'neutral' else color};"
        )
        for widget in (card, label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _refresh_budgets(self, statuses: list[dict]) -> None:
        self.budgets_empty.setVisible(not statuses)
        self.budgets_table.setVisible(bool(statuses))
        self.budgets_table.setRowCount(len(statuses))
        for row, status in enumerate(statuses):
            self.budgets_table.setItem(row, 0, QTableWidgetItem(status["category_name"]))
            self.budgets_table.setItem(row, 1, amount_item(status["spent"], neutral=True))
            self.budgets_table.setItem(row, 2, amount_item(status["limit"], neutral=True))
            used = QTableWidgetItem(f"{status['percent_used']:.2f}%")
            if status["percent_used"] > 100:
                used.setForeground(QColor("#ef7d7d"))
            elif status["percent_used"] >= 80:
                used.setForeground(QColor("#e6b65c"))
            else:
                used.setForeground(QColor("#72d6b2"))
            self.budgets_table.setItem(row, 3, used)
        fit_item_view_height(self.budgets_table, len(statuses), maximum_rows=3)

    def _refresh_forecast(self, data: dict) -> None:
        for value_label, helper_label, balance_key, change_key in (
            (
                self.forecast_three_value,
                self.forecast_three_helper,
                "three_month_balance",
                "three_month_change",
            ),
            (
                self.forecast_six_value,
                self.forecast_six_helper,
                "six_month_balance",
                "six_month_change",
            ),
        ):
            balance = data[balance_key]
            change = data[change_key]
            value_label.setText(compact_money(balance))
            value_label.setToolTip(format_money(balance))
            tone = "positive" if change > 0 else "negative" if change < 0 else "neutral"
            value_label.setProperty("tone", tone)
            value_label.style().unpolish(value_label)
            value_label.style().polish(value_label)
            signed_change = (
                f"+{format_money(change)}" if change > 0 else format_money(change)
            )
            helper_label.setText(f"Scheduled change {signed_change}")

        change = data["six_month_change"]
        if data["known_schedule_count"] == 0:
            tone = "neutral"
            message = "No scheduled movement yet"
            detail = "Add recurring wages and payments to calculate your direction."
        elif change < 0:
            tone = "negative"
            message = "Your available balance is forecast to decrease"
            detail = (
                f"Scheduled payments exceed income by {format_money(abs(change))} "
                "over the next six months."
            )
        elif change > 0:
            tone = "positive"
            message = "Your available balance is forecast to grow"
            detail = (
                f"Scheduled income exceeds payments by {format_money(change)} "
                "over the next six months."
            )
        else:
            tone = "neutral"
            message = "Your available balance is forecast to stay level"
            detail = "Scheduled income and payments are currently balanced."
        if data["unknown_amount_count"]:
            count = data["unknown_amount_count"]
            detail += f" {count} schedule{'s' if count != 1 else ''} without an estimate excluded."
        self.forecast_status.setProperty("tone", tone)
        self.forecast_status.style().unpolish(self.forecast_status)
        self.forecast_status.style().polish(self.forecast_status)
        self.forecast_message.setText(message)
        self.forecast_detail.setText(detail)

    def _refresh_scope(self, data: dict) -> None:
        self.scope_title.setText(f"Viewing: {data['scope_label']}")
        included = data.get("included_accounts", [])
        if data["scope_id"] == "all":
            included_text = "Included: all active accounts"
        elif not included:
            included_text = "Included: no active accounts"
        elif len(included) <= 4:
            included_text = f"Included: {', '.join(included)}"
        else:
            included_text = f"Included: {', '.join(included[:4])}, and {len(included) - 4} more"
        if data.get("payment_method_count"):
            included_text += f" · {data['payment_method_count']} payment method{'s' if data['payment_method_count'] != 1 else ''}"
        self.scope_caption.setText(included_text)

        for key, label in self.scope_cards.items():
            if key == "scope_children":
                child_count = data.get("child_account_count", 0)
                method_count = data.get("payment_method_count", 0)
                label.setText(f"{child_count} / {method_count}")
                continue
            full_value = format_money(data[key])
            label.setText(compact_money(data[key]))
            label.setToolTip(full_value)
            if key in {"selected_balance", "liquidity"}:
                tone = "negative" if data[key] < 0 else "neutral"
                label.setProperty("tone", tone)
                label.style().unpolish(label)
                label.style().polish(label)
            if key == "monthly_net_flow":
                tone = "positive" if data[key] >= 0 else "negative"
                label.setProperty("tone", tone)
                label.style().unpolish(label)
                label.style().polish(label)

        account_names = {
            account.id: account.name for account in self.account_repo.list(include_inactive=True)
        }
        recent_rows = group_transaction_rows(data["recent_transactions"])
        self.recent.setRowCount(len(recent_rows))
        for row_index, display_row in enumerate(recent_rows):
            transaction = display_row.selected_transaction()
            is_transfer = transaction.transfer_group_id is not None
            account_label = account_names.get(transaction.account_id, "Inactive account")
            outgoing = next(
                (item for item in display_row.transactions() if item.type == "transfer_out"),
                None,
            )
            incoming = next(
                (item for item in display_row.transactions() if item.type == "transfer_in"),
                None,
            )
            if outgoing and incoming:
                source = account_names.get(outgoing.account_id, "Inactive account")
                target = account_names.get(incoming.account_id, "Inactive account")
                account_label = f"{source} → {target}"
            values = [
                format_display_date(transaction.date),
                "",
                transaction.description or "No description",
                account_label,
                "",
            ]
            for col_index, value in enumerate(values):
                self.recent.setItem(row_index, col_index, QTableWidgetItem(str(value)))
            self.recent.setCellWidget(
                row_index,
                1,
                badge(
                    "Transfer" if is_transfer else "Loan" if transaction.loan_id else pretty_type(transaction.type),
                    badge_tone("transfer" if is_transfer else "loan" if transaction.loan_id else transaction.type),
                ),
            )
            self.recent.setItem(
                row_index,
                4,
                amount_item(
                    abs(transaction.amount) if is_transfer else transaction.amount,
                    neutral=is_transfer or transaction.type == "adjustment",
                ),
            )
        self.recent.setVisible(bool(recent_rows))
        self.recent_empty.setVisible(not recent_rows)
        fit_item_view_height(self.recent, len(recent_rows), maximum_rows=6)
        self.recent_card.setMaximumHeight(
            225 if not recent_rows else 112 + self.recent.maximumHeight()
        )

        accounts = data["accounts"][:8]
        self.accounts.setRowCount(len(accounts))
        for row_index, account in enumerate(accounts):
            self.accounts.setItem(row_index, 0, QTableWidgetItem(account["name"]))
            self.accounts.setItem(row_index, 2, amount_item(account["balance"], neutral=True))
            self.accounts.setCellWidget(
                row_index, 1, badge(pretty_type(account["type"]), "neutral")
            )
        self.accounts.setVisible(bool(accounts))
        self.accounts_empty.setVisible(not accounts)
        fit_item_view_height(self.accounts, len(accounts), maximum_rows=6)
        self.accounts_card.setMaximumHeight(
            225 if not accounts else 112 + self.accounts.maximumHeight()
        )

    def _populate_scope_selector(self) -> None:
        selected = self.current_scope_id
        self.scope_combo.blockSignals(True)
        self.scope_combo.clear()
        self.scope_combo.addItem("All accounts", "all")
        for account, depth in self._account_options():
            prefix = "  " * depth
            self.scope_combo.addItem(f"{prefix}{account.name}", account.id)
        index = self.scope_combo.findData(selected)
        if index < 0:
            self.current_scope_id = "all"
            index = 0
        self.scope_combo.setCurrentIndex(index)
        self.scope_combo.blockSignals(False)

    def _account_options(self) -> list[tuple[object, int]]:
        accounts = self.account_repo.list(include_inactive=False)
        children: dict[str | None, list[object]] = {}
        for account in accounts:
            children.setdefault(account.parent_id, []).append(account)
        for siblings in children.values():
            siblings.sort(key=lambda item: (item.display_order, item.name.lower()))
        options: list[tuple[object, int]] = []

        def walk(parent_id: str | None, depth: int) -> None:
            for account in children.get(parent_id, []):
                options.append((account, depth))
                if account.id is not None:
                    walk(account.id, depth + 1)

        walk(None, 0)
        return options

    def _scope_changed(self) -> None:
        scope_id = self.scope_combo.currentData()
        if not scope_id:
            return
        self.current_scope_id = scope_id
        self._refresh_scope(self.service.scope_summary(self.current_scope_id))
