from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.repositories.account_repository import AccountRepository
from app.services.dashboard_service import DashboardService
from app.ui.components import (
    amount_item,
    badge,
    badge_tone,
    clear_layout,
    create_card,
    empty_state,
    metric_card,
    page_layout,
    pretty_type,
    primary_button,
    secondary_button,
    style_table,
)
from app.ui.icons import icon
from app.utils.money import format_money
from app.utils.dates import format_display_date


class DashboardPage(QWidget):
    def __init__(self, db: sqlite3.Connection, on_add_transaction=None, on_add_account=None, on_backup=None):
        super().__init__()
        self.service = DashboardService(db)
        self.account_repo = AccountRepository(db)
        self.cards: dict[str, QLabel] = {}

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
        self.overview_grid.setSpacing(18)
        self.hero = self._build_hero(on_backup)
        self.liquidity_card, liquidity_value = metric_card(
            "Available liquidity",
            format_money(0),
            "Cash and readily available balances",
        )
        self.liquidity_card.setMinimumHeight(174)
        self.liquidity_card.setMaximumHeight(190)
        self.cards["liquidity"] = liquidity_value
        layout.addLayout(self.overview_grid)

        self.monthly_grid = QGridLayout()
        self.monthly_grid.setContentsMargins(0, 0, 0, 0)
        self.monthly_grid.setSpacing(18)
        self.monthly_widgets: list[QWidget] = []
        monthly_metadata = {
            "monthly_income": ("Income this month", "Money in", "positive"),
            "monthly_expenses": ("Spent this month", "Money out", "negative"),
            "monthly_net_flow": ("Monthly cash flow", "Income minus spending", None),
        }
        for key in ("monthly_income", "monthly_expenses", "monthly_net_flow"):
            label, helper, tone = monthly_metadata[key]
            card, value = metric_card(label, format_money(0), helper, tone)
            self.cards[key] = value
            self.monthly_widgets.append(card)
        layout.addLayout(self.monthly_grid)

        add_account = secondary_button("Add account", "plus")
        add_account.clicked.connect(on_add_account or (lambda: None))
        recent_card, recent_layout = create_card(
            "Recent activity",
            subtitle="Your latest income, spending, transfers, and adjustments",
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
        self.content_grid.setSpacing(18)
        self.recent_card = recent_card
        self.accounts_card = accounts_card
        layout.addLayout(self.content_grid)
        layout.addStretch()
        self._layout_dashboard()

    def _build_hero(self, on_backup) -> QFrame:
        hero = QFrame()
        hero.setProperty("role", "heroCard")
        hero.setMinimumHeight(174)
        hero.setMaximumHeight(190)
        layout = QVBoxLayout(hero)
        layout.setContentsMargins(25, 22, 25, 20)
        layout.setSpacing(6)
        label = QLabel("TOTAL NET WORTH")
        label.setProperty("role", "heroLabel")
        value = QLabel(format_money(0))
        value.setProperty("role", "heroValue")
        self.cards["net_worth"] = value
        self.hero_helper = QLabel("Across your active accounts")
        self.hero_helper.setProperty("role", "heroHelper")
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 8, 0, 0)
        updated = QLabel("Local data · Updated just now")
        updated.setProperty("role", "heroHelper")
        backup = QPushButton("Back up now")
        backup.setProperty("variant", "hero")
        backup.setIcon(icon("backup", "#ffffff", 16))
        backup.clicked.connect(on_backup or (lambda: None))
        bottom.addWidget(updated)
        bottom.addStretch()
        bottom.addWidget(backup)
        layout.addWidget(label)
        layout.addWidget(value)
        layout.addWidget(self.hero_helper)
        layout.addLayout(bottom)
        return hero

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_dashboard()

    def _layout_dashboard(self) -> None:
        if not hasattr(self, "overview_grid"):
            return
        width = max(1, self.width())
        clear_layout(self.overview_grid)
        for column in range(3):
            self.overview_grid.setColumnStretch(column, 0)
        if width >= 1160:
            self.overview_grid.addWidget(self.hero, 0, 0)
            self.overview_grid.addWidget(self.liquidity_card, 0, 1)
            self.overview_grid.setColumnStretch(0, 2)
            self.overview_grid.setColumnStretch(1, 1)
        else:
            self.overview_grid.addWidget(self.hero, 0, 0)
            self.overview_grid.addWidget(self.liquidity_card, 1, 0)
            self.overview_grid.setColumnStretch(0, 1)

        clear_layout(self.monthly_grid)
        for column in range(3):
            self.monthly_grid.setColumnStretch(column, 0)
        monthly_columns = 3 if width >= 1050 else 2 if width >= 620 else 1
        for index, card in enumerate(self.monthly_widgets):
            self.monthly_grid.addWidget(card, index // monthly_columns, index % monthly_columns)
            self.monthly_grid.setColumnStretch(index % monthly_columns, 1)

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

    def refresh(self) -> None:
        data = self.service.summary()
        for key, label in self.cards.items():
            label.setText(format_money(data[key]))
            if key == "monthly_net_flow":
                tone = "positive" if data[key] >= 0 else "negative"
                label.setProperty("tone", tone)
                label.style().unpolish(label)
                label.style().polish(label)
        self.hero_helper.setText(
            f"Across {len(data['accounts'])} active account{'s' if len(data['accounts']) != 1 else ''}"
        )

        account_names = {
            account.id: account.name for account in self.account_repo.list(include_inactive=True)
        }
        self.recent.setRowCount(len(data["recent_transactions"]))
        for row_index, transaction in enumerate(data["recent_transactions"]):
            values = [
                format_display_date(transaction.date),
                "",
                transaction.description or "No description",
                account_names.get(transaction.account_id, "Inactive account"),
                "",
            ]
            for col_index, value in enumerate(values):
                self.recent.setItem(row_index, col_index, QTableWidgetItem(str(value)))
            self.recent.setCellWidget(
                row_index, 1, badge(pretty_type(transaction.type), badge_tone(transaction.type))
            )
            self.recent.setItem(
                row_index,
                4,
                amount_item(
                    transaction.amount,
                    neutral=transaction.type in {"transfer_out", "transfer_in", "adjustment"},
                ),
            )
        self.recent.setVisible(bool(data["recent_transactions"]))
        self.recent_empty.setVisible(not data["recent_transactions"])

        accounts = data["accounts"][:8]
        self.accounts.setRowCount(len(accounts))
        for row_index, account in enumerate(accounts):
            values = [account["name"], "", format_money(account["balance"])]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col_index == 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.accounts.setItem(row_index, col_index, item)
            self.accounts.setCellWidget(
                row_index, 1, badge(pretty_type(account["type"]), "neutral")
            )
        self.accounts.setVisible(bool(accounts))
        self.accounts_empty.setVisible(not accounts)
