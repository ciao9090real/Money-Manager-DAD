from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


CENT = Decimal("0.01")


def to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value or "0")).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ValueError("Enter a valid amount")


def require_positive(value: object) -> Decimal:
    amount = to_decimal(value)
    if amount <= 0:
        raise ValueError("Amount must be positive")
    return amount


def format_money(value: object, currency: str = "EUR") -> str:
    amount = to_decimal(value)
    symbol = "€" if currency == "EUR" else f"{currency} "
    return f"{symbol}{amount:,.2f}"

