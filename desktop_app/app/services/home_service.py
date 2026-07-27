from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.models.navigation import WorkspaceRoute
from app.models.transaction import Transaction
from app.repositories.account_repository import AccountRepository
from app.repositories.category_repository import CategoryRepository
from app.services.budget_service import BudgetService
from app.services.dashboard_service import DashboardService
from app.services.goal_service import GoalService
from app.services.import_inbox_service import ImportInboxService
from app.services.loan_service import LoanService
from app.services.recurring_service import RecurringService
from app.utils.dates import format_display_date
from app.utils.money import format_money


@dataclass(frozen=True)
class HomeAction:
    id: str
    priority: int
    severity: str
    title: str
    detail: str
    action_label: str
    route: WorkspaceRoute
    due_date: date | None = None


@dataclass(frozen=True)
class UpcomingDecision:
    id: str
    date: date
    title: str
    amount: Decimal | None
    transaction_type: str
    route: WorkspaceRoute


@dataclass(frozen=True)
class HomeBrief:
    reference_date: date
    summary: str
    primary_action: HomeAction
    attention_items: tuple[HomeAction, ...]
    available_liquidity: Decimal
    safe_spend_configured: bool
    upcoming: tuple[UpcomingDecision, ...]
    recent_transactions: tuple[Transaction, ...]


class HomeService:
    """Build the decision-first Home read model from data the app already knows."""

    ATTENTION_HORIZON_DAYS = 30

    def __init__(self, db: sqlite3.Connection):
        self.dashboard = DashboardService(db)
        self.accounts = AccountRepository(db)
        self.categories = CategoryRepository(db)
        self.budgets = BudgetService(db)
        self.goals = GoalService(db)
        self.imports = ImportInboxService(db)
        self.loans = LoanService(db)
        self.recurring = RecurringService(db)

    def brief(self, reference_date: date | None = None) -> HomeBrief:
        reference = reference_date or date.today()
        snapshot = self.dashboard.global_snapshot()
        attention = self._attention(reference)
        primary = (
            attention.pop(0)
            if attention
            else self._calm_action(snapshot["accounts"], snapshot["recent_transactions"])
        )
        decision_count = len(attention) + (1 if primary.severity != "calm" else 0)
        summary = self._summary(decision_count)
        return HomeBrief(
            reference_date=reference,
            summary=summary,
            primary_action=primary,
            attention_items=tuple(attention[:5]),
            available_liquidity=snapshot["liquidity"],
            safe_spend_configured=False,
            upcoming=tuple(self._upcoming(reference)[:5]),
            recent_transactions=tuple(snapshot["recent_transactions"][:5]),
        )

    def _attention(self, reference: date) -> list[HomeAction]:
        items: list[HomeAction] = []
        horizon = reference + timedelta(days=self.ATTENTION_HORIZON_DAYS)

        for summary in self.imports.list_batches():
            batch = summary.batch
            if batch.status != "review":
                continue
            if summary.error_count:
                count = summary.error_count
                priority = 25
                severity = "urgent"
                title = (
                    f"{count} imported row"
                    f"{'s need' if count != 1 else ' needs'} fixing"
                )
                action = "Fix import"
            elif summary.needs_category_count:
                count = summary.needs_category_count
                priority = 55
                severity = "warning"
                title = (
                    f"{count} imported transaction"
                    f"{'s need' if count != 1 else ' needs'} a category"
                )
                action = "Review inbox"
            elif summary.ready_count:
                count = summary.ready_count
                priority = 85
                severity = "warning"
                title = (
                    f"{count} imported transaction"
                    f"{'s are' if count != 1 else ' is'} ready to post"
                )
                action = "Review and post"
            else:
                continue
            items.append(
                HomeAction(
                    id=f"import:{batch.id}",
                    priority=priority,
                    severity=severity,
                    title=title,
                    detail=f"{batch.source_name} · nothing posts without your review",
                    action_label=action,
                    route=WorkspaceRoute(
                        "activity", "import", batch.id
                    ),
                )
            )

        for rule in self.recurring.list_rules(status="active"):
            due = date.fromisoformat(rule.next_due_date)
            days_until = (due - reference).days
            within_reminder = 0 <= days_until <= rule.reminder_days
            if due < reference or within_reminder:
                overdue = due < reference
                amount = (
                    format_money(rule.amount)
                    if rule.amount is not None
                    else "Amount needs an estimate"
                )
                items.append(
                    HomeAction(
                        id=f"recurring:{rule.id}",
                        priority=10 if overdue else 40,
                        severity="urgent" if overdue else "warning",
                        title=(
                            f"{rule.name} is overdue"
                            if overdue
                            else f"{rule.name} is due {self._relative_day(days_until)}"
                        ),
                        detail=f"{amount} · {format_display_date(rule.next_due_date)}",
                        action_label="Review schedule",
                        route=WorkspaceRoute(
                            "activity", "recurring", rule.id
                        ),
                        due_date=due,
                    )
                )
            elif rule.amount_mode == "variable" and rule.amount is None and due <= horizon:
                items.append(
                    HomeAction(
                        id=f"estimate:{rule.id}",
                        priority=80,
                        severity="warning",
                        title=f"Add an estimate for {rule.name}",
                        detail=(
                            f"Due {format_display_date(rule.next_due_date)} · "
                            "the cash forecast currently excludes it"
                        ),
                        action_label="Add estimate",
                        route=WorkspaceRoute(
                            "activity", "recurring", rule.id
                        ),
                        due_date=due,
                    )
                )

        for account, balance in self.accounts.list_with_balances():
            if balance >= 0:
                continue
            items.append(
                HomeAction(
                    id=f"account:{account.id}",
                    priority=20,
                    severity="urgent",
                    title=f"{account.name} is below zero",
                    detail=f"Current balance {format_money(balance)}",
                    action_label="Review account",
                    route=WorkspaceRoute("position", "accounts", account.id),
                )
            )

        category_names = {
            category.id: category.name
            for category in self.categories.list(include_inactive=True)
        }
        for status in self.budgets.overspent(reference):
            budget_id = status.budget.id or status.budget.category_id
            category_name = category_names.get(
                status.budget.category_id, "A monthly category"
            )
            items.append(
                HomeAction(
                    id=f"budget:{budget_id}",
                    priority=60,
                    severity="warning",
                    title=f"{category_name} is over its monthly plan",
                    detail=(
                        f"{format_money(status.spent)} spent against "
                        f"{format_money(status.limit)}"
                    ),
                    action_label="Review plan",
                    route=WorkspaceRoute(
                        "plan", "monthly", status.budget.category_id
                    ),
                )
            )

        for progress in self.goals.list_progress(reference):
            if progress.on_track is not False:
                continue
            monthly = (
                f" · {format_money(progress.required_monthly_contribution)} per month needed"
                if progress.required_monthly_contribution is not None
                else ""
            )
            items.append(
                HomeAction(
                    id=f"goal:{progress.goal.id}",
                    priority=70,
                    severity="warning",
                    title=f"{progress.goal.name} is behind plan",
                    detail=f"{progress.percent_complete:.0f}% complete{monthly}",
                    action_label="Review goal",
                    route=WorkspaceRoute("plan", "goals", progress.goal.id),
                    due_date=(
                        date.fromisoformat(progress.goal.target_date)
                        if progress.goal.target_date
                        else None
                    ),
                )
            )

        for snapshot in self.loans.list_snapshots(status="active"):
            loan = snapshot.loan
            if not loan.due_date or snapshot.outstanding <= 0:
                continue
            due = date.fromisoformat(loan.due_date)
            if due > horizon:
                continue
            items.append(
                HomeAction(
                    id=f"loan:{loan.id}",
                    priority=5 if due < reference else 30,
                    severity="urgent" if due < reference else "warning",
                    title=(
                        f"{loan.name} has passed its payoff date"
                        if due < reference
                        else f"{loan.name} reaches its payoff date "
                        f"{self._relative_day((due - reference).days)}"
                    ),
                    detail=(
                        f"{format_money(snapshot.outstanding)} principal outstanding · "
                        f"{format_display_date(loan.due_date)}"
                    ),
                    action_label="Review loan",
                    route=WorkspaceRoute("plan", "debt", loan.id),
                    due_date=due,
                )
            )

        return sorted(
            items,
            key=lambda item: (
                item.priority,
                item.due_date or date.max,
                item.title.casefold(),
            ),
        )

    def _upcoming(self, reference: date) -> list[UpcomingDecision]:
        items: list[UpcomingDecision] = []
        for rule in self.recurring.list_rules(status="active"):
            due = date.fromisoformat(rule.next_due_date)
            if due < reference:
                continue
            items.append(
                UpcomingDecision(
                    id=f"recurring:{rule.id}",
                    date=due,
                    title=rule.name,
                    amount=rule.amount,
                    transaction_type=rule.transaction_type,
                    route=WorkspaceRoute("activity", "recurring", rule.id),
                )
            )
        for snapshot in self.loans.list_snapshots(status="active"):
            loan = snapshot.loan
            if not loan.due_date:
                continue
            due = date.fromisoformat(loan.due_date)
            if due < reference:
                continue
            items.append(
                UpcomingDecision(
                    id=f"loan:{loan.id}",
                    date=due,
                    title=f"{loan.name} payoff date",
                    amount=snapshot.outstanding,
                    transaction_type=(
                        "expense" if loan.direction == "borrowed" else "income"
                    ),
                    route=WorkspaceRoute("position", "loans", loan.id),
                )
            )
        return sorted(items, key=lambda item: (item.date, item.title.casefold()))

    @staticmethod
    def _calm_action(accounts: list[dict], transactions: list[Transaction]) -> HomeAction:
        if not accounts:
            return HomeAction(
                id="onboarding:account",
                priority=0,
                severity="calm",
                title="Start by adding the account you use most",
                detail="Your balances stay private on this device.",
                action_label="Add account",
                route=WorkspaceRoute("position", "accounts", action="add"),
            )
        if not transactions:
            return HomeAction(
                id="onboarding:transaction",
                priority=0,
                severity="calm",
                title="Your position is ready for its first activity",
                detail="Record income, spending, or a transfer.",
                action_label="Add transaction",
                route=WorkspaceRoute("activity", "transactions", action="add"),
            )
        return HomeAction(
            id="calm:position",
            priority=0,
            severity="calm",
            title="Nothing needs a decision right now",
            detail="Your recorded plans and schedules have no active warnings.",
            action_label="View position",
            route=WorkspaceRoute("position", "overview"),
        )

    @staticmethod
    def _summary(count: int) -> str:
        if count == 0:
            return "Nothing needs attention right now. Here’s your current position."
        if count == 1:
            return "One thing needs your attention. Here’s what matters first."
        return f"{count} things need your attention. Here’s what matters first."

    @staticmethod
    def _relative_day(days_until: int) -> str:
        if days_until == 0:
            return "today"
        if days_until == 1:
            return "tomorrow"
        return f"in {days_until} days"
