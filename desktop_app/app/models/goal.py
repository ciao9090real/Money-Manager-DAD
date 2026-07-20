from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class SavingsGoal:
    id: str | None
    name: str
    target_amount: Decimal
    target_date: str | None = None
    linked_account_id: str | None = None
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None
    revision: int = 1


@dataclass(frozen=True)
class GoalProgress:
    goal: SavingsGoal
    current_amount: Decimal
    percent_complete: Decimal
    on_track: bool | None
    required_monthly_contribution: Decimal | None
