from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.repositories.account_repository import AccountRepository
from app.services.category_service import CategoryService
from app.services.payment_method_service import PaymentMethodService
from app.services.recurring_service import RecurringService
from app.ui.components import (
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
from app.ui.icons import icon
from app.ui.recurring_form import RecordRecurringDialog, RecurringRuleForm
from app.ui.theme import Colors
from app.utils.dates import format_display_date
from app.utils.money import format_money


class UpcomingPage(QWidget):
    def __init__(self, db: sqlite3.Connection, on_changed, notify=None):
        super().__init__()
        self.service = RecurringService(db)
        self.accounts = AccountRepository(db)
        self.categories = CategoryService(db)
        self.payment_methods = PaymentMethodService(db)
        self.on_changed = on_changed
        self.notify = notify or (lambda _message: None)
        self.current_filter = "all"
        self.filter_buttons = {}

        add_button = primary_button("Add recurring", "plus")
        add_button.clicked.connect(self.add_rule)
        layout = page_layout(
            self,
            "Upcoming",
            "Wages, subscriptions, bills, and repeating money movements",
            add_button,
        )
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.metric_grid = QGridLayout()
        self.metric_grid.setContentsMargins(0, 0, 0, 0)
        self.metric_grid.setSpacing(16)
        self.metric_widgets: list[QWidget] = []
        self.metric_values: dict[str, QLabel] = {}
        for key, label, helper, tone in (
            ("due_soon_count", "Due in 30 days", "Income and payments", None),
            ("overdue_count", "Overdue", "Past their expected date", "negative"),
            ("expected_income_30_days", "Scheduled income", "Known income in 30 days", "positive"),
            ("expected_outgoings_30_days", "Scheduled out", "Known payments in 30 days", "negative"),
        ):
            card, value = metric_card(label, "0", helper, tone)
            self.metric_widgets.append(card)
            self.metric_values[key] = value
        layout.addLayout(self.metric_grid)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Due", "Payment", "Type", "Frequency", "Account", "Amount", "Status"]
        )
        style_table(self.table)
        header = self.table.horizontalHeader()
        for column in (0, 2, 3, 5, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 118)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._sync_actions)
        self.table.itemDoubleClicked.connect(lambda _item: self.edit_rule())

        self.edit_button = ghost_button("Edit", "edit")
        self.record_button = soft_button("Record", "play")
        self.skip_button = ghost_button("Skip", "skip")
        self.pause_button = soft_button("Pause", "pause")
        self.remove_button = danger_button("Remove", "delete")
        self.edit_button.clicked.connect(self.edit_rule)
        self.record_button.clicked.connect(self.record_payment)
        self.skip_button.clicked.connect(self.skip_occurrence)
        self.pause_button.clicked.connect(self.toggle_paused)
        self.remove_button.clicked.connect(self.remove_rule)
        for button in (
            self.edit_button,
            self.record_button,
            self.skip_button,
            self.pause_button,
            self.remove_button,
        ):
            button.setEnabled(False)

        filters = []
        for key, label in (
            ("all", "All"),
            ("income", "Income"),
            ("subscription", "Subscriptions"),
            ("bill", "Bills"),
            ("paused", "Paused"),
        ):
            button = chip_button(label)
            button.clicked.connect(lambda _checked=False, value=key: self.set_filter(value))
            self.filter_buttons[key] = button
            filters.append(button)

        self.result_label = QLabel("")
        self.result_label.setProperty("role", "count")
        self.selection_label = QLabel("")
        self.selection_label.setProperty("role", "count")
        self.selection_label.setVisible(False)
        controls = QFrame()
        controls.setProperty("role", "toolbar")
        controls.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(8, 7, 8, 7)
        controls_layout.setSpacing(5)
        filter_row = QHBoxLayout()
        filter_row.setSpacing(5)
        for button in filters:
            filter_row.addWidget(button)
        filter_row.addStretch()
        filter_row.addWidget(self.result_label)
        self.action_container = QWidget()
        self.action_container.setVisible(False)
        action_row = QHBoxLayout(self.action_container)
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(6)
        action_row.addWidget(self.selection_label)
        action_row.addStretch()
        action_row.addWidget(self.edit_button)
        action_row.addWidget(self.record_button)
        action_row.addWidget(self.skip_button)
        action_row.addWidget(self.pause_button)
        action_row.addWidget(self.remove_button)
        controls_layout.addLayout(filter_row)
        controls_layout.addWidget(self.action_container)

        card, card_layout = create_card(
            "Recurring schedule",
            subtitle="Review expected money in and out, then record it when it happens",
        )
        self.schedule_card = card
        card_layout.addWidget(controls)
        empty_action = primary_button("Add recurring schedule", "plus")
        empty_action.clicked.connect(self.add_rule)
        self.empty = empty_state(
            "No recurring schedules yet",
            "Add a wage, subscription, bill, or other repeating amount.",
            empty_action,
        )
        card_layout.addWidget(self.empty)
        card_layout.addWidget(self.table, 1)
        layout.addWidget(card, 1)
        self.set_filter("all", refresh=False)
        self._layout_metrics()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_metrics()
        if hasattr(self, "table"):
            self.table.setColumnHidden(3, self.width() < 1050)
            self.table.setColumnHidden(4, self.width() < 950)

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

    def set_filter(self, value: str, refresh: bool = True) -> None:
        self.current_filter = value
        for key, button in self.filter_buttons.items():
            selected = key == value
            button.setChecked(selected)
            button.setProperty("selected", "true" if selected else "false")
            button.style().unpolish(button)
            button.style().polish(button)
        if refresh:
            self.refresh()

    def refresh(self) -> None:
        summary = self.service.summary()
        for key, label in self.metric_values.items():
            value = summary[key]
            if key in {"expected_income_30_days", "expected_outgoings_30_days"}:
                label.setText(compact_money(value))
                label.setToolTip(format_money(value))
            else:
                label.setText(str(value))

        filters = {}
        if self.current_filter == "paused":
            filters["status"] = "paused"
        elif self.current_filter == "income":
            filters["transaction_type"] = "income"
        elif self.current_filter in {"subscription", "bill"}:
            filters["kind"] = self.current_filter
        rules = self.service.list_rules(**filters)
        account_names = {
            account.id: account.name for account in self.accounts.list(include_inactive=True)
        }
        self.table.setRowCount(len(rules))
        today = date.today()
        for row, rule in enumerate(rules):
            due = QTableWidgetItem(format_display_date(rule.next_due_date))
            due.setData(Qt.ItemDataRole.UserRole, rule.id)
            due_date = date.fromisoformat(rule.next_due_date)
            if rule.status == "active" and due_date < today:
                due.setForeground(QColor(Colors.NEGATIVE))
            self.table.setItem(row, 0, due)
            self.table.setItem(row, 1, QTableWidgetItem(rule.name))
            self.table.setCellWidget(
                row,
                2,
                badge(
                    "Income" if rule.transaction_type == "income" else pretty_type(rule.kind),
                    "positive"
                    if rule.transaction_type == "income"
                    else "info"
                    if rule.kind == "subscription"
                    else "neutral",
                ),
            )
            self.table.setItem(row, 3, QTableWidgetItem(pretty_type(rule.frequency)))
            self.table.setItem(
                row,
                4,
                QTableWidgetItem(account_names.get(rule.account_id, "Inactive account")),
            )
            amount_text = (
                format_money(rule.amount)
                if rule.amount_mode == "fixed" and rule.amount is not None
                else f"~{format_money(rule.amount)}"
                if rule.amount is not None
                else "Confirm later"
            )
            amount_item = QTableWidgetItem(amount_text)
            amount_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            amount_item.setForeground(
                QColor(Colors.POSITIVE if rule.transaction_type == "income" else Colors.NEGATIVE)
            )
            self.table.setItem(row, 5, amount_item)
            status, tone = self._display_status(rule, today)
            self.table.setCellWidget(row, 6, badge(status, tone))

        self.result_label.setText(f"{len(rules)} shown")
        has_rules = bool(rules)
        self.empty.setVisible(not has_rules)
        self.table.setVisible(has_rules)
        if has_rules and len(rules) <= 8:
            fit_item_view_height(self.table, len(rules), maximum_rows=8)
            self.schedule_card.setMaximumHeight(190 + self.table.maximumHeight())
        elif has_rules:
            self.table.setMaximumHeight(16777215)
            self.table.setMinimumHeight(320)
            self.schedule_card.setMaximumHeight(16777215)
        else:
            self.schedule_card.setMaximumHeight(330)
        self._sync_actions()

    @staticmethod
    def _display_status(rule, today: date) -> tuple[str, str]:
        if rule.status == "active" and date.fromisoformat(rule.next_due_date) < today:
            return "Overdue", "negative"
        if rule.status == "active":
            return "Active", "positive"
        if rule.status == "paused":
            return "Paused", "muted"
        return "Completed", "info"

    def add_rule(self) -> None:
        accounts = self.accounts.list(include_inactive=False)
        if not accounts:
            QMessageBox.information(self, "No accounts", "Create an account first.")
            return
        form = RecurringRuleForm(
            accounts,
            self.categories.list_categories(),
            self.payment_methods.list_payment_methods(),
            category_service=self.categories,
        )
        if form.exec():
            try:
                self.service.create_rule(**form.values())
                self.notify("Recurring schedule created")
                self.on_changed({"upcoming", "dashboard"})
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save recurring schedule", str(exc))

    def edit_rule(self) -> None:
        rule = self._selected_rule()
        if not rule or rule.status == "completed":
            return
        form = RecurringRuleForm(
            self.accounts.list(include_inactive=True),
            self.categories.list_categories(include_inactive=True),
            self.payment_methods.list_payment_methods(include_inactive=True),
            rule,
            category_service=self.categories,
        )
        if form.exec():
            try:
                self.service.update_rule(rule.id, **form.values())
                self.notify("Recurring schedule updated")
                self.on_changed({"upcoming", "dashboard"})
            except ValueError as exc:
                QMessageBox.warning(self, "Could not save recurring schedule", str(exc))

    def record_payment(self) -> None:
        rule = self._selected_rule()
        if not rule or rule.status != "active":
            return
        dialog = RecordRecurringDialog(rule)
        if dialog.exec():
            try:
                self.service.record_payment(rule.id, **dialog.values())
                self.notify("Recurring income recorded" if rule.transaction_type == "income" else "Recurring payment recorded")
                self.on_changed({"upcoming", "transactions", "accounts", "dashboard"})
            except ValueError as exc:
                QMessageBox.warning(self, "Could not record payment", str(exc))

    def skip_occurrence(self) -> None:
        rule = self._selected_rule()
        if not rule or rule.status != "active":
            return
        confirm = QMessageBox.question(
            self,
            "Skip occurrence",
            f"Skip the {format_display_date(rule.next_due_date)} occurrence of {rule.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.skip_occurrence(rule.id)
            self.notify("Occurrence skipped")
            self.on_changed({"upcoming", "dashboard"})
        except ValueError as exc:
            QMessageBox.warning(self, "Could not skip occurrence", str(exc))

    def toggle_paused(self) -> None:
        rule = self._selected_rule()
        if not rule or rule.status == "completed":
            return
        try:
            paused = rule.status == "active"
            self.service.set_paused(rule.id, paused)
            self.notify("Recurring payment paused" if paused else "Recurring payment resumed")
            self.on_changed({"upcoming", "dashboard"})
        except ValueError as exc:
            QMessageBox.warning(self, "Could not update recurring payment", str(exc))

    def remove_rule(self) -> None:
        rule = self._selected_rule()
        if not rule:
            return
        confirm = QMessageBox.question(
            self,
            "Remove recurring payment",
            f"Remove {rule.name}? Recorded transactions will be kept.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_rule(rule.id)
            self.notify("Recurring payment removed")
            self.on_changed({"upcoming", "dashboard"})
        except ValueError as exc:
            QMessageBox.warning(self, "Could not remove recurring payment", str(exc))

    def _selected_rule(self):
        item = self.table.item(self.table.currentRow(), 0) if self.table.currentRow() >= 0 else None
        rule_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        return self.service.get_rule(str(rule_id)) if rule_id else None

    def _sync_actions(self) -> None:
        rule = self._selected_rule()
        selected = rule is not None
        active = bool(rule and rule.status == "active")
        editable = bool(rule and rule.status != "completed")
        self.selection_label.setText(rule.name if rule else "")
        self.selection_label.setVisible(selected)
        self.edit_button.setEnabled(editable)
        self.record_button.setEnabled(active)
        self.skip_button.setEnabled(active)
        self.pause_button.setEnabled(editable)
        self.remove_button.setEnabled(selected)
        self.action_container.setVisible(selected and self.table.isVisible())
        if rule and rule.status == "paused":
            self.pause_button.setText("Resume")
            self.pause_button.setIcon(icon("play", Colors.PRIMARY_DARK, 17))
        else:
            self.pause_button.setText("Pause")
            self.pause_button.setIcon(icon("pause", Colors.PRIMARY_DARK, 17))
