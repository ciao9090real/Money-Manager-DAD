from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Transaction:
    id: str | None
    date: str
    type: str
    account_id: str
    amount: Decimal
    payment_method_id: str | None = None
    description: str = ""
    category_id: str | None = None
    transfer_group_id: str | None = None
    notes: str | None = None
    status: str = "cleared"
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None
    revision: int = 1
