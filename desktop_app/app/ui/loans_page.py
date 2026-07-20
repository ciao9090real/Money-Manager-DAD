from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from app.models.loan import LoanSnapshot
from app.repositories.account_repository import AccountRepository
from app.services.loan_service import LoanService
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
    primary_button,
    soft_button,
    style_table,
)
from app.ui.loan_form import LoanForm, LoanPaymentDialog
from app.utils.dates import format_display_date
from app.utils.money import format_money, to_decimal


class LoansPage(QWidget):
    AMORTIZATION_PAGE_SIZE = 24

    def __init__(self, db: sqlite3.Connection, on_changed, notify=None):
        super().__init__()
        self.service = LoanService(db)
        self.accounts = AccountRepository(db)
        self.on_changed = on_changed
        self.notify = notify or (lambda _message: None)
        self.current_filter = "all"
        self.filter_buttons = {}

        add_button = primary_button("Add loan", "plus")
        add_button.clicked.connect(self.add_loan)
        layout = page_layout(
            self,
            "Loans",
            "Track principal borrowed and lent, then explore interest-aware payoff estimates",
            add_button,
        )
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.metric_grid = QGridLayout()
        self.metric_grid.setContentsMargins(0, 0, 0, 0)
        self.metric_grid.setSpacing(14)
        self.metric_widgets: list[QWidget] = []
        self.metric_values: dict[str, QLabel] = {}
        for key, label, helper, tone in (
            ("borrowed", "Borrowed", "Principal still owed", "negative"),
            ("lent", "Money lent", "Principal still receivable", "positive"),
            ("net_position", "Net loan position", "Lent minus borrowed", None),
            ("active_count", "Active loans", "Borrowed and lent records", None),
        ):
            card, value = metric_card(label, "0" if key == "active_count" else format_money(0), helper, tone)
            self.metric_widgets.append(card)
            self.metric_values[key] = value
        layout.addLayout(self.metric_grid)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [
                "Loan",
                "Direction",
                "Counterparty",
                "Principal",
                "Principal outstanding",
                "Interest rate",
                "Due",
                "Status",
            ]
        )
        style_table(self.table)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 8):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.itemSelectionChanged.connect(self._sync_actions)
        self.table.itemDoubleClicked.connect(lambda _item: self.edit_loan())

        filters = []
        for key, label in (
            ("all", "All"),
            ("borrowed", "Borrowed"),
            ("lent", "Lent"),
            ("settled", "Settled"),
        ):
            button = chip_button(label)
            button.clicked.connect(lambda _checked=False, value=key: self.set_filter(value))
            self.filter_buttons[key] = button
            filters.append(button)
        self.result_label = QLabel("")
        self.result_label.setProperty("role", "count")
        self.edit_button = ghost_button("Edit", "edit")
        self.payment_button = soft_button("Record payment", "transactions")
        self.edit_button.clicked.connect(self.edit_loan)
        self.payment_button.clicked.connect(self.record_payment)
        self.edit_button.setVisible(False)
        self.payment_button.setVisible(False)

        controls = QFrame()
        controls.setProperty("role", "toolbar")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(8, 7, 8, 7)
        controls_layout.setSpacing(5)
        for button in filters:
            controls_layout.addWidget(button)
        controls_layout.addStretch()
        controls_layout.addWidget(self.result_label)
        controls_layout.addWidget(self.edit_button)
        controls_layout.addWidget(self.payment_button)

        card, card_layout = create_card(
            "Loan book",
            subtitle="Borrowed liabilities and money owed back to you",
        )
        self.loan_card = card
        card_layout.addWidget(controls)
        empty_action = primary_button("Add loan", "plus")
        empty_action.clicked.connect(self.add_loan)
        self.empty = empty_state(
            "No loans yet",
            "Add money borrowed or money lent to keep net worth complete.",
            empty_action,
        )
        card_layout.addWidget(self.empty)
        card_layout.addWidget(self.table)
        layout.addWidget(card, 1)

        self.payoff_card = self._build_payoff_planner()
        layout.addWidget(self.payoff_card)
        self.set_filter("all", refresh=False)
        self._layout_metrics()
        self._layout_payoff_summary()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_metrics()
        self._layout_payoff_summary()
        if hasattr(self, "table"):
            self.table.setColumnHidden(2, self.width() < 1050)
            self.table.setColumnHidden(3, self.width() < 1100)
            self.table.setColumnHidden(5, self.width() < 1050)

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

    def _build_payoff_planner(self) -> QFrame:
        card, layout = create_card(
            "Payoff planner",
            subtitle="See how an extra monthly payment changes payoff time and interest",
        )

        self.payoff_empty = empty_state(
            "Select an active borrowed loan",
            "Payoff estimates are available for money you owe with an interest rate and due date.",
        )
        layout.addWidget(self.payoff_empty)

        self.payoff_controls = QFrame()
        self.payoff_controls.setProperty("role", "toolbar")
        controls_layout = QHBoxLayout(self.payoff_controls)
        controls_layout.setContentsMargins(8, 7, 8, 7)
        controls_layout.setSpacing(9)
        self.payoff_subject = QLabel()
        self.payoff_subject.setProperty("role", "sectionTitle")
        regular_label = QLabel("Regular each month")
        regular_label.setProperty("role", "metricLabel")
        self.regular_payment = QLineEdit()
        self.regular_payment.setPlaceholderText("From due date")
        self.regular_payment.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.regular_payment.setMaximumWidth(140)
        extra_label = QLabel("Extra each month")
        extra_label.setProperty("role", "metricLabel")
        self.extra_payment = QLineEdit()
        self.extra_payment.setPlaceholderText("50.00")
        self.extra_payment.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.extra_payment.setMaximumWidth(150)
        self.extra_payment.returnPressed.connect(self.calculate_payoff)
        self.calculate_payoff_button = soft_button("Calculate", "loans")
        self.calculate_payoff_button.clicked.connect(self.calculate_payoff)
        controls_layout.addWidget(self.payoff_subject)
        controls_layout.addStretch()
        controls_layout.addWidget(regular_label)
        controls_layout.addWidget(self.regular_payment)
        controls_layout.addWidget(extra_label)
        controls_layout.addWidget(self.extra_payment)
        controls_layout.addWidget(self.calculate_payoff_button)
        layout.addWidget(self.payoff_controls)

        self.payoff_summary_grid = QGridLayout()
        self.payoff_summary_grid.setContentsMargins(0, 0, 0, 0)
        self.payoff_summary_grid.setSpacing(14)
        self.payoff_metric_widgets: list[QWidget] = []
        self.payoff_metric_values: dict[str, QLabel] = {}
        for key, label, value, helper, tone in (
            ("payoff_date", "New payoff date", "—", "With the extra payment", None),
            (
                "interest_saved",
                "Interest saved",
                format_money(0),
                "Compared with the current plan",
                "positive",
            ),
            ("months_saved", "Time saved", "0 months", "Earlier than scheduled", "positive"),
        ):
            metric, value_label = metric_card(label, value, helper, tone, compact=True)
            self.payoff_metric_widgets.append(metric)
            self.payoff_metric_values[key] = value_label
        layout.addLayout(self.payoff_summary_grid)

        self.payoff_comparison_label = QLabel(
            "Enter an extra amount to compare the current and accelerated plans."
        )
        self.payoff_comparison_label.setProperty("role", "helper")
        self.payoff_comparison_label.setWordWrap(True)
        layout.addWidget(self.payoff_comparison_label)

        self.amortization_table = QTableWidget(0, 6)
        self.amortization_table.setHorizontalHeaderLabels(
            ["Payment", "Date", "Amount", "Principal", "Interest", "Remaining"]
        )
        style_table(self.amortization_table)
        amortization_header = self.amortization_table.horizontalHeader()
        for column in (0, 1):
            amortization_header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        for column in range(2, 6):
            amortization_header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        self.amortization_table.setVisible(False)
        layout.addWidget(self.amortization_table)

        self.amortization_footer = QWidget()
        footer_layout = QHBoxLayout(self.amortization_footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)
        self.amortization_count = QLabel()
        self.amortization_count.setProperty("role", "count")
        self.load_more_amortization_button = ghost_button("Load more payments", "download")
        self.load_more_amortization_button.clicked.connect(self.load_more_amortization)
        footer_layout.addWidget(self.amortization_count)
        footer_layout.addStretch()
        footer_layout.addWidget(self.load_more_amortization_button)
        self.amortization_footer.setVisible(False)
        layout.addWidget(self.amortization_footer)

        self._payoff_loan_id: str | None = None
        self._amortization_entries: list[object] = []
        self._amortization_visible_count = self.AMORTIZATION_PAGE_SIZE
        self.payoff_controls.setVisible(False)
        for metric in self.payoff_metric_widgets:
            metric.setVisible(False)
        self.payoff_comparison_label.setVisible(False)
        return card

    def _layout_payoff_summary(self) -> None:
        if not hasattr(self, "payoff_summary_grid"):
            return
        columns = 3 if self.width() >= 820 else 1
        if getattr(self, "_payoff_summary_columns", None) == columns:
            return
        self._payoff_summary_columns = columns
        clear_layout(self.payoff_summary_grid)
        for column in range(3):
            self.payoff_summary_grid.setColumnStretch(column, 1 if column < columns else 0)
        for index, card in enumerate(self.payoff_metric_widgets):
            self.payoff_summary_grid.addWidget(card, index // columns, index % columns)

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
        for key in ("borrowed", "lent", "net_position"):
            label = self.metric_values[key]
            label.setText(compact_money(summary[key]))
            label.setToolTip(format_money(summary[key]))
        self.metric_values["active_count"].setText(str(summary["active_count"]))
        net_tone = "positive" if summary["net_position"] > 0 else "negative" if summary["net_position"] < 0 else "neutral"
        self.metric_values["net_position"].setProperty("tone", net_tone)
        self.metric_values["net_position"].style().unpolish(self.metric_values["net_position"])
        self.metric_values["net_position"].style().polish(self.metric_values["net_position"])

        direction = self.current_filter if self.current_filter in {"borrowed", "lent"} else None
        status = "settled" if self.current_filter == "settled" else None
        snapshots = self.service.list_snapshots(direction=direction, status=status)
        self.table.setRowCount(len(snapshots))
        for row, snapshot in enumerate(snapshots):
            loan = snapshot.loan
            name_item = QTableWidgetItem(loan.name)
            name_item.setData(Qt.ItemDataRole.UserRole, loan.id)
            self.table.setItem(row, 0, name_item)
            direction_tone = "negative" if loan.direction == "borrowed" else "info"
            self.table.setCellWidget(row, 1, badge(loan.direction.title(), direction_tone))
            self.table.setItem(row, 2, QTableWidgetItem(loan.counterparty))
            self.table.setItem(row, 3, amount_item(loan.principal, neutral=True))
            self.table.setItem(row, 4, amount_item(snapshot.outstanding, neutral=True))
            rate_item = QTableWidgetItem(f"{loan.interest_rate:.2f}%")
            rate_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 5, rate_item)
            self.table.setItem(
                row,
                6,
                QTableWidgetItem(format_display_date(loan.due_date) if loan.due_date else "No due date"),
            )
            self.table.setCellWidget(
                row,
                7,
                badge("Active" if loan.status == "active" else "Settled", "positive" if loan.status == "active" else "muted"),
            )

        self.result_label.setText(f"{len(snapshots)} shown")
        has_rows = bool(snapshots)
        self.empty.setVisible(not has_rows)
        self.table.setVisible(has_rows)
        if has_rows and len(snapshots) <= 9:
            fit_item_view_height(self.table, len(snapshots), maximum_rows=9)
            self.loan_card.setMaximumHeight(175 + self.table.maximumHeight())
        elif has_rows:
            self.table.setMaximumHeight(16777215)
            self.table.setMinimumHeight(320)
            self.loan_card.setMaximumHeight(16777215)
        else:
            self.loan_card.setMaximumHeight(310)
        self._sync_actions()

    def add_loan(self) -> None:
        accounts = self._funding_accounts()
        if not accounts:
            QMessageBox.information(
                self,
                "No account",
                "Create a bank, current, savings, cash, or wallet account first.",
            )
            return
        form = LoanForm(accounts)
        if form.exec():
            try:
                self.service.create_loan(**form.create_values())
                self._changed("Loan added")
            except ValueError as exc:
                QMessageBox.warning(self, "Could not add loan", str(exc))

    def edit_loan(self) -> None:
        snapshot = self._selected_snapshot()
        if not snapshot:
            return
        form = LoanForm(self._funding_accounts(include_inactive=True), snapshot.loan)
        if form.exec():
            try:
                self.service.update_loan(snapshot.loan.id, **form.edit_values())
                self._changed("Loan updated")
            except ValueError as exc:
                QMessageBox.warning(self, "Could not update loan", str(exc))

    def record_payment(self) -> None:
        snapshot = self._selected_snapshot()
        if not snapshot or snapshot.loan.status != "active":
            return
        accounts = self._funding_accounts()
        if not accounts:
            QMessageBox.information(self, "No account", "No active payment account is available.")
            return
        dialog = LoanPaymentDialog(snapshot, accounts)
        if dialog.exec():
            try:
                self.service.record_payment(snapshot.loan.id, **dialog.values())
                self._changed("Loan payment recorded")
            except ValueError as exc:
                QMessageBox.warning(self, "Could not record payment", str(exc))

    def calculate_payoff(self) -> None:
        snapshot = self._selected_snapshot()
        if not self._is_payoff_eligible(snapshot):
            return
        self._reset_payoff_results()
        self.payoff_comparison_label.setText(
            "Enter an extra amount to compare the current and accelerated plans."
        )
        try:
            extra_payment = to_decimal(self.extra_payment.text())
            if extra_payment <= 0:
                raise ValueError("Extra monthly payment must be positive")
            comparison = self.service.payoff_comparison(
                snapshot.loan.id,
                extra_payment,
                monthly_payment=self.regular_payment.text().strip() or None,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Could not calculate payoff", str(exc))
            return

        current_plan = comparison["without_extra"]
        accelerated_plan = comparison["with_extra"]
        months_saved = comparison.get(
            "months_saved",
            comparison.get("periods_saved", 0),
        )
        self.payoff_metric_values["payoff_date"].setText(
            format_display_date(accelerated_plan.payoff_date)
        )
        self.payoff_metric_values["interest_saved"].setText(
            format_money(comparison["interest_saved"])
        )
        month_label = "month" if months_saved == 1 else "months"
        self.payoff_metric_values["months_saved"].setText(
            f"{months_saved} {month_label}"
        )
        for metric in self.payoff_metric_widgets:
            metric.setVisible(True)
        self.payoff_comparison_label.setText(
            f"Current plan: {format_display_date(current_plan.payoff_date)} with "
            f"{format_money(current_plan.total_interest_paid)} interest. "
            f"With {format_money(extra_payment)} extra each month: "
            f"{format_money(accelerated_plan.total_interest_paid)} interest."
        )
        self.payoff_comparison_label.setVisible(True)
        self._amortization_entries = list(accelerated_plan.entries)
        self._amortization_visible_count = self.AMORTIZATION_PAGE_SIZE
        self._render_amortization()

    def load_more_amortization(self) -> None:
        self._amortization_visible_count += self.AMORTIZATION_PAGE_SIZE
        self._render_amortization()

    def _render_amortization(self) -> None:
        visible_entries = self._amortization_entries[: self._amortization_visible_count]
        self.amortization_table.setRowCount(len(visible_entries))
        for row, entry in enumerate(visible_entries):
            period = QTableWidgetItem(str(entry.period))
            period.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.amortization_table.setItem(row, 0, period)
            self.amortization_table.setItem(
                row,
                1,
                QTableWidgetItem(format_display_date(entry.date)),
            )
            self.amortization_table.setItem(row, 2, amount_item(entry.payment, neutral=True))
            self.amortization_table.setItem(
                row,
                3,
                amount_item(entry.principal_portion, neutral=True),
            )
            self.amortization_table.setItem(
                row,
                4,
                amount_item(entry.interest_portion, neutral=True),
            )
            self.amortization_table.setItem(
                row,
                5,
                amount_item(entry.remaining_balance, neutral=True),
            )

        has_entries = bool(visible_entries)
        self.amortization_table.setVisible(has_entries)
        self.amortization_footer.setVisible(has_entries)
        if has_entries:
            fit_item_view_height(
                self.amortization_table,
                len(visible_entries),
                maximum_rows=8,
            )
        total = len(self._amortization_entries)
        shown = len(visible_entries)
        self.amortization_count.setText(
            f"{shown} of {total} payment{'s' if total != 1 else ''} shown"
        )
        self.load_more_amortization_button.setVisible(shown < total)

    def _sync_payoff_selection(self, snapshot: LoanSnapshot | None) -> None:
        if not self._is_payoff_eligible(snapshot):
            self._payoff_loan_id = None
            self.payoff_empty.setVisible(True)
            self.payoff_controls.setVisible(False)
            self.payoff_comparison_label.setVisible(False)
            self._reset_payoff_results()
            return
        assert snapshot is not None
        if snapshot.loan.id == self._payoff_loan_id:
            return
        self._payoff_loan_id = snapshot.loan.id
        self.payoff_empty.setVisible(False)
        self.payoff_controls.setVisible(True)
        self.payoff_subject.setText(snapshot.loan.name)
        self.regular_payment.clear()
        self.extra_payment.clear()
        self._reset_payoff_results()
        self.payoff_comparison_label.setText(
            "Enter an extra amount to compare the current and accelerated plans."
        )
        self.payoff_comparison_label.setVisible(True)

    def _reset_payoff_results(self) -> None:
        self.payoff_metric_values["payoff_date"].setText("—")
        self.payoff_metric_values["interest_saved"].setText(format_money(0))
        self.payoff_metric_values["months_saved"].setText("0 months")
        for metric in self.payoff_metric_widgets:
            metric.setVisible(False)
        self._amortization_entries = []
        self._amortization_visible_count = self.AMORTIZATION_PAGE_SIZE
        self.amortization_table.setRowCount(0)
        self.amortization_table.setVisible(False)
        self.amortization_footer.setVisible(False)

    @staticmethod
    def _is_payoff_eligible(snapshot: LoanSnapshot | None) -> bool:
        return bool(
            snapshot
            and snapshot.loan.id is not None
            and snapshot.loan.direction == "borrowed"
            and snapshot.loan.status == "active"
            and snapshot.outstanding > 0
        )

    def _selected_snapshot(self) -> LoanSnapshot | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        loan_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        return self.service.get_snapshot(str(loan_id)) if loan_id else None

    def _sync_actions(self) -> None:
        snapshot = self._selected_snapshot()
        self.edit_button.setVisible(snapshot is not None)
        self.payment_button.setVisible(snapshot is not None and snapshot.loan.status == "active")
        self._sync_payoff_selection(snapshot)

    def _funding_accounts(self, include_inactive: bool = False):
        return [
            account
            for account in self.accounts.list(include_inactive=include_inactive)
            if account.type in self.service.FUNDING_ACCOUNT_TYPES
        ]

    def _changed(self, message: str) -> None:
        self.notify(message)
        self.on_changed({"loans", "accounts", "transactions", "dashboard"})
