import asyncio
from io import BytesIO
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi import UploadFile
from starlette.datastructures import Headers
from starlette.requests import Request

from app.api import auth
from app.api.crud import add_calendar_months, recurring_occurrences
from app.main import app
from app.models import Account, Card
from app.core.security import create_password_reset_token, read_password_reset_token
from app.services import market
from app.services.notifications import reminder_is_due


def test_card_relationship_points_to_account():
    assert Card.account.property.mapper.class_ is Account
    assert Account.cards.property.mapper.class_ is Card


def test_reminder_is_due_inside_notification_window():
    payment = SimpleNamespace(
        next_due_date=date(2026, 7, 7),
        notify_days_before=3,
        is_active=True,
        last_notified_at=None,
    )
    assert reminder_is_due(payment, today=date(2026, 7, 4))


def test_reminder_is_only_sent_once_per_day():
    payment = SimpleNamespace(
        next_due_date=date(2026, 7, 5),
        notify_days_before=3,
        is_active=True,
        last_notified_at=datetime(2026, 7, 4, 8, tzinfo=timezone.utc),
    )
    assert not reminder_is_due(payment, today=date(2026, 7, 4))


def test_calendar_month_addition_keeps_month_end_valid():
    assert add_calendar_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_calendar_months(date(2026, 1, 31), 2) == date(2026, 3, 31)


def test_monthly_forecast_occurrences_keep_original_due_day():
    assert recurring_occurrences(
        date(2026, 1, 31),
        "monthly",
        date(2026, 2, 1),
        date(2026, 4, 30),
    ) == [date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]


def test_weekly_forecast_skips_past_occurrences():
    assert recurring_occurrences(
        date(2026, 7, 1),
        "weekly",
        date(2026, 7, 10),
        date(2026, 7, 20),
    ) == [date(2026, 7, 15)]


def test_finnhub_quote_is_normalized(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"c": 203.42, "d": 1.25, "dp": 0.62, "h": 204, "l": 200, "o": 201, "pc": 202.17, "t": 1}

    monkeypatch.setattr(market.settings, "finnhub_api_key", "test-key")
    monkeypatch.setattr(market.httpx, "get", lambda *args, **kwargs: Response())
    quote = market.get_quote(" aapl ")
    assert quote["symbol"] == "AAPL"
    assert quote["current"] == Decimal("203.42")


def test_same_currency_does_not_call_forex_api(monkeypatch):
    monkeypatch.setattr(market.settings, "finnhub_api_key", "")
    assert market.get_exchange_rate("EUR", "EUR") == Decimal("1")


def test_password_reset_token_round_trip():
    token = create_password_reset_token(42)
    assert read_password_reset_token(token) == 42


def test_profile_photo_upload_uses_configured_directory(tmp_path, monkeypatch):
    class Database:
        def commit(self):
            return None

        def refresh(self, item):
            return None

    monkeypatch.setattr(auth.app_settings, "upload_dir", str(tmp_path))
    request = Request({
        "type": "http",
        "method": "POST",
        "path": "/settings/profile-photo",
        "raw_path": b"/settings/profile-photo",
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": [],
        "client": ("test", 123),
        "server": ("testserver", 80),
        "app": app,
        "router": app.router,
    })
    file = UploadFile(
        file=BytesIO(b"\x89PNG\r\n\x1a\nprofile"),
        filename="avatar.png",
        headers=Headers({"content-type": "image/png"}),
    )
    user = SimpleNamespace(id=7, settings=SimpleNamespace(profile_photo_url=None))
    result = asyncio.run(auth.update_profile_photo(request, file, Database(), user))
    assert result.profile_photo_url.endswith(".png")
    assert len(list(tmp_path.glob("profile-7-*.png"))) == 1
