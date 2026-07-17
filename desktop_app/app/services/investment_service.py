from __future__ import annotations

import sqlite3
from datetime import date as Date, timedelta
from decimal import Decimal

from app.core.database import unit_of_work
from app.models.investment import (
    Investment,
    InvestmentLiquidationShare,
    InvestmentPerformancePoint,
    InvestmentSnapshot,
    InvestmentValuePoint,
)
from app.repositories.account_repository import AccountRepository
from app.repositories.investment_repository import InvestmentRepository
from app.services.account_service import AccountService
from app.services.transaction_service import TransactionService
from app.utils.dates import require_iso_date
from app.utils.money import cents_to_decimal, decimal_to_cents, require_positive, to_decimal
from app.utils.validators import require_text


class InvestmentService:
    KINDS = {"fund", "etf", "stock", "bond", "crypto", "other"}
    PERFORMANCE_INTERVALS = {"updates", "monthly"}
    FUNDING_ACCOUNT_TYPES = {
        "bank",
        "current_account",
        "savings_account",
        "cash",
        "wallet",
        "benefit",
    }

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.investments = InvestmentRepository(db)
        self.account_repository = AccountRepository(db)
        self.accounts = AccountService(db)
        self.transactions = TransactionService(db)

    def create_investment(
        self,
        name: str,
        kind: str,
        source_account_id: str,
        amount: object,
        date: str,
        current_value: object = None,
        symbol: str | None = None,
        notes: str | None = None,
    ) -> InvestmentSnapshot:
        with unit_of_work(self.db):
            cleaned_name = require_text(name, "Investment name")
            self._funding_account(source_account_id)
            contribution = require_positive(amount)
            value = self._value(current_value, contribution)
            transaction_date = self._investment_date(date)
            account = self.accounts.create_account(cleaned_name, "investment")
            assert account.id is not None
            investment = self.investments.create(
                Investment(
                    id=None,
                    name=cleaned_name,
                    kind=self._kind(kind),
                    symbol=self._symbol(symbol),
                    account_id=account.id,
                    notes=self._notes(notes),
                )
            )
            assert investment.id is not None
            self.transactions.add_transfer(
                source_account_id,
                account.id,
                contribution,
                transaction_date,
                f"Invest in {cleaned_name}",
                notes,
                investment_id=investment.id,
            )
            difference = value - contribution
            if difference:
                self.transactions.add_adjustment(
                    account.id,
                    difference,
                    transaction_date,
                    f"Set {cleaned_name} market value",
                    investment_id=investment.id,
                )
            self.investments.record_value(investment.id, transaction_date, value)
            return self._snapshot(investment.id)

    def update_investment(
        self,
        investment_id: str,
        name: str,
        kind: str,
        symbol: str | None = None,
        notes: str | None = None,
    ) -> InvestmentSnapshot:
        with unit_of_work(self.db):
            investment = self._investment(investment_id)
            cleaned_name = require_text(name, "Investment name")
            investment.name = cleaned_name
            investment.kind = self._kind(kind)
            investment.symbol = self._symbol(symbol)
            investment.notes = self._notes(notes)
            account = self.account_repository.get(investment.account_id)
            if not account:
                raise ValueError("Investment account not found")
            self.accounts.update_account(
                account.id,
                cleaned_name,
                "investment",
                account.parent_id,
                account.opening_balance,
                account.is_active,
                account.display_order,
            )
            self.investments.update(investment)
            return self._snapshot(investment_id)

    def add_funds(
        self,
        investment_id: str,
        source_account_id: str,
        amount: object,
        date: str,
    ) -> InvestmentSnapshot:
        with unit_of_work(self.db):
            investment = self._investment(investment_id)
            self._funding_account(source_account_id)
            if source_account_id == investment.account_id:
                raise ValueError("Funding and investment accounts must be different")
            transaction_date = self._investment_date(date)
            self._require_current_timeline_date(investment.id, transaction_date)
            self.transactions.add_transfer(
                source_account_id,
                investment.account_id,
                require_positive(amount),
                transaction_date,
                f"Add funds to {investment.name}",
                investment_id=investment.id,
            )
            current_value = self.accounts.account_balance(investment.account_id)
            self.investments.record_value(
                investment.id,
                transaction_date,
                current_value,
            )
            return self._snapshot(investment_id)

    def update_value(
        self,
        investment_id: str,
        current_value: object,
        date: str,
    ) -> InvestmentSnapshot:
        with unit_of_work(self.db):
            investment = self._investment(investment_id)
            target = self._value(current_value)
            transaction_date = self._investment_date(date)
            self._require_current_timeline_date(investment.id, transaction_date)
            current = self.accounts.account_balance(investment.account_id)
            difference = target - current
            if difference:
                self.transactions.add_adjustment(
                    investment.account_id,
                    difference,
                    transaction_date,
                    f"Update {investment.name} market value",
                    investment_id=investment.id,
                )
            self.investments.record_value(investment.id, transaction_date, target)
            return self._snapshot(investment_id)

    def liquidation_plan(
        self,
        investment_id: str,
    ) -> list[InvestmentLiquidationShare]:
        investment = self._investment(investment_id)
        current_value = self.accounts.account_balance(investment.account_id)
        sources = self.investments.list_funding_sources(investment_id)
        if not sources:
            if current_value:
                raise ValueError("No original funding account was found for this investment")
            return []

        source_accounts = []
        for account_id, contributed in sources:
            account = self.account_repository.get(account_id)
            if not account:
                raise ValueError("An original funding account is no longer available")
            if not account.is_active:
                raise ValueError(f"Original funding account '{account.name}' is inactive")
            source_accounts.append((account, contributed))

        total_contributed_cents = sum(
            decimal_to_cents(contributed)
            for _account, contributed in source_accounts
        )
        if total_contributed_cents <= 0:
            if current_value:
                raise ValueError("The original contribution amounts are unavailable")
            return []

        remaining_cents = decimal_to_cents(current_value)
        shares: list[InvestmentLiquidationShare] = []
        for index, (account, contributed) in enumerate(source_accounts):
            contributed_cents = decimal_to_cents(contributed)
            if index == len(source_accounts) - 1:
                proceeds_cents = remaining_cents
            else:
                proceeds_cents = (
                    decimal_to_cents(current_value)
                    * contributed_cents
                    // total_contributed_cents
                )
                remaining_cents -= proceeds_cents
            shares.append(
                InvestmentLiquidationShare(
                    account_id=str(account.id),
                    account_name=account.name,
                    contributed=contributed,
                    proceeds=cents_to_decimal(proceeds_cents),
                )
            )
        return shares

    def delete_investment(self, investment_id: str, date: str) -> None:
        with unit_of_work(self.db):
            investment = self._investment(investment_id)
            transaction_date = self._investment_date(date)
            self._require_current_timeline_date(investment.id, transaction_date)
            shares = self.liquidation_plan(investment_id)
            for share in shares:
                if not share.proceeds:
                    continue
                self.transactions.add_transfer(
                    investment.account_id,
                    share.account_id,
                    share.proceeds,
                    transaction_date,
                    f"Liquidate {investment.name}",
                    investment_id=investment.id,
                )
            remaining = self.accounts.account_balance(investment.account_id)
            if remaining:
                raise RuntimeError("Investment liquidation did not settle to zero")
            self.investments.record_value(
                investment.id,
                transaction_date,
                Decimal("0"),
            )
            self.investments.delete(investment.id)
            self.account_repository.deactivate(investment.account_id)

    def list_snapshots(self) -> list[InvestmentSnapshot]:
        return [
            self._make_snapshot(investment, contributed, current)
            for investment, contributed, current in self.investments.list_with_values()
        ]

    def get_snapshot(self, investment_id: str) -> InvestmentSnapshot | None:
        return next(
            (
                snapshot
                for snapshot in self.list_snapshots()
                if snapshot.investment.id == investment_id
            ),
            None,
        )

    def value_history(self, investment_id: str) -> list[InvestmentValuePoint]:
        self._investment(investment_id)
        return self.investments.list_value_history(investment_id)

    def edit_value_update(
        self,
        investment_id: str,
        point_id: str,
        current_value: object,
    ) -> InvestmentValuePoint:
        with unit_of_work(self.db):
            investment = self._investment(investment_id)
            history, index = self._history_position(investment_id, point_id)
            target = self._value(current_value)
            updated = self.investments.update_value_point(
                investment_id,
                point_id,
                target,
            )
            if index == len(history) - 1:
                current = self.accounts.account_balance(investment.account_id)
                difference = target - current
                if difference:
                    self.transactions.add_adjustment(
                        investment.account_id,
                        difference,
                        updated.date,
                        f"Correct {investment.name} market value",
                        investment_id=investment.id,
                    )
            return updated

    def delete_value_update(self, investment_id: str, point_id: str) -> None:
        with unit_of_work(self.db):
            investment = self._investment(investment_id)
            history, index = self._history_position(investment_id, point_id)
            point = history[index]
            if index == len(history) - 1 and len(history) > 1:
                previous = history[index - 1]
                current = self.accounts.account_balance(investment.account_id)
                difference = previous.value - current
                if difference:
                    self.transactions.add_adjustment(
                        investment.account_id,
                        difference,
                        point.date,
                        f"Remove {investment.name} value log",
                        investment_id=investment.id,
                    )
            self.investments.delete_value_point(investment_id, point_id)

    def clear_value_logs(self, investment_id: str) -> int:
        with unit_of_work(self.db):
            self._investment(investment_id)
            return self.investments.delete_all_value_points(investment_id)

    def portfolio_history(self) -> list[InvestmentValuePoint]:
        active_ids = {
            investment.id
            for investment in self.investments.list()
            if investment.id is not None
        }
        latest_values: dict[str, Decimal] = {}
        latest_contributions: dict[str, Decimal] = {}
        portfolio: list[InvestmentValuePoint] = []
        for point in self.investments.list_value_history():
            if point.investment_id not in active_ids:
                continue
            latest_values[point.investment_id] = point.value
            latest_contributions[point.investment_id] = point.contributed
            portfolio.append(
                InvestmentValuePoint(
                    id=f"portfolio-{point.id}",
                    investment_id="portfolio",
                    date=point.date,
                    value=sum(latest_values.values(), Decimal("0")),
                    contributed=sum(latest_contributions.values(), Decimal("0")),
                    recorded_at=point.recorded_at,
                )
            )
        return portfolio

    def performance_history(
        self,
        investment_id: str | None = None,
        interval: str = "monthly",
        reference_date: Date | None = None,
    ) -> list[InvestmentPerformancePoint]:
        if interval not in self.PERFORMANCE_INTERVALS:
            raise ValueError("Performance interval is not supported")
        if investment_id is not None:
            investment = self._investment(investment_id)
            active_ids = {investment.id}
        else:
            active_ids = {
                investment.id
                for investment in self.investments.list()
                if investment.id is not None
            }

        value_points = [
            point
            for point in self.investments.list_value_history(investment_id)
            if point.investment_id in active_ids
        ]
        if not value_points:
            return []

        updates: list[InvestmentPerformancePoint] = []
        latest_values: dict[str, Decimal] = {}
        latest_contributions: dict[str, Decimal] = {}
        for point in value_points:
            latest_values[point.investment_id] = point.value
            latest_contributions[point.investment_id] = point.contributed
            updates.append(
                InvestmentPerformancePoint(
                    date=point.date,
                    contributed=sum(latest_contributions.values(), Decimal("0")),
                    current_value=sum(latest_values.values(), Decimal("0")),
                )
            )
        if interval == "updates":
            return updates

        event_dates = [Date.fromisoformat(point.date) for point in updates]
        horizon = max(reference_date or Date.today(), max(event_dates))
        period_start = min(event_dates).replace(day=1)
        update_index = 0
        latest_update = updates[0]
        series: list[InvestmentPerformancePoint] = []

        while period_start <= horizon:
            next_period = self._next_month(period_start)
            cutoff = min(next_period - timedelta(days=1), horizon)
            while update_index < len(updates):
                point = updates[update_index]
                if Date.fromisoformat(point.date) > cutoff:
                    break
                latest_update = point
                update_index += 1
            series.append(
                InvestmentPerformancePoint(
                    date=cutoff.isoformat(),
                    contributed=latest_update.contributed,
                    current_value=latest_update.current_value,
                )
            )
            period_start = next_period
        return series

    def summary(self) -> dict[str, Decimal | int]:
        snapshots = self.list_snapshots()
        contributed = sum((item.contributed for item in snapshots), Decimal("0"))
        current_value = sum((item.current_value for item in snapshots), Decimal("0"))
        gain_loss = current_value - contributed
        return_percent = (
            (gain_loss / contributed * Decimal("100")).quantize(Decimal("0.01"))
            if contributed
            else Decimal("0")
        )
        return {
            "count": len(snapshots),
            "contributed": contributed,
            "current_value": current_value,
            "gain_loss": gain_loss,
            "return_percent": return_percent,
        }

    def _snapshot(self, investment_id: str) -> InvestmentSnapshot:
        snapshot = self.get_snapshot(investment_id)
        if not snapshot:
            raise ValueError("Investment not found")
        return snapshot

    @staticmethod
    def _make_snapshot(
        investment: Investment,
        contributed: Decimal,
        current_value: Decimal,
    ) -> InvestmentSnapshot:
        gain_loss = current_value - contributed
        return_percent = (
            (gain_loss / contributed * Decimal("100")).quantize(Decimal("0.01"))
            if contributed
            else Decimal("0")
        )
        return InvestmentSnapshot(
            investment=investment,
            contributed=contributed,
            current_value=current_value,
            gain_loss=gain_loss,
            return_percent=return_percent,
        )

    def _investment(self, investment_id: str) -> Investment:
        investment = self.investments.get(investment_id)
        if not investment or not investment.is_active:
            raise ValueError("Investment not found")
        return investment

    def _require_current_timeline_date(
        self,
        investment_id: str,
        value_date: str,
    ) -> None:
        history = self.investments.list_value_history(investment_id)
        if history and value_date < history[-1].date:
            raise ValueError(
                "Date cannot be earlier than the latest recorded investment value "
                f"({history[-1].date}). Delete or clear later logs first"
            )

    def _history_position(
        self,
        investment_id: str,
        point_id: str,
    ) -> tuple[list[InvestmentValuePoint], int]:
        history = self.investments.list_value_history(investment_id)
        for index, point in enumerate(history):
            if point.id == point_id:
                return history, index
        raise ValueError("Value log not found")

    @staticmethod
    def _investment_date(value: str) -> str:
        validated = require_iso_date(value)
        if Date.fromisoformat(validated) > Date.today():
            raise ValueError("Investment dates cannot be in the future")
        return validated

    def _funding_account(self, account_id: str):
        account = self.account_repository.get(account_id)
        if not account or not account.is_active:
            raise ValueError("Funding account is unavailable")
        if account.type not in self.FUNDING_ACCOUNT_TYPES:
            raise ValueError("Choose a bank, current, savings, cash, or wallet account")
        return account

    def _kind(self, value: str) -> str:
        cleaned = require_text(value, "Investment type")
        if cleaned not in self.KINDS:
            raise ValueError("Investment type is not supported")
        return cleaned

    @staticmethod
    def _value(value: object, fallback: Decimal | None = None) -> Decimal:
        if (value is None or not str(value).strip()) and fallback is not None:
            return fallback
        amount = to_decimal(value)
        if amount < 0:
            raise ValueError("Current value cannot be negative")
        return amount

    @staticmethod
    def _symbol(value: str | None) -> str | None:
        cleaned = (value or "").strip().upper()
        return cleaned or None

    @staticmethod
    def _notes(value: str | None) -> str | None:
        cleaned = (value or "").strip()
        return cleaned or None

    @staticmethod
    def _next_month(value: Date) -> Date:
        if value.month == 12:
            return Date(value.year + 1, 1, 1)
        return Date(value.year, value.month + 1, 1)
