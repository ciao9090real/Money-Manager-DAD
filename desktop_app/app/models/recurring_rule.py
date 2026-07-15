from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class RecurringRule:
    id: str | None
    name: str
    kind: str
    amount_mode: str
    account_id: str
    frequency: str
    start_date: str
    next_due_date: str
    amount: Decimal | None = None
    category_id: str | None = None
    payment_method_id: str | None = None
    end_date: str | None = None
    reminder_days: int = 3
    status: str = "active"
    last_recorded_date: str | None = None
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None
    revision: int = 1
