from __future__ import annotations

import sqlite3
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QWidget,
)

from app.models.goal import GoalProgress, SavingsGoal
from app.services.account_service import AccountService
from app.services.goal_service import GoalService
from app.ui.budgets_page import BudgetProgress
from app.ui.components import (
    FittedLabel,
    badge,
    clear_layout,
    create_card,
    empty_state,
    ghost_button,
    page_layout,
    primary_button,
    soft_button,
)
from app.ui.goal_form import GoalContributionDialog, GoalForm
from app.utils.dates import format_display_date
from app.utils.money import format_money


class GoalProgressBar(BudgetProgress):
    """Budget-style progress visual with goal-appropriate success semantics."""

    WARNING_AT = Decimal("Infinity")
    OVERSPENT_AT = Decimal("Infinity")

    def set_progress(self, percent_used: Decimal, *, started: bool = True) -> None:
        percent = Decimal(percent_used)
        super().set_progress(
            min(Decimal("100"), max(Decimal("0"), percent)),
            started=True,
        )
        self.label.setText(f"{self._format_percent(max(Decimal('0'), percent))}%")
        self.setToolTip("Savings-goal progress")


class GoalsPage(QWidget):
    def __init__(self, db: sqlite3.Connection, on_changed, notify=None):
        super().__init__()
        self.service = GoalService(db)
        self.account_service = AccountService(db)
        self.on_changed = on_changed
        self.notify = notify or (lambda _message: None)
        self._goals_by_id: dict[str, SavingsGoal] = {}
        self._goal_cards: list[QFrame] = []

        add_button = primary_button("Add goal", "plus")
        add_button.clicked.connect(self.add_goal)
        layout = page_layout(
            self,
            "Savings goals",
            "Turn savings targets into clear, measurable progress",
            add_button,
        )
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        empty_action = primary_button("Add savings goal", "plus")
        empty_action.clicked.connect(self.add_goal)
        self.empty = empty_state(
            "No active savings goals",
            "Create a target and link an account or record contributions manually.",
            empty_action,
        )
        layout.addWidget(self.empty)

        self.goal_grid = QGridLayout()
        self.goal_grid.setContentsMargins(0, 0, 0, 0)
        self.goal_grid.setHorizontalSpacing(16)
        self.goal_grid.setVerticalSpacing(16)
        layout.addLayout(self.goal_grid)
        layout.addStretch()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_goal_cards()

    def refresh(self) -> None:
        progress_items = self.service.list_progress()
        account_names = {
            account.id: account.name
            for account in self.account_service.list_accounts(include_inactive=True)
        }
        self._clear_goal_cards()
        self._goals_by_id = {
            item.goal.id: item.goal
            for item in progress_items
            if item.goal.id is not None
        }
        self._goal_cards = [
            self._build_goal_card(item, account_names) for item in progress_items
        ]
        self.empty.setVisible(not progress_items)
        self._goal_columns = None
        self._layout_goal_cards()

    def _build_goal_card(
        self,
        progress: GoalProgress,
        account_names: dict[str | None, str],
    ) -> QFrame:
        goal = progress.goal
        status_text, status_tone = self._status_badge(progress)
        deadline = (
            f"Target date {format_display_date(goal.target_date)}"
            if goal.target_date
            else "No target date"
        )
        card, layout = create_card(
            goal.name,
            subtitle=deadline,
            action=badge(status_text, status_tone),
        )
        card.setMinimumHeight(245)

        amounts = FittedLabel(
            f"{format_money(progress.current_amount)} of {format_money(goal.target_amount)}",
            maximum_size=23,
            minimum_size=13,
        )
        amounts.setProperty("role", "metricValue")
        amounts.setMinimumHeight(32)
        layout.addWidget(amounts)
        layout.addWidget(GoalProgressBar(progress.percent_complete))

        tracking = (
            f"Tracked from {account_names.get(goal.linked_account_id, 'inactive account')}"
            if goal.linked_account_id
            else "Tracked from recorded contributions"
        )
        if progress.current_amount >= goal.target_amount:
            contribution_text = "Target reached"
        elif progress.required_monthly_contribution is not None:
            contribution_text = (
                f"{format_money(progress.required_monthly_contribution)} per month needed"
            )
        else:
            contribution_text = "No monthly contribution target"
        helper = QLabel(f"{tracking}  ·  {contribution_text}")
        helper.setProperty("role", "helper")
        helper.setWordWrap(True)
        layout.addWidget(helper)
        layout.addStretch()

        edit_button = ghost_button("Edit", "edit")
        contribute_button = soft_button("Add contribution", "plus")
        archive_button = ghost_button("Archive", "archive")
        edit_button.clicked.connect(
            lambda _checked=False, goal_id=goal.id: self.edit_goal(goal_id)
        )
        contribute_button.clicked.connect(
            lambda _checked=False, goal_id=goal.id: self.add_contribution(goal_id)
        )
        contribute_button.setVisible(goal.linked_account_id is None)
        archive_button.clicked.connect(
            lambda _checked=False, goal_id=goal.id: self.archive_goal(goal_id)
        )
        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(7)
        actions_layout.addWidget(contribute_button)
        actions_layout.addStretch()
        actions_layout.addWidget(edit_button)
        actions_layout.addWidget(archive_button)
        layout.addWidget(actions)
        return card

    def _layout_goal_cards(self) -> None:
        if not hasattr(self, "goal_grid"):
            return
        columns = 2 if self.width() >= 820 else 1
        if getattr(self, "_goal_columns", None) == columns:
            return
        self._goal_columns = columns
        clear_layout(self.goal_grid)
        for column in range(2):
            self.goal_grid.setColumnStretch(column, 1 if column < columns else 0)
        for index, card in enumerate(self._goal_cards):
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.goal_grid.addWidget(card, index // columns, index % columns)

    def _clear_goal_cards(self) -> None:
        while self.goal_grid.count():
            item = self.goal_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
        self._goal_cards = []

    def add_goal(self) -> None:
        form = GoalForm(self._goal_accounts(), parent=self)
        if form.exec():
            try:
                self.service.create_goal(**form.values())
                self._changed("Savings goal created")
            except (ValueError, sqlite3.IntegrityError) as exc:
                QMessageBox.warning(self, "Could not save goal", str(exc))

    def edit_goal(self, goal_id: str | None) -> None:
        goal = self._goals_by_id.get(str(goal_id)) if goal_id else None
        if not goal:
            return
        form = GoalForm(self._goal_accounts(include_inactive=True), goal, self)
        if form.exec():
            try:
                self.service.update_goal(goal.id, **form.values())
                self._changed("Savings goal updated")
            except (ValueError, sqlite3.IntegrityError) as exc:
                QMessageBox.warning(self, "Could not update goal", str(exc))

    def archive_goal(self, goal_id: str | None) -> None:
        goal = self._goals_by_id.get(str(goal_id)) if goal_id else None
        if not goal or goal.id is None:
            return
        try:
            self.service.set_active(goal.id, False)
            self._changed("Savings goal archived")
        except (ValueError, sqlite3.IntegrityError) as exc:
            QMessageBox.warning(self, "Could not archive goal", str(exc))

    def add_contribution(self, goal_id: str | None) -> None:
        goal = self._goals_by_id.get(str(goal_id)) if goal_id else None
        if not goal or goal.id is None:
            return
        if goal.linked_account_id is not None:
            QMessageBox.information(
                self,
                "Tracked automatically",
                "This goal follows its linked account balance and does not use "
                "manual contributions.",
            )
            return
        accounts = self._goal_accounts()
        account_ids = {account.id for account in accounts}
        if len(account_ids) < 2:
            QMessageBox.information(
                self,
                "Two accounts required",
                "Create two active non-liability accounts to move money into this goal.",
            )
            return
        dialog = GoalContributionDialog(goal, accounts, self)
        if dialog.exec():
            try:
                self.service.add_contribution(goal.id, **dialog.values())
                self._changed(
                    "Goal contribution recorded",
                    {"goals", "accounts", "transactions", "dashboard"},
                )
            except (ValueError, sqlite3.IntegrityError) as exc:
                QMessageBox.warning(self, "Could not record contribution", str(exc))

    def _goal_accounts(self, include_inactive: bool = False):
        return [
            account
            for account in self.account_service.list_accounts(
                include_inactive=include_inactive
            )
            if account.type not in self.account_service.LIABILITY_TYPES
        ]

    @staticmethod
    def _status_badge(progress: GoalProgress) -> tuple[str, str]:
        if progress.current_amount >= progress.goal.target_amount:
            return "Complete", "positive"
        if progress.on_track is True:
            return "On track", "positive"
        if progress.on_track is False:
            return "Needs attention", "negative"
        return "No deadline", "neutral"

    def _changed(self, message: str, tags: set[str] | None = None) -> None:
        self.notify(message)
        self.refresh()
        self.on_changed(tags or {"goals", "dashboard"})
