from __future__ import annotations

import sqlite3
from decimal import Decimal

from app.core.database import unit_of_work
from app.models.loan import Loan, LoanPayment, LoanSnapshot
from app.repositories.account_repository import AccountRepository
from app.repositories.loan_repository import LoanRepository
from app.services.transaction_service import TransactionService
from app.utils.dates import require_iso_date
from app.utils.money import require_positive, to_decimal
from app.utils.validators import require_text


class LoanService:
    DIRECTIONS = {"borrowed", "lent"}
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
        self.loans = LoanRepository(db)
        self.accounts = AccountRepository(db)
        self.transactions = TransactionService(db)

    def create_loan(
        self,
        direction: str,
        name: str,
        counterparty: str,
        account_id: str,
        principal: object,
        start_date: str,
        due_date: str | None = None,
        interest_rate: object = 0,
        notes: str | None = None,
    ) -> LoanSnapshot:
        with unit_of_work(self.db):
            cleaned_direction = self._direction(direction)
            cleaned_name = require_text(name, "Loan name")
            cleaned_counterparty = require_text(counterparty, "Counterparty")
            self._funding_account(account_id)
            amount = require_positive(principal)
            started = require_iso_date(start_date)
            due = self._due_date(due_date, started)
            loan = self.loans.create(
                Loan(
                    id=None,
                    direction=cleaned_direction,
                    name=cleaned_name,
                    counterparty=cleaned_counterparty,
                    principal=amount,
                    account_id=account_id,
                    start_date=started,
                    due_date=due,
                    interest_rate=self._interest_rate(interest_rate),
                    notes=self._notes(notes),
                )
            )
            assert loan.id is not None
            transaction_amount = amount if cleaned_direction == "borrowed" else -amount
            description = (
                f"Loan received: {cleaned_name}"
                if cleaned_direction == "borrowed"
                else f"Money lent: {cleaned_name}"
            )
            self.transactions.add_adjustment(
                account_id,
                transaction_amount,
                started,
                description,
                notes,
                loan_id=loan.id,
            )
            return self._snapshot(loan.id)

    def update_loan(
        self,
        loan_id: str,
        name: str,
        counterparty: str,
        due_date: str | None = None,
        interest_rate: object = 0,
        notes: str | None = None,
    ) -> LoanSnapshot:
        with unit_of_work(self.db):
            loan = self._loan(loan_id)
            loan.name = require_text(name, "Loan name")
            loan.counterparty = require_text(counterparty, "Counterparty")
            loan.due_date = self._due_date(due_date, loan.start_date)
            loan.interest_rate = self._interest_rate(interest_rate)
            loan.notes = self._notes(notes)
            self.loans.update(loan)
            return self._snapshot(loan_id)

    def record_payment(
        self,
        loan_id: str,
        account_id: str,
        amount: object,
        date: str,
        notes: str | None = None,
    ) -> LoanSnapshot:
        with unit_of_work(self.db):
            snapshot = self._snapshot(loan_id)
            loan = snapshot.loan
            if loan.status != "active" or snapshot.outstanding <= 0:
                raise ValueError("This loan is already settled")
            self._funding_account(account_id)
            payment_amount = require_positive(amount)
            if payment_amount > snapshot.outstanding:
                raise ValueError("Payment cannot exceed the outstanding balance")
            payment_date = require_iso_date(date)
            if payment_date < loan.start_date:
                raise ValueError("Payment date cannot be before the loan start date")
            transaction_amount = -payment_amount if loan.direction == "borrowed" else payment_amount
            description = (
                f"Loan repayment: {loan.name}"
                if loan.direction == "borrowed"
                else f"Loan repayment received: {loan.name}"
            )
            transaction = self.transactions.add_adjustment(
                account_id,
                transaction_amount,
                payment_date,
                description,
                notes,
                loan_id=loan.id,
            )
            assert transaction.id is not None and loan.id is not None
            self.loans.create_payment(
                LoanPayment(
                    id=None,
                    loan_id=loan.id,
                    account_id=account_id,
                    transaction_id=transaction.id,
                    amount=payment_amount,
                    date=payment_date,
                    notes=self._notes(notes),
                )
            )
            if payment_amount == snapshot.outstanding:
                loan.status = "settled"
                self.loans.update(loan)
            return self._snapshot(loan_id)

    def list_snapshots(
        self,
        direction: str | None = None,
        status: str | None = None,
    ) -> list[LoanSnapshot]:
        cleaned_direction = self._direction(direction) if direction else None
        rows = self.loans.list_with_balances(
            direction=cleaned_direction,
            include_settled=status != "active",
        )
        snapshots = [LoanSnapshot(loan, paid, outstanding) for loan, paid, outstanding in rows]
        if status == "settled":
            snapshots = [item for item in snapshots if item.loan.status == "settled"]
        return snapshots

    def get_snapshot(self, loan_id: str) -> LoanSnapshot | None:
        return next(
            (item for item in self.list_snapshots() if item.loan.id == loan_id),
            None,
        )

    def list_payments(self, loan_id: str) -> list[LoanPayment]:
        self._loan(loan_id)
        return self.loans.list_payments(loan_id)

    def summary(self) -> dict[str, Decimal | int]:
        active = self.list_snapshots(status="active")
        borrowed = sum(
            (item.outstanding for item in active if item.loan.direction == "borrowed"),
            Decimal("0"),
        )
        lent = sum(
            (item.outstanding for item in active if item.loan.direction == "lent"),
            Decimal("0"),
        )
        return {
            "active_count": len(active),
            "borrowed": borrowed,
            "lent": lent,
            "net_position": lent - borrowed,
        }

    def _snapshot(self, loan_id: str) -> LoanSnapshot:
        snapshot = self.get_snapshot(loan_id)
        if not snapshot:
            raise ValueError("Loan not found")
        return snapshot

    def _loan(self, loan_id: str) -> Loan:
        loan = self.loans.get(loan_id)
        if not loan:
            raise ValueError("Loan not found")
        return loan

    def _funding_account(self, account_id: str):
        account = self.accounts.get(account_id)
        if not account or not account.is_active:
            raise ValueError("Account is unavailable")
        if account.type not in self.FUNDING_ACCOUNT_TYPES:
            raise ValueError("Choose a bank, current, savings, cash, or wallet account")
        return account

    def _direction(self, value: str) -> str:
        cleaned = (value or "").strip().lower()
        if cleaned not in self.DIRECTIONS:
            raise ValueError("Loan direction must be borrowed or lent")
        return cleaned

    @staticmethod
    def _interest_rate(value: object) -> Decimal:
        rate = to_decimal(value)
        if rate < 0 or rate > 100:
            raise ValueError("Interest rate must be between 0% and 100%")
        return rate

    @staticmethod
    def _due_date(value: str | None, start_date: str) -> str | None:
        if value is None or not str(value).strip():
            return None
        due = require_iso_date(value)
        if due < start_date:
            raise ValueError("Due date cannot be before the start date")
        return due

    @staticmethod
    def _notes(value: str | None) -> str | None:
        cleaned = (value or "").strip()
        return cleaned or None
