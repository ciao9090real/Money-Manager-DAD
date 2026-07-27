from __future__ import annotations

import sqlite3
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.dashboard_service import DashboardService
from app.services.import_inbox_service import ImportInboxService
from app.services.net_worth_service import NetWorthService
from app.services.reporting_service import ReportingService
from app.repositories.category_repository import CategoryRepository
from app.ui.charts import CashFlowChart, NetWorthChart
from app.ui.components import (
    BadgeDelegate,
    FittedLabel,
    amount_item,
    apply_soft_shadow,
    badge_tone,
    clear_layout,
    compact_money,
    create_card,
    danger_button,
    empty_state,
    fit_item_view_height,
    metric_card,
    page_layout,
    primary_button,
    secondary_button,
    style_table,
)
from app.ui.theme import Colors
from app.utils.money import format_money


class CashForecastPage(QWidget):
    """The planning projection extracted from the former mixed dashboard."""

    def __init__(
        self,
        db: sqlite3.Connection,
        *,
        on_add_recurring=None,
        on_open_cash_flow_month=None,
    ):
        super().__init__()
        self.reporting = ReportingService(db)
        add_schedule = primary_button("Add schedule", "plus")
        add_schedule.clicked.connect(on_add_recurring or (lambda: None))
        layout = page_layout(
            self,
            "Cash forecast",
            "See where recorded income and scheduled commitments are taking you",
            add_schedule,
        )

        self.direction_card = QFrame()
        self.direction_card.setProperty("role", "forecastHero")
        apply_soft_shadow(self.direction_card, blur_radius=30, y_offset=6, alpha=18)
        hero_layout = QHBoxLayout(self.direction_card)
        hero_layout.setContentsMargins(30, 26, 30, 26)
        hero_layout.setSpacing(30)

        message_block = QVBoxLayout()
        message_block.setSpacing(6)
        eyebrow = QLabel("6-MONTH DIRECTION")
        eyebrow.setProperty("role", "homeEyebrow")
        self.forecast_message = QLabel("No scheduled movement yet")
        self.forecast_message.setProperty("role", "forecastHeroTitle")
        self.forecast_message.setWordWrap(True)
        self.forecast_detail = QLabel()
        self.forecast_detail.setProperty("role", "sectionSubtitle")
        self.forecast_detail.setWordWrap(True)
        message_block.addWidget(eyebrow)
        message_block.addWidget(self.forecast_message)
        message_block.addWidget(self.forecast_detail)
        hero_layout.addLayout(message_block, 3)

        self.six_month_value = FittedLabel(
            format_money(Decimal("0")), maximum_size=36, minimum_size=17
        )
        self.six_month_value.setProperty("role", "forecastHeroValue")
        self.six_month_value.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        hero_layout.addWidget(self.six_month_value, 2)
        layout.addWidget(self.direction_card)

        self.metric_grid = QGridLayout()
        self.metric_grid.setContentsMargins(0, 0, 0, 0)
        self.metric_grid.setSpacing(14)
        self.metric_widgets: list[QWidget] = []
        self.metric_values: dict[str, QLabel] = {}
        for key, label, helper, tone in (
            ("current_balance", "Available now", "Current liquid balance", None),
            ("three_month_balance", "In three months", "After known schedules", None),
            ("six_month_income", "Scheduled income", "Next six months", "positive"),
            (
                "six_month_outgoings",
                "Scheduled outgoings",
                "Next six months",
                "negative",
            ),
        ):
            card, value = metric_card(label, format_money(0), helper, tone)
            self.metric_widgets.append(card)
            self.metric_values[key] = value
        layout.addLayout(self.metric_grid)

        chart_card, chart_layout = create_card(
            "Recorded cash flow",
            subtitle="Six months of income and expenses; transfers are excluded",
        )
        self.cash_flow_chart = CashFlowChart()
        self.cash_flow_chart.period_selected.connect(
            on_open_cash_flow_month or (lambda _month, _kind: None)
        )
        chart_layout.addWidget(self.cash_flow_chart)
        layout.addWidget(chart_card)
        layout.addStretch()
        self._layout_metrics()

    def refresh(self) -> None:
        forecast = self.reporting.cash_forecast()
        for key, label in self.metric_values.items():
            label.setText(compact_money(forecast[key]))
            label.setToolTip(format_money(forecast[key]))
        self.six_month_value.setText(format_money(forecast["six_month_balance"]))

        change = forecast["six_month_change"]
        if forecast["known_schedule_count"] == 0:
            tone = "neutral"
            title = "No scheduled movement yet"
            detail = "Add recurring income and payments to calculate a direction."
        elif change < 0:
            tone = "negative"
            title = "Available cash is forecast to decrease"
            detail = (
                f"Known commitments exceed scheduled income by "
                f"{format_money(abs(change))} over six months."
            )
        elif change > 0:
            tone = "positive"
            title = "Available cash is forecast to grow"
            detail = (
                f"Scheduled income exceeds known commitments by "
                f"{format_money(change)} over six months."
            )
        else:
            tone = "neutral"
            title = "Available cash is forecast to stay level"
            detail = "Known scheduled income and payments are balanced."
        if forecast["unknown_amount_count"]:
            count = forecast["unknown_amount_count"]
            detail += (
                f" {count} variable schedule{'s are' if count != 1 else ' is'} "
                "excluded because no estimate is recorded."
            )
        self.direction_card.setProperty("tone", tone)
        self.direction_card.style().unpolish(self.direction_card)
        self.direction_card.style().polish(self.direction_card)
        self.forecast_message.setText(title)
        self.forecast_detail.setText(detail)

        cash_flow = self.reporting.monthly_cash_flow()
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

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_metrics()

    def _layout_metrics(self) -> None:
        if not hasattr(self, "metric_grid"):
            return
        columns = 4 if self.width() >= 940 else 2
        if getattr(self, "_metric_columns", None) == columns:
            return
        self._metric_columns = columns
        clear_layout(self.metric_grid)
        for column in range(4):
            self.metric_grid.setColumnStretch(column, 1 if column < columns else 0)
        for index, card in enumerate(self.metric_widgets):
            self.metric_grid.addWidget(card, index // columns, index % columns)


class PositionOverviewPage(QWidget):
    """A compact balance-sheet view without planning or activity duplication."""

    def __init__(self, db: sqlite3.Connection, *, on_add_account=None):
        super().__init__()
        self.dashboard = DashboardService(db)
        self.net_worth = NetWorthService(db)
        add_account = primary_button("Add account", "plus")
        add_account.clicked.connect(on_add_account or (lambda: None))
        layout = page_layout(
            self,
            "Your position",
            "A clear view of what you own, what you owe, and what is available",
            add_account,
        )

        hero = QFrame()
        hero.setProperty("role", "positionHero")
        hero.setMinimumHeight(178)
        apply_soft_shadow(hero, blur_radius=32, y_offset=7, alpha=19)
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(32, 26, 32, 26)
        hero_layout.setSpacing(28)
        value_block = QVBoxLayout()
        value_block.setSpacing(5)
        eyebrow = QLabel("TOTAL NET WORTH")
        eyebrow.setProperty("role", "homeEyebrow")
        self.net_worth_value = FittedLabel(
            format_money(0), maximum_size=48, minimum_size=20
        )
        self.net_worth_value.setProperty("role", "positionValue")
        self.position_detail = QLabel("Across no active accounts")
        self.position_detail.setProperty("role", "sectionSubtitle")
        value_block.addWidget(eyebrow)
        value_block.addWidget(self.net_worth_value)
        value_block.addWidget(self.position_detail)
        hero_layout.addLayout(value_block, 3)

        self.hero_assets = self._hero_fact("ASSETS")
        self.hero_debt = self._hero_fact("OWED")
        hero_layout.addWidget(self.hero_assets[0], 1)
        hero_layout.addWidget(self.hero_debt[0], 1)
        layout.addWidget(hero)

        self.metric_grid = QGridLayout()
        self.metric_grid.setContentsMargins(0, 0, 0, 0)
        self.metric_grid.setSpacing(14)
        self.metric_widgets: list[QWidget] = []
        self.metric_values: dict[str, QLabel] = {}
        for key, label, helper, tone in (
            ("liquidity", "Liquid balance", "Bank, cash, and wallets", None),
            (
                "investments_property",
                "Investments",
                "Investments and property",
                None,
            ),
            ("loan_receivables", "Money lent", "Principal due back", "positive"),
            ("borrowed_loans", "Borrowed", "Principal outstanding", "negative"),
        ):
            card, value = metric_card(label, format_money(0), helper, tone)
            self.metric_widgets.append(card)
            self.metric_values[key] = value
        layout.addLayout(self.metric_grid)

        content_grid = QGridLayout()
        content_grid.setContentsMargins(0, 0, 0, 0)
        content_grid.setSpacing(18)

        chart_card, chart_layout = create_card(
            "Net-worth direction",
            subtitle="Assets less liabilities over the last year",
        )
        self.history_chart = NetWorthChart()
        chart_layout.addWidget(self.history_chart)

        accounts_card, accounts_layout = create_card(
            "Accounts",
            subtitle="Live balances across active accounts",
        )
        self.accounts_empty = empty_state(
            "No accounts yet", "Add a bank, wallet, cash, or asset account."
        )
        self.accounts_table = QTableWidget(0, 2)
        self.accounts_table.setHorizontalHeaderLabels(["Account", "Balance"])
        style_table(self.accounts_table)
        header = self.accounts_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        accounts_layout.addWidget(self.accounts_empty)
        accounts_layout.addWidget(self.accounts_table)

        content_grid.addWidget(chart_card, 0, 0)
        content_grid.addWidget(accounts_card, 0, 1)
        content_grid.setColumnStretch(0, 3)
        content_grid.setColumnStretch(1, 2)
        layout.addLayout(content_grid)
        layout.addStretch()
        self._layout_metrics()

    @staticmethod
    def _hero_fact(label: str) -> tuple[QWidget, QLabel]:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 22, 0, 0)
        layout.setSpacing(5)
        caption = QLabel(label)
        caption.setProperty("role", "homeEyebrow")
        value = QLabel(format_money(0))
        value.setProperty("role", "positionFact")
        layout.addWidget(caption)
        layout.addWidget(value)
        layout.addStretch()
        return widget, value

    def refresh(self) -> None:
        snapshot = self.dashboard.global_snapshot()
        self.net_worth_value.setText(format_money(snapshot["net_worth"]))
        count = len(snapshot["accounts"])
        self.position_detail.setText(
            f"Across {count} active account{'s' if count != 1 else ''}"
        )
        self.hero_assets[1].setText(compact_money(snapshot["total_assets"]))
        self.hero_assets[1].setToolTip(format_money(snapshot["total_assets"]))
        self.hero_debt[1].setText(compact_money(snapshot["total_debt"]))
        self.hero_debt[1].setToolTip(format_money(snapshot["total_debt"]))
        self.hero_debt[1].setProperty(
            "tone", "negative" if snapshot["total_debt"] > 0 else "neutral"
        )
        for key, label in self.metric_values.items():
            label.setText(compact_money(snapshot[key]))
            label.setToolTip(format_money(snapshot[key]))

        points = self.net_worth.history()
        self.history_chart.set_data(points)

        accounts = snapshot["accounts"]
        self.accounts_table.setRowCount(len(accounts))
        for row, account in enumerate(accounts):
            self.accounts_table.setItem(row, 0, QTableWidgetItem(account["name"]))
            self.accounts_table.setItem(
                row, 1, amount_item(account["balance"], neutral=True)
            )
        self.accounts_empty.setVisible(not accounts)
        self.accounts_table.setVisible(bool(accounts))
        if accounts:
            fit_item_view_height(self.accounts_table, len(accounts), maximum_rows=7)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_metrics()

    def _layout_metrics(self) -> None:
        if not hasattr(self, "metric_grid"):
            return
        columns = 4 if self.width() >= 940 else 2
        if getattr(self, "_metric_columns", None) == columns:
            return
        self._metric_columns = columns
        clear_layout(self.metric_grid)
        for column in range(4):
            self.metric_grid.setColumnStretch(column, 1 if column < columns else 0)
        for index, card in enumerate(self.metric_widgets):
            self.metric_grid.addWidget(card, index // columns, index % columns)


class NetWorthHistoryPage(QWidget):
    def __init__(self, db: sqlite3.Connection):
        super().__init__()
        self.service = NetWorthService(db)
        layout = page_layout(
            self,
            "Net-worth history",
            "Follow the long-term direction of assets, liabilities, and your position",
        )
        self.metrics = QGridLayout()
        self.metrics.setContentsMargins(0, 0, 0, 0)
        self.metrics.setSpacing(14)
        self.values: dict[str, QLabel] = {}
        for column, (key, label, tone) in enumerate(
            (
                ("net_worth", "Current net worth", None),
                ("assets", "Gross assets", "positive"),
                ("liabilities", "Gross liabilities", "negative"),
            )
        ):
            card, value = metric_card(label, format_money(0), tone=tone)
            self.values[key] = value
            self.metrics.addWidget(card, 0, column)
            self.metrics.setColumnStretch(column, 1)
        layout.addLayout(self.metrics)
        card, card_layout = create_card(
            "Twelve-month direction",
            subtitle="Estimated month-end points are used when no recorded snapshot exists",
        )
        self.chart = NetWorthChart()
        card_layout.addWidget(self.chart)
        layout.addWidget(card)
        self.note = QLabel()
        self.note.setProperty("role", "sectionSubtitle")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        layout.addStretch()

    def refresh(self) -> None:
        point = self.service.current()
        history = self.service.history()
        self.values["net_worth"].setText(compact_money(point.net_worth))
        self.values["assets"].setText(compact_money(point.assets))
        self.values["liabilities"].setText(compact_money(point.liabilities))
        for key, value in (
            ("net_worth", point.net_worth),
            ("assets", point.assets),
            ("liabilities", point.liabilities),
        ):
            self.values[key].setToolTip(format_money(value))
        self.chart.set_data(history)
        estimated = sum(1 for item in history if item.estimated)
        self.note.setText(
            f"{estimated} of {len(history)} points are reconstructed from the ledger."
            if estimated
            else "Every displayed point has an exact recorded value."
        )


class ActivityImportPage(QWidget):
    STATUS_LABELS = {
        "needs_category": "Needs category",
        "ready": "Ready",
        "duplicate": "Duplicate",
        "ignored": "Ignored",
        "posted": "Posted",
        "error": "Needs fixing",
    }

    def __init__(
        self,
        db: sqlite3.Connection,
        *,
        on_import_statement=None,
        on_import_csv=None,
        on_before_post=None,
        on_changed=None,
        notify=None,
    ):
        super().__init__()
        self.db = db
        self.inbox = ImportInboxService(db)
        self.categories = CategoryRepository(db)
        self.on_import_statement = on_import_statement or (lambda: None)
        self.on_import_csv = on_import_csv or (lambda: None)
        self.on_before_post = on_before_post or (lambda: True)
        self.on_changed = on_changed or (lambda _tags: None)
        self.notify = notify or (lambda _message: None)
        self._selected_batch_id: str | None = None
        self._batch_summaries = []

        header_actions = QWidget()
        header_actions_layout = QHBoxLayout(header_actions)
        header_actions_layout.setContentsMargins(0, 0, 0, 0)
        header_actions_layout.setSpacing(8)
        csv_button = secondary_button("Import CSV", "download")
        csv_button.clicked.connect(self._import_csv)
        statement = primary_button("Import statement", "download")
        statement.clicked.connect(self._import_statement)
        header_actions_layout.addWidget(csv_button)
        header_actions_layout.addWidget(statement)
        layout = page_layout(
            self,
            "Import inbox",
            "Review bank rows safely, resolve exceptions, then post only what is ready",
            header_actions,
        )

        self.summary_board = QFrame()
        self.summary_board.setProperty("role", "metricBoard")
        summary_layout = QHBoxLayout(self.summary_board)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(0)
        self.summary_values: dict[str, QLabel] = {}
        for index, (key, label) in enumerate(
            (
                ("open_batches", "OPEN IMPORTS"),
                ("ready", "READY TO POST"),
                ("needs_category", "NEED A CATEGORY"),
                ("errors", "NEED FIXING"),
            )
        ):
            cell = QFrame()
            cell.setProperty("role", "metricCell")
            cell.setProperty("divider", index > 0)
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(22, 16, 22, 16)
            cell_layout.setSpacing(3)
            caption = QLabel(label)
            caption.setProperty("role", "eyebrow")
            value = QLabel("0")
            value.setProperty("role", "detailTitle")
            cell_layout.addWidget(caption)
            cell_layout.addWidget(value)
            summary_layout.addWidget(cell, 1)
            self.summary_values[key] = value
        layout.addWidget(self.summary_board)

        batches_card, batches_layout = create_card(
            "Imports",
            subtitle="Select a file to review its rows and posting status",
        )
        self.batches_empty = empty_state(
            "Your inbox is clear",
            "Import a bank statement or Money Manager CSV to start a review.",
        )
        self.batches_table = QTableWidget(0, 5)
        self.batches_table.setHorizontalHeaderLabels(
            ["Source", "Scope", "Review", "Status", "Added"]
        )
        style_table(self.batches_table)
        self.batches_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.batches_table.itemSelectionChanged.connect(
            self._batch_selection_changed
        )
        batch_header = self.batches_table.horizontalHeader()
        batch_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        batch_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        batch_header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        batch_header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        batch_header.setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self.batches_table.setItemDelegateForColumn(
            3,
            BadgeDelegate(
                lambda text: (
                    "positive"
                    if text == "Posted"
                    else "muted"
                    if text == "Cancelled"
                    else "info"
                ),
                self.batches_table,
            ),
        )
        batches_layout.addWidget(self.batches_empty)
        batches_layout.addWidget(self.batches_table)
        layout.addWidget(batches_card)

        self.rows_card, rows_layout = create_card(
            "Review rows",
            subtitle="Select one or more rows to categorize, ignore, or restore",
        )
        self.batch_context = QLabel()
        self.batch_context.setProperty("role", "sectionSubtitle")
        self.batch_context.setWordWrap(True)
        rows_layout.addWidget(self.batch_context)

        self.rows_table = QTableWidget(0, 7)
        self.rows_table.setHorizontalHeaderLabels(
            ["Row", "Date", "Type", "Description", "Amount", "Category", "Status"]
        )
        style_table(self.rows_table)
        self.rows_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        row_header = self.rows_table.horizontalHeader()
        for column in (0, 1, 2, 4, 6):
            row_header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        row_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        row_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.rows_table.setItemDelegateForColumn(
            2, BadgeDelegate(badge_tone, self.rows_table)
        )
        self.rows_table.setItemDelegateForColumn(
            6,
            BadgeDelegate(
                lambda text: {
                    "Ready": "positive",
                    "Posted": "positive",
                    "Needs category": "info",
                    "Needs fixing": "negative",
                    "Ignored": "muted",
                    "Duplicate": "muted",
                }.get(text, "neutral"),
                self.rows_table,
            ),
        )
        self.rows_table.itemSelectionChanged.connect(self._update_actions)
        rows_layout.addWidget(self.rows_table)

        review_actions = QHBoxLayout()
        review_actions.setSpacing(8)
        self.category_combo = QComboBox()
        self.category_combo.setMinimumWidth(220)
        self.apply_category_button = secondary_button("Apply category")
        self.apply_category_button.clicked.connect(self._apply_category)
        self.ignore_button = secondary_button("Ignore selected")
        self.ignore_button.clicked.connect(self._ignore_selected)
        self.restore_button = secondary_button("Restore selected")
        self.restore_button.clicked.connect(self._restore_selected)
        review_actions.addWidget(self.category_combo)
        review_actions.addWidget(self.apply_category_button)
        review_actions.addWidget(self.ignore_button)
        review_actions.addWidget(self.restore_button)
        review_actions.addStretch()
        rows_layout.addLayout(review_actions)

        post_bar = QFrame()
        post_bar.setProperty("role", "honestNotice")
        post_layout = QHBoxLayout(post_bar)
        post_layout.setContentsMargins(18, 14, 18, 14)
        post_layout.setSpacing(10)
        post_copy = QVBoxLayout()
        post_copy.setSpacing(2)
        post_title = QLabel("Post to your ledger")
        post_title.setProperty("role", "sectionTitle")
        self.post_detail = QLabel(
            "A local recovery point is created before ready rows are posted."
        )
        self.post_detail.setProperty("role", "sectionSubtitle")
        self.post_detail.setWordWrap(True)
        self.allow_uncategorized = QCheckBox("Include uncategorized rows")
        self.allow_uncategorized.toggled.connect(self._update_actions)
        post_copy.addWidget(post_title)
        post_copy.addWidget(self.post_detail)
        post_copy.addWidget(self.allow_uncategorized)
        post_layout.addLayout(post_copy, 1)
        self.cancel_batch_button = danger_button("Cancel import")
        self.cancel_batch_button.clicked.connect(self._cancel_batch)
        self.post_button = primary_button("Post ready rows")
        self.post_button.clicked.connect(self._post_ready)
        post_layout.addWidget(self.cancel_batch_button)
        post_layout.addWidget(self.post_button)
        rows_layout.addWidget(post_bar)
        layout.addWidget(self.rows_card)
        layout.addStretch()
        self.rows_card.hide()
        self._populate_categories()

    def refresh(self) -> None:
        preferred = self._selected_batch_id
        self._populate_categories()
        self._batch_summaries = self.inbox.list_batches()
        summary = self.inbox.summary()
        for key, value in self.summary_values.items():
            value.setText(str(summary[key]))

        self.batches_table.blockSignals(True)
        self.batches_table.setRowCount(len(self._batch_summaries))
        selected_row = -1
        for row, item in enumerate(self._batch_summaries):
            batch = item.batch
            source = QTableWidgetItem(batch.source_name)
            source.setData(Qt.ItemDataRole.UserRole, batch.id)
            source.setToolTip(batch.source_name)
            self.batches_table.setItem(row, 0, source)
            if batch.period_start and batch.period_end:
                scope = f"{batch.period_start} to {batch.period_end}"
            elif batch.sheet_name:
                scope = batch.sheet_name
            else:
                scope = (
                    "Bank statement"
                    if batch.source_type == "bank_statement"
                    else "Money Manager CSV"
                )
            self.batches_table.setItem(row, 1, QTableWidgetItem(scope))
            review = (
                f"{item.resolved_count}/{item.total_count} resolved"
                if item.total_count
                else "No rows"
            )
            self.batches_table.setItem(row, 2, QTableWidgetItem(review))
            status = {
                "review": "In review",
                "posted": "Posted",
                "cancelled": "Cancelled",
            }[batch.status]
            self.batches_table.setItem(row, 3, QTableWidgetItem(status))
            created = batch.created_at[:16].replace("T", " ")
            self.batches_table.setItem(row, 4, QTableWidgetItem(created))
            if batch.id == preferred:
                selected_row = row
        self.batches_table.blockSignals(False)
        has_batches = bool(self._batch_summaries)
        self.batches_empty.setVisible(not has_batches)
        self.batches_table.setVisible(has_batches)
        if has_batches:
            fit_item_view_height(
                self.batches_table, len(self._batch_summaries), maximum_rows=5
            )
            self.batches_table.selectRow(
                selected_row if selected_row >= 0 else 0
            )
        else:
            self._selected_batch_id = None
            self.rows_card.hide()

    def select_entity(self, batch_id: str) -> None:
        self._selected_batch_id = batch_id
        self.refresh()

    def _import_statement(self) -> None:
        batch_id = self.on_import_statement()
        if batch_id:
            self.select_entity(batch_id)

    def _import_csv(self) -> None:
        batch_id = self.on_import_csv()
        if batch_id:
            self.select_entity(batch_id)

    def _batch_selection_changed(self) -> None:
        selected = self.batches_table.selectedItems()
        if not selected:
            return
        source = self.batches_table.item(selected[0].row(), 0)
        if not source:
            return
        self._selected_batch_id = source.data(Qt.ItemDataRole.UserRole)
        self._render_rows()

    def _render_rows(self) -> None:
        summary = self._current_summary()
        if not summary:
            self.rows_card.hide()
            return
        batch = summary.batch
        rows = self.inbox.list_rows(batch.id)
        categories = {
            category.id: category.name
            for category in self.categories.list(include_inactive=True)
        }
        context = [
            batch.source_name,
            (
                "Bank statement"
                if batch.source_type == "bank_statement"
                else "Money Manager CSV"
            ),
        ]
        if batch.sheet_name:
            context.append(f"sheet {batch.sheet_name}")
        if batch.period_start and batch.period_end:
            context.append(f"{batch.period_start} to {batch.period_end}")
        self.batch_context.setText("  ·  ".join(context))
        self.rows_table.setRowCount(len(rows))
        for table_row, inbox_row in enumerate(rows):
            number = QTableWidgetItem(str(inbox_row.source_row_number))
            number.setData(Qt.ItemDataRole.UserRole, inbox_row.id)
            self.rows_table.setItem(table_row, 0, number)
            self.rows_table.setItem(
                table_row, 1, QTableWidgetItem(inbox_row.date or "—")
            )
            self.rows_table.setItem(
                table_row,
                2,
                QTableWidgetItem(
                    (inbox_row.transaction_type or "Issue").title()
                ),
            )
            description = (
                inbox_row.description
                or inbox_row.issue_text
                or "Could not parse this row"
            )
            description_item = QTableWidgetItem(description)
            if inbox_row.issue_text:
                description_item.setToolTip(inbox_row.issue_text)
            self.rows_table.setItem(table_row, 3, description_item)
            if inbox_row.amount is None:
                amount = QTableWidgetItem("—")
                amount.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight
                    | Qt.AlignmentFlag.AlignVCenter
                )
            else:
                signed = (
                    -inbox_row.amount
                    if inbox_row.transaction_type == "expense"
                    else inbox_row.amount
                )
                amount = amount_item(
                    signed, neutral=inbox_row.transaction_type == "transfer"
                )
            self.rows_table.setItem(table_row, 4, amount)
            self.rows_table.setItem(
                table_row,
                5,
                QTableWidgetItem(
                    categories.get(inbox_row.category_id, "—")
                ),
            )
            self.rows_table.setItem(
                table_row,
                6,
                QTableWidgetItem(self.STATUS_LABELS[inbox_row.status]),
            )
        fit_item_view_height(self.rows_table, len(rows), maximum_rows=8)
        self.rows_card.show()
        open_batch = batch.status == "review"
        self.allow_uncategorized.setVisible(open_batch)
        self.cancel_batch_button.setVisible(open_batch)
        self.post_button.setVisible(open_batch)
        self.category_combo.setVisible(open_batch)
        self.apply_category_button.setVisible(open_batch)
        self.ignore_button.setVisible(open_batch)
        self.restore_button.setVisible(open_batch)
        self._update_actions()

    def _populate_categories(self) -> None:
        self.category_combo.clear()
        self.category_combo.addItem("Choose a category…", None)
        for category in self.categories.list():
            self.category_combo.addItem(
                f"{category.type.title()} · {category.name}",
                category.id,
            )

    def _selected_row_ids(self) -> list[str]:
        return [
            self.rows_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            for row in sorted(
                {index.row() for index in self.rows_table.selectedIndexes()}
            )
            if self.rows_table.item(row, 0)
        ]

    def _apply_category(self) -> None:
        category_id = self.category_combo.currentData()
        if not category_id:
            QMessageBox.information(
                self, "Choose a category", "Select a category to apply first."
            )
            return
        try:
            changed = self.inbox.set_category(
                self._selected_row_ids(), category_id
            )
        except (ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Category was not applied", str(exc))
            return
        self._after_review_change(f"{changed} row{'s' if changed != 1 else ''} updated")

    def _ignore_selected(self) -> None:
        try:
            changed = self.inbox.ignore_rows(self._selected_row_ids())
        except (ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Rows were not ignored", str(exc))
            return
        self._after_review_change(f"{changed} row{'s' if changed != 1 else ''} ignored")

    def _restore_selected(self) -> None:
        try:
            changed = self.inbox.restore_rows(self._selected_row_ids())
        except (ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Rows were not restored", str(exc))
            return
        self._after_review_change(f"{changed} row{'s' if changed != 1 else ''} restored")

    def _post_ready(self) -> None:
        summary = self._current_summary()
        if not summary:
            return
        count = summary.ready_count
        if self.allow_uncategorized.isChecked():
            count += summary.needs_category_count
        if count == 0:
            QMessageBox.information(
                self,
                "Nothing is ready",
                "Categorize a row, allow uncategorized rows, or resolve an issue first.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Post ready rows?",
            f"Post {count} row{'s' if count != 1 else ''} to your ledger?\n\n"
            "A local recovery point will be created first.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if not self.on_before_post():
            return
        try:
            posted = self.inbox.post_ready(
                summary.batch.id,
                include_uncategorized=self.allow_uncategorized.isChecked(),
            )
        except (ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(
                self,
                "Rows were not posted",
                f"No partial import was kept.\n\n{exc}",
            )
            return
        self.allow_uncategorized.setChecked(False)
        self.on_changed({"imports", "transactions"})
        self.notify(
            f"{posted} imported transaction{'s' if posted != 1 else ''} posted"
        )
        self.refresh()

    def _cancel_batch(self) -> None:
        summary = self._current_summary()
        if not summary:
            return
        answer = QMessageBox.question(
            self,
            "Cancel this import?",
            "Unposted rows will be marked ignored. Transactions already posted "
            "from this batch will stay in your ledger.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.inbox.cancel_batch(summary.batch.id)
        except (ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Import was not cancelled", str(exc))
            return
        self.on_changed({"imports"})
        self.notify("Import cancelled")
        self.refresh()

    def _after_review_change(self, message: str) -> None:
        self.on_changed({"imports"})
        self.notify(message)
        self.refresh()

    def _current_summary(self):
        return next(
            (
                item
                for item in self._batch_summaries
                if item.batch.id == self._selected_batch_id
            ),
            None,
        )

    def _update_actions(self) -> None:
        summary = self._current_summary()
        selected = bool(self._selected_row_ids())
        open_batch = bool(summary and summary.batch.status == "review")
        self.apply_category_button.setEnabled(open_batch and selected)
        self.ignore_button.setEnabled(open_batch and selected)
        self.restore_button.setEnabled(open_batch and selected)
        ready = bool(
            summary
            and (
                summary.ready_count
                or (
                    self.allow_uncategorized.isChecked()
                    and summary.needs_category_count
                )
            )
        )
        self.post_button.setEnabled(open_batch and ready)
        if summary:
            postable = summary.ready_count + (
                summary.needs_category_count
                if self.allow_uncategorized.isChecked()
                else 0
            )
            self.post_button.setText(
                f"Post {postable} ready row"
                f"{'s' if postable != 1 else ''}"
            )


class ReconciliationPage(QWidget):
    def __init__(
        self,
        db: sqlite3.Connection,
        *,
        on_import_statement=None,
    ):
        super().__init__()
        self.inbox = ImportInboxService(db)
        self.on_import_statement = on_import_statement or (lambda: None)
        import_button = primary_button("Import a statement", "download")
        import_button.clicked.connect(self._import_statement)
        layout = page_layout(
            self,
            "Reconciliation",
            "Confirm that every row in a card statement has a clear outcome",
            import_button,
        )
        empty_import_button = primary_button("Import a statement", "download")
        empty_import_button.clicked.connect(self._import_statement)
        self.empty = empty_state(
            "No statements to reconcile",
            "Imported statement coverage will appear here.",
            empty_import_button,
        )
        self.empty.setProperty("role", "reconciliationEmpty")
        layout.addWidget(self.empty)

        self.table_card, table_layout = create_card(
            "Statement coverage",
            subtitle="Every source row is tracked as posted, duplicate, ignored, or unresolved",
        )
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Statement", "Period", "Outcome", "Status"]
        )
        style_table(self.table)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setItemDelegateForColumn(
            3,
            BadgeDelegate(
                lambda text: (
                    "positive"
                    if text == "Reconciled"
                    else "negative"
                    if text == "Needs review"
                    else "muted"
                ),
                self.table,
            ),
        )
        table_layout.addWidget(self.table)
        layout.addWidget(self.table_card)
        layout.addStretch()
        self.table_card.hide()

    def refresh(self) -> None:
        summaries = [
            item
            for item in self.inbox.list_batches()
            if item.batch.source_type == "bank_statement"
        ]
        self.empty.setVisible(not summaries)
        self.table_card.setVisible(bool(summaries))
        self.table.setRowCount(len(summaries))
        for row, item in enumerate(summaries):
            batch = item.batch
            self.table.setItem(row, 0, QTableWidgetItem(batch.source_name))
            period = (
                f"{batch.period_start} to {batch.period_end}"
                if batch.period_start and batch.period_end
                else "Not specified"
            )
            self.table.setItem(row, 1, QTableWidgetItem(period))
            outcome = (
                f"{item.posted_count} posted · {item.duplicate_count} duplicate · "
                f"{item.ignored_count} ignored"
            )
            self.table.setItem(row, 2, QTableWidgetItem(outcome))
            unresolved = (
                item.ready_count
                + item.needs_category_count
                + item.error_count
            )
            status = (
                "Reconciled"
                if not unresolved and batch.status == "posted"
                else "Cancelled"
                if batch.status == "cancelled"
                else "Needs review"
            )
            self.table.setItem(row, 3, QTableWidgetItem(status))
        if summaries:
            fit_item_view_height(self.table, len(summaries), maximum_rows=8)

    def _import_statement(self) -> None:
        self.on_import_statement()
        self.refresh()
