from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
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
from app.ui.charts import PerformanceChart
from app.ui.components import (
    amount_item,
    badge,
    chip_button,
    clear_layout,
    compact_money,
    create_card,
    danger_button,
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
    EditInvestmentValueDialog,
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
            ("updates", "Every log"),
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

        self.updates_selector = QComboBox()
        self.updates_selector.setMinimumWidth(150)
        self.updates_selector.setMaximumWidth(170)
        self.updates_selector.currentIndexChanged.connect(self._refresh_value_updates)
        updates_card, updates_layout = create_card(
            "Logs",
            subtitle="Saved market values, newest first",
            action=self.updates_selector,
        )
        self.updates_card = updates_card
        self.updates_caption = QLabel("Choose a portfolio or investment")
        self.updates_caption.setProperty("role", "helper")
        self.edit_update_button = ghost_button("Edit", "edit")
        self.delete_update_button = danger_button("Delete", "delete")
        self.clear_logs_button = ghost_button("Clear logs", "delete")
        self.edit_update_button.setEnabled(False)
        self.delete_update_button.setEnabled(False)
        self.clear_logs_button.setEnabled(False)
        self.edit_update_button.clicked.connect(self.edit_value_update)
        self.delete_update_button.clicked.connect(self.delete_value_update)
        self.clear_logs_button.clicked.connect(self.clear_value_logs)
        update_controls = QHBoxLayout()
        update_controls.setContentsMargins(0, 0, 0, 0)
        update_controls.setSpacing(6)
        update_controls.addStretch()
        update_controls.addWidget(self.edit_update_button)
        update_controls.addWidget(self.delete_update_button)
        update_controls.addWidget(self.clear_logs_button)
        self.updates_table = QTableWidget(0, 3)
        self.updates_table.setHorizontalHeaderLabels(["Date", "Value", "Change"])
        style_table(self.updates_table)
        self.updates_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.updates_table.itemSelectionChanged.connect(self._sync_update_actions)
        self.updates_table.itemDoubleClicked.connect(
            lambda _item: self.edit_value_update()
        )
        updates_header = self.updates_table.horizontalHeader()
        updates_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        updates_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        updates_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.updates_table.setMinimumHeight(250)
        updates_layout.addWidget(self.updates_caption)
        updates_layout.addLayout(update_controls)
        updates_layout.addWidget(self.updates_table)

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
        self.delete_button = danger_button("Delete", "delete")
        self.delete_button.setToolTip(
            "Delete portfolio and return its current value to its funding accounts"
        )
        self.edit_button.clicked.connect(self.edit_investment)
        self.add_funds_button.clicked.connect(self.add_funds)
        self.update_value_button.clicked.connect(self.update_value)
        self.delete_button.clicked.connect(self.delete_investment)
        for button in (
            self.edit_button,
            self.add_funds_button,
            self.update_value_button,
            self.delete_button,
        ):
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
        controls_layout.addWidget(self.delete_button)

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
            self.updates_card.setMaximumWidth(360)
            self.chart_grid.addWidget(self.history_card, 0, 0)
            self.chart_grid.addWidget(self.updates_card, 0, 1)
            self.chart_grid.setColumnStretch(0, 2)
            self.chart_grid.setColumnStretch(1, 1)
        else:
            self.updates_card.setMaximumWidth(16777215)
            self.chart_grid.addWidget(self.history_card, 0, 0)
            self.chart_grid.addWidget(self.updates_card, 1, 0)
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
        selected_updates = self.updates_selector.currentData()
        selected_portfolio_id = None
        selected_row = self.table.currentRow()
        if selected_row >= 0:
            selected_item = self.table.item(selected_row, 0)
            if selected_item:
                selected_portfolio_id = selected_item.data(Qt.ItemDataRole.UserRole)
        self.history_selector.blockSignals(True)
        self.updates_selector.blockSignals(True)
        self.history_selector.clear()
        self.updates_selector.clear()
        self.history_selector.addItem("Portfolio total", "portfolio")
        for snapshot in snapshots:
            investment = snapshot.investment
            label = f"{investment.symbol} · {investment.name}" if investment.symbol else investment.name
            self.history_selector.addItem(label, investment.id)
            self.updates_selector.addItem(label, investment.id)
        selected_index = self.history_selector.findData(selected_history)
        self.history_selector.setCurrentIndex(max(0, selected_index))
        if snapshots:
            updates_index = self.updates_selector.findData(selected_updates)
            self.updates_selector.setCurrentIndex(max(0, updates_index))
            self.updates_selector.setEnabled(True)
        else:
            self.updates_selector.addItem("No portfolios", None)
            self.updates_selector.setEnabled(False)
        self.history_selector.blockSignals(False)
        self.updates_selector.blockSignals(False)
        self._refresh_history_chart()
        self._refresh_value_updates()
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

        if snapshots:
            target_row = 0
            if selected_portfolio_id:
                for row in range(self.table.rowCount()):
                    item = self.table.item(row, 0)
                    if item and item.data(Qt.ItemDataRole.UserRole) == selected_portfolio_id:
                        target_row = row
                        break
            self.table.selectRow(target_row)

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
                self._changed("Value log added")
            except ValueError as exc:
                QMessageBox.warning(self, "Could not update value", str(exc))

    def delete_investment(self) -> None:
        snapshot = self._selected_snapshot()
        if not snapshot:
            return
        try:
            shares = self.service.liquidation_plan(snapshot.investment.id)
        except ValueError as exc:
            QMessageBox.warning(self, "Could not delete portfolio", str(exc))
            return

        destinations = "\n".join(
            f"- {share.account_name}: {format_money(share.proceeds)}"
            for share in shares
            if share.proceeds
        )
        if not destinations:
            destinations = "- No funds to return"
        confirm = QMessageBox.question(
            self,
            "Delete portfolio",
            f"Delete {snapshot.investment.name} and liquidate its current value "
            f"of {format_money(snapshot.current_value)}?\n\n"
            f"Funds will be returned to:\n{destinations}\n\n"
            "The investment will be removed from active views, while its financial "
            "history remains in the local database.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_investment(
                snapshot.investment.id,
                date.today().isoformat(),
            )
            self._changed("Portfolio deleted and funds returned")
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Could not delete portfolio", str(exc))

    def edit_value_update(self) -> None:
        selected = self._selected_value_update()
        if not selected:
            return
        investment_id, point = selected
        dialog = EditInvestmentValueDialog(
            self.updates_selector.currentText(),
            point,
        )
        if dialog.exec():
            try:
                self.service.edit_value_update(
                    investment_id,
                    point.id,
                    dialog.value(),
                )
                self._changed("Value log corrected")
            except ValueError as exc:
                QMessageBox.warning(self, "Could not edit value log", str(exc))

    def delete_value_update(self) -> None:
        selected = self._selected_value_update()
        if not selected:
            return
        investment_id, point = selected
        confirm = QMessageBox.question(
            self,
            "Delete value log",
            f"Delete the {format_display_date(point.date)} value log of "
            f"{format_money(point.value)}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_value_update(investment_id, point.id)
            self._changed("Value log deleted")
        except ValueError as exc:
            QMessageBox.warning(self, "Could not delete value log", str(exc))

    def clear_value_logs(self) -> None:
        investment_id = self.updates_selector.currentData()
        if not investment_id or investment_id == "portfolio":
            return
        points = self.service.value_history(str(investment_id))
        if not points:
            return
        investment_name = self.updates_selector.currentText()
        confirm = QMessageBox.question(
            self,
            "Clear portfolio logs",
            f"Delete all {len(points)} saved logs for {investment_name}?\n\n"
            "This clears the graph history only. The current portfolio value, "
            "contributions, and transactions will not change.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = self.service.clear_value_logs(str(investment_id))
            self._changed(
                f"{deleted} portfolio log{'s' if deleted != 1 else ''} cleared"
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Could not clear portfolio logs", str(exc))

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

    def _selected_value_update(self):
        investment_id = self.updates_selector.currentData()
        if not investment_id or investment_id == "portfolio":
            return None
        row = self.updates_table.currentRow()
        item = self.updates_table.item(row, 0) if row >= 0 else None
        point_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        point = self._update_points_by_id.get(str(point_id)) if point_id else None
        return (str(investment_id), point) if point else None

    def _sync_actions(self) -> None:
        snapshot = self._selected_snapshot()
        selected = snapshot is not None
        self.edit_button.setEnabled(selected)
        self.add_funds_button.setEnabled(selected)
        self.update_value_button.setEnabled(selected)
        self.delete_button.setEnabled(selected)
        if snapshot and self.history_selector.currentData() != snapshot.investment.id:
            index = self.history_selector.findData(snapshot.investment.id)
            if index >= 0:
                self.history_selector.setCurrentIndex(index)
        if snapshot and self.updates_selector.currentData() != snapshot.investment.id:
            index = self.updates_selector.findData(snapshot.investment.id)
            if index >= 0:
                self.updates_selector.setCurrentIndex(index)

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
        elif self.history_interval == "updates":
            update_word = "log" if len(points) == 1 else "logs"
            self.history_caption.setText(
                f"{len(points)} saved {update_word} · "
                f"{format_display_date(points[0].date)} to "
                f"{format_display_date(points[-1].date)}"
            )
        else:
            interval_name = self.history_interval.title()
            period_word = "period" if len(points) == 1 else "periods"
            update_word = "log" if len(raw_points) == 1 else "logs"
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
        return point_date.strftime("%d %b")

    def _refresh_value_updates(self, _index: int | None = None) -> None:
        if not hasattr(self, "updates_table"):
            return
        investment_id = self.updates_selector.currentData()
        if not investment_id:
            points = []
            subject = "portfolio"
        elif investment_id == "portfolio":
            points = self.service.portfolio_history()
            subject = "portfolio"
        else:
            points = self.service.value_history(str(investment_id))
            subject = self.updates_selector.currentText()
        self._update_points_by_id = {point.id: point for point in points}
        self.updates_caption.setText(
            f"{len(points)} saved log{'s' if len(points) != 1 else ''} for {subject}"
        )
        changes = []
        previous_value = None
        date_totals: dict[str, int] = {}
        for point in points:
            date_totals[point.date] = date_totals.get(point.date, 0) + 1
            change = None if previous_value is None else point.value - previous_value
            changes.append((point, change))
            previous_value = point.value

        date_occurrences: dict[str, int] = {}
        labels: dict[str, str] = {}
        for point in points:
            date_occurrences[point.date] = date_occurrences.get(point.date, 0) + 1
            label = format_display_date(point.date)
            if date_totals[point.date] > 1:
                label += f" · {date_occurrences[point.date]}/{date_totals[point.date]}"
            labels[point.id] = label

        self.updates_table.setRowCount(len(changes))
        for row, (point, change) in enumerate(reversed(changes)):
            date_item = QTableWidgetItem(labels[point.id])
            date_item.setData(Qt.ItemDataRole.UserRole, point.id)
            if date.fromisoformat(point.date) > date.today():
                date_item.setForeground(QColor(Colors.NEGATIVE))
                date_item.setToolTip(
                    "Future-dated log. Delete it or clear the logs to unlock "
                    "current portfolio actions."
                )
            value_item = amount_item(point.value, neutral=True)
            value_item.setToolTip(
                f"Invested at this point: {format_money(point.contributed)}"
            )
            if change is None:
                change_item = QTableWidgetItem("Initial")
                change_item.setForeground(QColor(Colors.TEXT_MUTED))
                change_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            else:
                change_item = amount_item(change)
                if change > 0:
                    change_item.setText(f"+{format_money(change)}")
            self.updates_table.setItem(row, 0, date_item)
            self.updates_table.setItem(row, 1, value_item)
            self.updates_table.setItem(row, 2, change_item)
        self.updates_table.setVisible(bool(points))
        self._sync_update_actions()

    def _sync_update_actions(self) -> None:
        selected = self._selected_value_update()
        self.edit_update_button.setEnabled(selected is not None)
        self.delete_update_button.setEnabled(selected is not None)
        individual_portfolio = self.updates_selector.currentData() not in (None, "portfolio")
        self.clear_logs_button.setEnabled(
            individual_portfolio and bool(self._update_points_by_id)
        )
        if not individual_portfolio:
            tip = "Choose an individual investment to change its logs"
        else:
            tip = ""
        self.delete_update_button.setToolTip(tip)
        self.clear_logs_button.setToolTip(tip)

    def _changed(self, message: str) -> None:
        self.notify(message)
        self.on_changed({"investments", "accounts", "transactions", "dashboard"})

    @staticmethod
    def _set_performance_tone(label: QLabel, value) -> None:
        tone = "positive" if value > 0 else "negative" if value < 0 else "neutral"
        label.setProperty("tone", tone)
        label.style().unpolish(label)
        label.style().polish(label)
