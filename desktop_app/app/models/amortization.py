from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AmortizationEntry:
    period: int
    date: str
    payment: Decimal
    principal_portion: Decimal
    interest_portion: Decimal
    remaining_balance: Decimal


@dataclass(frozen=True)
class PayoffPlan:
    loan_id: str
    strategy: str
    entries: list[AmortizationEntry]
    payoff_date: str
    total_interest_paid: Decimal
