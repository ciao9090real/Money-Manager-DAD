from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Account:
    id: str | None
    name: str
    type: str
    parent_id: str | None = None
    opening_balance: Decimal = Decimal("0")
    is_active: bool = True
    display_order: int = 0
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None
    revision: int = 1
