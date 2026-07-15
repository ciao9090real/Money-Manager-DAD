from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
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
from app.ui.components import (
    amount_item,
    badge,
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
from app.utils.money import format_money


class InvestmentsPage(QWidget):
    def __init__(self, db: sqlite3.Connection, on_changed, notify=None):
        super().__init__()
        self.service = InvestmentService(db)
        self.accounts = AccountRepository(db)
        self.on_changed = on_changed
        self.notify = notify or (lambda _message: None)

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

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_metrics()
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
        selected = self._selected_snapshot() is not None
        self.edit_button.setEnabled(selected)
        self.add_funds_button.setEnabled(selected)
        self.update_value_button.setEnabled(selected)

    def _changed(self, message: str) -> None:
        self.notify(message)
        self.on_changed({"investments", "accounts", "transactions", "dashboard"})

    @staticmethod
    def _set_performance_tone(label: QLabel, value) -> None:
        tone = "positive" if value > 0 else "negative" if value < 0 else "neutral"
        label.setProperty("tone", tone)
        label.style().unpolish(label)
        label.style().polish(label)
