from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class NetWorthPoint:
    date: str
    assets: Decimal
    liabilities: Decimal
    net_worth: Decimal
    estimated: bool = False
