from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PaymentMethod:
    id: int | None
    name: str
    account_id: int
    type: str
    is_active: bool = True

