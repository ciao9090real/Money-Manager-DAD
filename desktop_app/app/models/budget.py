from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Budget:
    id: str | None
    category_id: str
    period: str
    amount: Decimal
    rollover: bool = False
    start_date: str = ""
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None
    revision: int = 1


@dataclass(frozen=True)
class BudgetStatus:
    budget: Budget
    period_label: str
    limit: Decimal
    spent: Decimal
    remaining: Decimal
    percent_used: Decimal
    rolled_over_from_prior: Decimal
