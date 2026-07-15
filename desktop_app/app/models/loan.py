from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Loan:
    id: str | None
    direction: str
    name: str
    counterparty: str
    principal: Decimal
    account_id: str
    start_date: str
    due_date: str | None = None
    interest_rate: Decimal = Decimal("0")
    notes: str | None = None
    status: str = "active"
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None
    revision: int = 1


@dataclass
class LoanPayment:
    id: str | None
    loan_id: str
    account_id: str
    transaction_id: str
    amount: Decimal
    date: str
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None
    revision: int = 1


@dataclass(frozen=True)
class LoanSnapshot:
    loan: Loan
    paid: Decimal
    outstanding: Decimal
