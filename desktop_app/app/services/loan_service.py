from __future__ import annotations

import calendar
import sqlite3
from datetime import date as Date
from decimal import Decimal, ROUND_HALF_UP, localcontext

from app.core.database import unit_of_work
from app.models.amortization import AmortizationEntry, PayoffPlan
from app.models.loan import Loan, LoanPayment, LoanSnapshot
from app.repositories.account_repository import AccountRepository
from app.repositories.loan_repository import LoanRepository
from app.services.transaction_service import TransactionService
from app.utils.dates import require_iso_date
from app.utils.money import CENT, require_positive, to_decimal
from app.utils.validators import require_text


class LoanService:
    CALCULATION_MODE = "principal_only"
    MAX_AMORTIZATION_PERIODS = 1200
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
        """Return principal positions; reference interest is not accrued."""
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

    def amortization_schedule(
        self,
        loan_id: str,
        monthly_payment: object | None = None,
        reference_date: Date | None = None,
    ) -> list[AmortizationEntry]:
        """Build a prospective monthly schedule from principal outstanding."""

        snapshot = self._snapshot(loan_id)
        if snapshot.outstanding <= 0 or snapshot.loan.status == "settled":
            return []

        reference = reference_date or Date.today()
        first_payment = self._first_payment_date(snapshot.loan, reference)
        derived_dates: list[Date] | None = None
        if monthly_payment is None or (
            isinstance(monthly_payment, str) and not monthly_payment.strip()
        ):
            derived_dates = self._dates_through_due_date(
                snapshot.loan,
                first_payment,
                reference,
            )
            payment = self._amortizing_payment(
                snapshot.outstanding,
                snapshot.loan.interest_rate,
                len(derived_dates),
            )
        else:
            payment = require_positive(monthly_payment)

        monthly_rate = snapshot.loan.interest_rate / Decimal("1200")
        first_interest = self._interest(snapshot.outstanding, monthly_rate)
        if payment <= first_interest:
            raise ValueError(
                "Monthly payment must be greater than the monthly interest"
            )

        balance = snapshot.outstanding
        anchor_day = Date.fromisoformat(snapshot.loan.start_date).day
        entries: list[AmortizationEntry] = []
        for period in range(1, self.MAX_AMORTIZATION_PERIODS + 1):
            if derived_dates is not None and period <= len(derived_dates):
                payment_date = derived_dates[period - 1]
            else:
                payment_date = self._add_months(
                    first_payment,
                    period - 1,
                    anchor_day,
                )

            interest = self._interest(balance, monthly_rate)
            settle_on_this_period = (
                balance + interest <= payment
                or derived_dates is not None and period == len(derived_dates)
            )
            if settle_on_this_period:
                actual_payment = (balance + interest).quantize(
                    CENT,
                    rounding=ROUND_HALF_UP,
                )
                principal = balance
                remaining = Decimal("0.00")
            else:
                actual_payment = payment
                principal = (actual_payment - interest).quantize(
                    CENT,
                    rounding=ROUND_HALF_UP,
                )
                if principal <= 0:
                    raise ValueError(
                        "Monthly payment is too small to reduce the loan balance"
                    )
                remaining = (balance - principal).quantize(
                    CENT,
                    rounding=ROUND_HALF_UP,
                )

            entries.append(
                AmortizationEntry(
                    period=period,
                    date=payment_date.isoformat(),
                    payment=actual_payment,
                    principal_portion=principal,
                    interest_portion=interest,
                    remaining_balance=remaining,
                )
            )
            if remaining == 0:
                return entries
            balance = remaining

        raise ValueError(
            "Monthly payment does not repay the loan within 100 years"
        )

    def payoff_comparison(
        self,
        loan_id: str,
        extra_monthly_payment: object,
        monthly_payment: object | None = None,
        reference_date: Date | None = None,
    ) -> dict[str, PayoffPlan | Decimal | int]:
        extra = to_decimal(extra_monthly_payment)
        if extra < 0:
            raise ValueError("Extra monthly payment cannot be negative")

        baseline_entries = self.amortization_schedule(
            loan_id,
            monthly_payment,
            reference_date,
        )
        if not baseline_entries:
            raise ValueError("This loan is already settled")
        regular_payment = (
            require_positive(monthly_payment)
            if monthly_payment is not None
            and not (isinstance(monthly_payment, str) and not monthly_payment.strip())
            else baseline_entries[0].payment
        )
        extra_entries = self.amortization_schedule(
            loan_id,
            regular_payment + extra,
            reference_date,
        )
        without_extra = self._payoff_plan(loan_id, "minimum", baseline_entries)
        with_extra = self._payoff_plan(loan_id, "custom", extra_entries)
        periods_saved = len(baseline_entries) - len(extra_entries)
        return {
            "without_extra": without_extra,
            "with_extra": with_extra,
            "interest_saved": (
                without_extra.total_interest_paid - with_extra.total_interest_paid
            ).quantize(CENT, rounding=ROUND_HALF_UP),
            "periods_saved": periods_saved,
            "months_saved": periods_saved,
        }

    def multi_loan_strategy(
        self,
        strategy: str,
        extra_budget: object,
        reference_date: Date | None = None,
    ) -> list[PayoffPlan]:
        cleaned_strategy = (strategy or "").strip().lower()
        if cleaned_strategy not in {"snowball", "avalanche"}:
            raise ValueError("Strategy must be snowball or avalanche")
        extra = to_decimal(extra_budget)
        if extra < 0:
            raise ValueError("Extra monthly budget cannot be negative")

        snapshots = self.list_snapshots(direction="borrowed", status="active")
        if cleaned_strategy == "snowball":
            snapshots.sort(
                key=lambda item: (
                    item.outstanding,
                    -item.loan.interest_rate,
                    item.loan.name.lower(),
                    item.loan.id or "",
                )
            )
        else:
            snapshots.sort(
                key=lambda item: (
                    -item.loan.interest_rate,
                    item.outstanding,
                    item.loan.name.lower(),
                    item.loan.id or "",
                )
            )
        if not snapshots:
            return []

        reference = reference_date or Date.today()
        states: list[dict] = []
        for snapshot in snapshots:
            first_payment = self._first_payment_date(snapshot.loan, reference)
            dates = self._dates_through_due_date(
                snapshot.loan,
                first_payment,
                reference,
            )
            minimum = self._amortizing_payment(
                snapshot.outstanding,
                snapshot.loan.interest_rate,
                len(dates),
            )
            states.append(
                {
                    "snapshot": snapshot,
                    "balance": snapshot.outstanding,
                    "minimum": minimum,
                    "monthly_rate": snapshot.loan.interest_rate / Decimal("1200"),
                    "first_payment": first_payment,
                    "anchor_day": Date.fromisoformat(snapshot.loan.start_date).day,
                    "entries": [],
                }
            )

        for period in range(1, self.MAX_AMORTIZATION_PERIODS + 1):
            if all(state["balance"] == 0 for state in states):
                break

            extra_pool = extra + sum(
                (
                    state["minimum"]
                    for state in states
                    if state["balance"] == 0
                ),
                Decimal("0"),
            )
            period_entries: dict[int, AmortizationEntry] = {}

            for index, state in enumerate(states):
                balance = state["balance"]
                if balance == 0:
                    continue
                interest = self._interest(balance, state["monthly_rate"])
                scheduled = state["minimum"]
                actual = min(scheduled, balance + interest).quantize(
                    CENT,
                    rounding=ROUND_HALF_UP,
                )
                principal = (actual - interest).quantize(
                    CENT,
                    rounding=ROUND_HALF_UP,
                )
                if principal <= 0:
                    loan = state["snapshot"].loan
                    raise ValueError(
                        f"The derived monthly payment for '{loan.name}' does not reduce its balance"
                    )
                remaining = max(balance - principal, Decimal("0")).quantize(
                    CENT,
                    rounding=ROUND_HALF_UP,
                )
                extra_pool += scheduled - actual
                payment_date = self._add_months(
                    state["first_payment"],
                    period - 1,
                    state["anchor_day"],
                )
                period_entries[index] = AmortizationEntry(
                    period=period,
                    date=payment_date.isoformat(),
                    payment=actual,
                    principal_portion=principal,
                    interest_portion=interest,
                    remaining_balance=remaining,
                )
                state["balance"] = remaining

            for index, state in enumerate(states):
                if extra_pool <= 0:
                    break
                entry = period_entries.get(index)
                if entry is None or entry.remaining_balance <= 0:
                    continue
                applied = min(extra_pool, entry.remaining_balance).quantize(
                    CENT,
                    rounding=ROUND_HALF_UP,
                )
                remaining = (entry.remaining_balance - applied).quantize(
                    CENT,
                    rounding=ROUND_HALF_UP,
                )
                period_entries[index] = AmortizationEntry(
                    period=entry.period,
                    date=entry.date,
                    payment=entry.payment + applied,
                    principal_portion=entry.principal_portion + applied,
                    interest_portion=entry.interest_portion,
                    remaining_balance=remaining,
                )
                state["balance"] = remaining
                extra_pool -= applied

            for index, entry in period_entries.items():
                states[index]["entries"].append(entry)
        else:
            raise ValueError("The payoff strategy does not settle every loan within 100 years")

        return [
            self._payoff_plan(
                state["snapshot"].loan.id,
                cleaned_strategy,
                state["entries"],
            )
            for state in states
        ]

    def _snapshot(self, loan_id: str) -> LoanSnapshot:
        snapshot = self.get_snapshot(loan_id)
        if not snapshot:
            raise ValueError("Loan not found")
        return snapshot

    @staticmethod
    def _payoff_plan(
        loan_id: str | None,
        strategy: str,
        entries: list[AmortizationEntry],
    ) -> PayoffPlan:
        if loan_id is None or not entries:
            raise ValueError("A payoff plan requires an active loan")
        return PayoffPlan(
            loan_id=loan_id,
            strategy=strategy,
            entries=entries,
            payoff_date=entries[-1].date,
            total_interest_paid=sum(
                (entry.interest_portion for entry in entries),
                Decimal("0"),
            ).quantize(CENT, rounding=ROUND_HALF_UP),
        )

    def _first_payment_date(self, loan: Loan, reference: Date) -> Date:
        anchor_day = Date.fromisoformat(loan.start_date).day
        baseline = max(reference, Date.fromisoformat(loan.start_date))
        payments = self.loans.list_payments(str(loan.id)) if loan.id else []
        if payments:
            baseline = max(
                baseline,
                max(Date.fromisoformat(payment.date) for payment in payments),
            )
        candidate = Date(
            baseline.year,
            baseline.month,
            min(anchor_day, calendar.monthrange(baseline.year, baseline.month)[1]),
        )
        if candidate <= baseline:
            candidate = self._add_months(candidate, 1, anchor_day)
        return candidate

    def _dates_through_due_date(
        self,
        loan: Loan,
        first_payment: Date,
        reference: Date,
    ) -> list[Date]:
        if not loan.due_date:
            raise ValueError(
                f"A due date is required to derive a monthly payment for '{loan.name}'"
            )
        due = Date.fromisoformat(loan.due_date)
        if due <= reference:
            raise ValueError("Loan due date must be after the payoff-plan date")

        dates: list[Date] = []
        anchor_day = Date.fromisoformat(loan.start_date).day
        payment_date = first_payment
        while payment_date < due:
            dates.append(payment_date)
            if len(dates) >= self.MAX_AMORTIZATION_PERIODS:
                raise ValueError("Loan due date is more than 100 years away")
            payment_date = self._add_months(payment_date, 1, anchor_day)
        dates.append(due)
        return dates

    @staticmethod
    def _amortizing_payment(
        balance: Decimal,
        annual_rate: Decimal,
        periods: int,
    ) -> Decimal:
        if periods < 1:
            raise ValueError("At least one payment period is required")
        monthly_rate = annual_rate / Decimal("1200")
        with localcontext() as context:
            context.prec = 40
            if monthly_rate == 0:
                payment = balance / Decimal(periods)
            else:
                payment = (
                    balance
                    * monthly_rate
                    / (Decimal("1") - (Decimal("1") + monthly_rate) ** -periods)
                )
        return payment.quantize(CENT, rounding=ROUND_HALF_UP)

    @staticmethod
    def _interest(balance: Decimal, monthly_rate: Decimal) -> Decimal:
        return (balance * monthly_rate).quantize(CENT, rounding=ROUND_HALF_UP)

    @staticmethod
    def _add_months(value: Date, months: int, anchor_day: int) -> Date:
        month_index = value.year * 12 + value.month - 1 + months
        year, zero_based_month = divmod(month_index, 12)
        month = zero_based_month + 1
        day = min(anchor_day, calendar.monthrange(year, month)[1])
        return Date(year, month, day)

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
