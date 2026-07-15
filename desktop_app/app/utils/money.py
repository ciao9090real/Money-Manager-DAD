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


def decimal_to_cents(value: object) -> int:
    """Convert a display amount to the exact integer stored by SQLite."""
    return int(to_decimal(value) * 100)


def cents_to_decimal(value: object) -> Decimal:
    """Convert an integer database amount to the UI/service Decimal contract."""
    try:
        return (Decimal(int(value or 0)) / 100).quantize(CENT)
    except (TypeError, ValueError, InvalidOperation):
        raise ValueError("Stored amount is not a valid integer-cent value")


def format_money(value: object, currency: str = "EUR") -> str:
    amount = to_decimal(value)
    symbol = "\u20ac" if currency == "EUR" else f"{currency} "
    prefix = "-" if amount < 0 else ""
    return f"{prefix}{symbol}{abs(amount):,.2f}"
