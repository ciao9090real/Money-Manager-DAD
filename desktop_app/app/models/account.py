from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Account:
    id: int | None
    name: str
    type: str
    parent_id: int | None = None
    opening_balance: Decimal = Decimal("0")
    is_active: bool = True
    display_order: int = 0

