from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.investment import InvestmentSnapshot
from app.repositories.account_repository import AccountRepository
from app.services.investment_service import InvestmentService
from app.ui.charts import AllocationChart, PerformanceChart
from app.ui.components import (
    amount_item,
    badge,
    chip_button,
    clear_layout,
    compact_money,
    create_card,
    empty_state,
    fit_item_view_height,
    ghost_button,
    metric_card,
    page_layout,
    pretty_type,
    primary_button,
    soft_button,
    style_table,
)
from app.ui.investment_form import (
    AddInvestmentFundsDialog,
    InvestmentForm,
    UpdateInvestmentValueDialog,
)
from app.ui.theme import Colors
from app.utils.dates import format_display_date
from app.utils.money import format_money


class InvestmentsPage(QWidget):
    def __init__(self, db: sqlite3.Connection, on_changed, notify=None):
        super().__init__()
        self.service = InvestmentService(db)
        self.accounts = AccountRepository(db)
        self.on_changed = on_changed
        self.notify = notify or (lambda _message: None)
        self.history_interval = "monthly"
        self.interval_buttons = {}

        add_button = primary_button("Add investment", "plus")
        add_button.clicked.connect(self.add_investment)
        layout = page_layout(
            self,
            "Investments",
            "Track contributions, current values, and portfolio performance",
            add_button,
        )
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.metric_grid = QGridLayout()
        self.metric_grid.setContentsMargins(0, 0, 0, 0)
        self.metric_grid.setSpacing(16)
        self.metric_widgets: list[QWidget] = []
        self.metric_values: dict[str, QLabel] = {}
        for key, label, helper, tone in (
            ("current_value", "Portfolio value", "Latest recorded values", None),
            ("contributed", "Total contributed", "Money moved into investments", None),
            ("gain_loss", "Gain / loss", "Value minus contributions", None),
            ("return_percent", "Overall return", "Gain or loss on contributions", None),
        ):
            card, value = metric_card(label, "€0.00", helper, tone)
            self.metric_widgets.append(card)
            self.metric_values[key] = value
        layout.addLayout(self.metric_grid)

        self.history_selector = QComboBox()
        self.history_selector.setMinimumWidth(180)
        self.history_selector.setMaximumWidth(280)
        self.history_selector.currentIndexChanged.connect(self._refresh_history_chart)
        history_card, history_layout = create_card(
            "Value history",
            subtitle="Recorded market values over time",
            action=self.history_selector,
        )
        self.history_card = history_card
        self.history_caption = QLabel("Choose a portfolio or investment")
        self.history_caption.setProperty("role", "helper")
        interval_row = QHBoxLayout()
        interval_row.setSpacing(5)
        interval_label = QLabel("Period")
        interval_label.setProperty("role", "metricLabel")
        interval_row.addWidget(interval_label)
        for key, label in (
            ("monthly", "Monthly"),
            ("biweekly", "Biweekly"),
            ("weekly", "Weekly"),
            ("daily", "Daily"),
        ):
            button = chip_button(label)
            button.clicked.connect(
                lambda _checked=False, value=key: self._set_history_interval(value)
            )
            self.interval_buttons[key] = button
            interval_row.addWidget(button)
        interval_row.addStretch()
        self.history_chart = PerformanceChart()
        history_layout.addWidget(self.history_caption)
        history_layout.addLayout(interval_row)
        history_layout.addWidget(self.history_chart)

        allocation_card, allocation_layout = create_card(
            "Current allocation",
            subtitle="How today’s portfolio value is distributed",
        )
        self.allocation_card = allocation_card
        self.allocation_chart = AllocationChart()
        allocation_layout.addWidget(self.allocation_chart)

        self.chart_grid = QGridLayout()
        self.chart_grid.setContentsMargins(0, 0, 0, 0)
        self.chart_grid.setSpacing(16)
        layout.addLayout(self.chart_grid)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Investment", "Type", "Contributed", "Current value", "Gain / loss", "Return"]
        )
        style_table(self.table)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._sync_actions)
        self.table.itemDoubleClicked.connect(lambda _item: self.update_value())

        self.result_label = QLabel("")
        self.result_label.setProperty("role", "count")
        self.edit_button = ghost_button("Edit", "edit")
        self.add_funds_button = soft_button("Add funds", "plus")
        self.update_value_button = soft_button("Update value", "investments")
        self.edit_button.clicked.connect(self.edit_investment)
        self.add_funds_button.clicked.connect(self.add_funds)
        self.update_value_button.clicked.connect(self.update_value)
        for button in (self.edit_button, self.add_funds_button, self.update_value_button):
            button.setEnabled(False)

        controls = QFrame()
        controls.setProperty("role", "toolbar")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(8, 7, 8, 7)
        controls_layout.setSpacing(7)
        controls_layout.addWidget(self.result_label)
        controls_layout.addStretch()
        controls_layout.addWidget(self.edit_button)
        controls_layout.addWidget(self.add_funds_button)
        controls_layout.addWidget(self.update_value_button)

        card, card_layout = create_card(
            "Portfolio",
            subtitle="Contributions and manually recorded market values",
        )
        self.portfolio_card = card
        card_layout.addWidget(controls)
        empty_action = primary_button("Add investment", "plus")
        empty_action.clicked.connect(self.add_investment)
        self.empty = empty_state(
            "No investments yet",
            "Add an investment funded from one of your accounts.",
            empty_action,
        )
        card_layout.addWidget(self.empty)
        card_layout.addWidget(self.table, 1)
        layout.addWidget(card, 1)
        self._layout_metrics()
        self._layout_charts()
        self._set_history_interval("monthly", refresh=False)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_metrics()
        self._layout_charts()
        if hasattr(self, "table"):
            self.table.setColumnHidden(1, self.width() < 980)
            self.table.setColumnHidden(2, self.width() < 860)

    def _layout_metrics(self) -> None:
        if not hasattr(self, "metric_grid"):
            return
        columns = 4 if self.width() >= 900 else 2
        if getattr(self, "_metric_columns", None) == columns:
            return
        self._metric_columns = columns
        clear_layout(self.metric_grid)
        for column in range(4):
            self.metric_grid.setColumnStretch(column, 1 if column < columns else 0)
        for index, card in enumerate(self.metric_widgets):
            self.metric_grid.addWidget(card, index // columns, index % columns)

    def _layout_charts(self) -> None:
        if not hasattr(self, "chart_grid"):
            return
        wide = self.width() >= 1100
        if getattr(self, "_charts_wide", None) == wide:
            return
        self._charts_wide = wide
        clear_layout(self.chart_grid)
        if wide:
            self.chart_grid.addWidget(self.history_card, 0, 0)
            self.chart_grid.addWidget(self.allocation_card, 0, 1)
            self.chart_grid.setColumnStretch(0, 2)
            self.chart_grid.setColumnStretch(1, 1)
        else:
            self.chart_grid.addWidget(self.history_card, 0, 0)
            self.chart_grid.addWidget(self.allocation_card, 1, 0)
            self.chart_grid.setColumnStretch(0, 1)
            self.chart_grid.setColumnStretch(1, 0)

    def refresh(self) -> None:
        summary = self.service.summary()
        for key in ("current_value", "contributed", "gain_loss"):
            label = self.metric_values[key]
            label.setText(compact_money(summary[key]))
            label.setToolTip(format_money(summary[key]))
        return_value = summary["return_percent"]
        self.metric_values["return_percent"].setText(f"{return_value:+.2f}%")
        self._set_performance_tone(self.metric_values["gain_loss"], summary["gain_loss"])
        self._set_performance_tone(self.metric_values["return_percent"], return_value)

        snapshots = self.service.list_snapshots()
        selected_history = self.history_selector.currentData() or "portfolio"
        self.history_selector.blockSignals(True)
        self.history_selector.clear()
        self.history_selector.addItem("Portfolio total", "portfolio")
        for snapshot in snapshots:
            investment = snapshot.investment
            label = f"{investment.symbol} · {investment.name}" if investment.symbol else investment.name
            self.history_selector.addItem(label, investment.id)
        selected_index = self.history_selector.findData(selected_history)
        self.history_selector.setCurrentIndex(max(0, selected_index))
        self.history_selector.blockSignals(False)
        self.allocation_chart.set_data(
            [
                (
                    snapshot.investment.symbol or snapshot.investment.name,
                    snapshot.current_value,
                )
                for snapshot in snapshots
            ]
        )
        self._refresh_history_chart()
        self.table.setRowCount(len(snapshots))
        for row, snapshot in enumerate(snapshots):
            investment = snapshot.investment
            name = investment.name
            if investment.symbol:
                name = f"{investment.symbol}  ·  {name}"
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, investment.id)
            self.table.setItem(row, 0, name_item)
            self.table.setCellWidget(row, 1, badge(pretty_type(investment.kind), "neutral"))
            self.table.setItem(row, 2, amount_item(snapshot.contributed, neutral=True))
            self.table.setItem(row, 3, amount_item(snapshot.current_value, neutral=True))
            self.table.setItem(row, 4, amount_item(snapshot.gain_loss))
            return_item = QTableWidgetItem(f"{snapshot.return_percent:+.2f}%")
            return_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            if snapshot.return_percent > 0:
                return_item.setForeground(QColor(Colors.POSITIVE))
            elif snapshot.return_percent < 0:
                return_item.setForeground(QColor(Colors.NEGATIVE))
            self.table.setItem(row, 5, return_item)

        has_investments = bool(snapshots)
        self.result_label.setText(
            f"{len(snapshots)} investment{'s' if len(snapshots) != 1 else ''}"
        )
        self.empty.setVisible(not has_investments)
        self.table.setVisible(has_investments)
        controls = self.edit_button.parentWidget()
        if controls:
            controls.setVisible(has_investments)
        if has_investments and len(snapshots) <= 8:
            fit_item_view_height(self.table, len(snapshots), maximum_rows=8)
            self.portfolio_card.setMaximumHeight(175 + self.table.maximumHeight())
        elif has_investments:
            self.table.setMaximumHeight(16777215)
            self.table.setMinimumHeight(320)
            self.portfolio_card.setMaximumHeight(16777215)
        else:
            self.portfolio_card.setMaximumHeight(300)
        self._sync_actions()

    def add_investment(self) -> None:
        accounts = self._funding_accounts()
        if not accounts:
            QMessageBox.information(
                self,
                "No funding account",
                "Create a bank, current, savings, cash, or wallet account first.",
            )
            return
        form = InvestmentForm(accounts)
        if form.exec():
            try:
                self.service.create_investment(**form.create_values())
                self._changed("Investment added")
            except ValueError as exc:
                QMessageBox.warning(self, "Could not add investment", str(exc))

    def edit_investment(self) -> None:
        snapshot = self._selected_snapshot()
        if not snapshot:
            return
        form = InvestmentForm([], snapshot.investment)
        if form.exec():
            try:
                self.service.update_investment(
                    snapshot.investment.id,
                    **form.edit_values(),
                )
                self._changed("Investment updated")
            except ValueError as exc:
                QMessageBox.warning(self, "Could not update investment", str(exc))

    def add_funds(self) -> None:
        snapshot = self._selected_snapshot()
        if not snapshot:
            return
        accounts = self._funding_accounts()
        if not accounts:
            QMessageBox.information(self, "No funding account", "No active funding account is available.")
            return
        dialog = AddInvestmentFundsDialog(snapshot, accounts)
        if dialog.exec():
            try:
                self.service.add_funds(snapshot.investment.id, **dialog.values())
                self._changed("Investment funds added")
            except ValueError as exc:
                QMessageBox.warning(self, "Could not add funds", str(exc))

    def update_value(self) -> None:
        snapshot = self._selected_snapshot()
        if not snapshot:
            return
        dialog = UpdateInvestmentValueDialog(snapshot)
        if dialog.exec():
            try:
                self.service.update_value(snapshot.investment.id, **dialog.values())
                self._changed("Investment value updated")
            except ValueError as exc:
                QMessageBox.warning(self, "Could not update value", str(exc))

    def _funding_accounts(self):
        return [
            account
            for account in self.accounts.list(include_inactive=False)
            if account.type in self.service.FUNDING_ACCOUNT_TYPES
        ]

    def _selected_snapshot(self) -> InvestmentSnapshot | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        investment_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        return self.service.get_snapshot(str(investment_id)) if investment_id else None

    def _sync_actions(self) -> None:
        snapshot = self._selected_snapshot()
        selected = snapshot is not None
        self.edit_button.setEnabled(selected)
        self.add_funds_button.setEnabled(selected)
        self.update_value_button.setEnabled(selected)
        if snapshot and self.history_selector.currentData() != snapshot.investment.id:
            index = self.history_selector.findData(snapshot.investment.id)
            if index >= 0:
                self.history_selector.setCurrentIndex(index)

    def _refresh_history_chart(self, _index: int | None = None) -> None:
        if not hasattr(self, "history_chart"):
            return
        investment_id = self.history_selector.currentData()
        if not investment_id or investment_id == "portfolio":
            raw_points = self.service.portfolio_history()
            points = self.service.performance_history(
                interval=self.history_interval,
            )
            subject = "portfolio"
        else:
            raw_points = self.service.value_history(str(investment_id))
            points = self.service.performance_history(
                str(investment_id),
                self.history_interval,
            )
            subject = self.history_selector.currentText()
        self.history_chart.set_data(
            [
                (
                    self._period_label(point.date),
                    point.contributed,
                    point.current_value,
                )
                for point in points
            ]
        )
        if not points:
            self.history_caption.setText(f"No recorded values for {subject}")
        else:
            interval_name = self.history_interval.title()
            period_word = "period" if len(points) == 1 else "periods"
            update_word = "update" if len(raw_points) == 1 else "updates"
            self.history_caption.setText(
                f"{len(raw_points)} saved {update_word} · "
                f"{len(points)} {interval_name.lower()} {period_word} · "
                f"{format_display_date(points[0].date)} to "
                f"{format_display_date(points[-1].date)}"
            )

    def _set_history_interval(self, value: str, refresh: bool = True) -> None:
        self.history_interval = value
        for key, button in self.interval_buttons.items():
            selected = key == value
            button.setChecked(selected)
            button.setProperty("selected", "true" if selected else "false")
            button.style().unpolish(button)
            button.style().polish(button)
        if refresh:
            self._refresh_history_chart()

    def _period_label(self, value: str) -> str:
        point_date = date.fromisoformat(value)
        if self.history_interval == "monthly":
            return point_date.strftime("%b %Y")
        if self.history_interval == "weekly":
            return point_date.strftime("Week %d %b")
        if self.history_interval == "biweekly":
            return point_date.strftime("2w %d %b")
        return point_date.strftime("%d %b")

    def _changed(self, message: str) -> None:
        self.notify(message)
        self.on_changed({"investments", "accounts", "transactions", "dashboard"})

    @staticmethod
    def _set_performance_tone(label: QLabel, value) -> None:
        tone = "positive" if value > 0 else "negative" if value < 0 else "neutral"
        label.setProperty("tone", tone)
        label.style().unpolish(label)
        label.style().polish(label)
