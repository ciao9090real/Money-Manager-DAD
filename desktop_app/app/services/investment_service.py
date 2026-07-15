from __future__ import annotations

import sqlite3
from decimal import Decimal

from app.core.database import unit_of_work
from app.models.investment import Investment, InvestmentSnapshot
from app.repositories.account_repository import AccountRepository
from app.repositories.investment_repository import InvestmentRepository
from app.services.account_service import AccountService
from app.services.transaction_service import TransactionService
from app.utils.dates import require_iso_date
from app.utils.money import require_positive, to_decimal
from app.utils.validators import require_text


class InvestmentService:
    KINDS = {"fund", "etf", "stock", "bond", "crypto", "other"}
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
            transaction_date = require_iso_date(date)
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
            self.transactions.add_transfer(
                source_account_id,
                investment.account_id,
                require_positive(amount),
                require_iso_date(date),
                f"Add funds to {investment.name}",
                investment_id=investment.id,
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
            current = self.accounts.account_balance(investment.account_id)
            difference = target - current
            if difference:
                self.transactions.add_adjustment(
                    investment.account_id,
                    difference,
                    require_iso_date(date),
                    f"Update {investment.name} market value",
                    investment_id=investment.id,
                )
            return self._snapshot(investment_id)

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
