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
    symbol = "\u20ac" if currency == "EUR" else f"{currency} "
    prefix = "-" if amount < 0 else ""
    return f"{prefix}{symbol}{abs(amount):,.2f}"
