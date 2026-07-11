from __future__ import annotations

from datetime import date, datetime


def today_iso() -> str:
    return date.today().isoformat()


def require_iso_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError("Date is required and must be YYYY-MM-DD")


def month_prefix(value: date | None = None) -> str:
    current = value or date.today()
    return current.strftime("%Y-%m")


def timestamp_for_filename() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

