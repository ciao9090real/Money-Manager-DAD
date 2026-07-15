from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Investment:
    id: str | None
    name: str
    kind: str
    account_id: str
    symbol: str | None = None
    notes: str | None = None
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None
    revision: int = 1


@dataclass(frozen=True)
class InvestmentSnapshot:
    investment: Investment
    contributed: Decimal
    current_value: Decimal
    gain_loss: Decimal
    return_percent: Decimal
