from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Transaction:
    id: int | None
    date: str
    type: str
    account_id: int
    amount: Decimal
    payment_method_id: int | None = None
    description: str = ""
    category_id: int | None = None
    transfer_group_id: str | None = None
    notes: str | None = None

