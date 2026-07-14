from __future__ import annotations

from datetime import date, datetime


def today_iso() -> str:
    return date.today().isoformat()


def require_iso_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError("Date is required and must be YYYY-MM-DD")


def format_display_date(value: str) -> str:
    try:
        return date.fromisoformat(value).strftime("%d %b %Y")
    except ValueError:
        return value


def month_prefix(value: date | None = None) -> str:
    current = value or date.today()
    return current.strftime("%Y-%m")


def month_bounds(value: date | None = None) -> tuple[str, str]:
    current = value or date.today()
    start = current.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.isoformat(), end.isoformat()


def timestamp_for_filename() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")
