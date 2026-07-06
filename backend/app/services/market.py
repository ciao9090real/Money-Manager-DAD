from decimal import Decimal

import httpx
from fastapi import HTTPException

from app.core.config import settings


FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"
FINNHUB_FOREX_URL = "https://finnhub.io/api/v1/forex/rates"
FRANKFURTER_FOREX_URL = "https://api.frankfurter.dev/v1/latest"


def get_quote(symbol: str) -> dict[str, Decimal | str | int]:
    if not settings.finnhub_api_key:
        raise HTTPException(status_code=503, detail="Finnhub is not configured")
    clean_symbol = symbol.strip().upper()
    if not clean_symbol:
        raise HTTPException(status_code=422, detail="A stock symbol is required")
    data = {}
    try:
        response = httpx.get(
            FINNHUB_QUOTE_URL,
            params={"symbol": clean_symbol, "token": settings.finnhub_api_key},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Could not reach Finnhub") from exc
    current = Decimal(str(data.get("c") or 0))
    if current <= 0:
        raise HTTPException(status_code=404, detail=f"No live quote found for {clean_symbol}")
    return {
        "symbol": clean_symbol,
        "current": current,
        "change": Decimal(str(data.get("d") or 0)),
        "percent_change": Decimal(str(data.get("dp") or 0)),
        "high": Decimal(str(data.get("h") or 0)),
        "low": Decimal(str(data.get("l") or 0)),
        "open": Decimal(str(data.get("o") or 0)),
        "previous_close": Decimal(str(data.get("pc") or 0)),
        "timestamp": int(data.get("t") or 0),
    }


def get_exchange_rate(base_currency: str, target_currency: str) -> Decimal:
    base = base_currency.strip().upper()
    target = target_currency.strip().upper()
    if base == target:
        return Decimal("1")
    if not settings.finnhub_api_key:
        raise HTTPException(status_code=503, detail="Finnhub is not configured")
    try:
        response = httpx.get(
            FINNHUB_FOREX_URL,
            params={"base": base, "token": settings.finnhub_api_key},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError):
        try:
            response = httpx.get(
                FRANKFURTER_FOREX_URL,
                params={"base": base, "symbols": target},
                timeout=10,
            )
            response.raise_for_status()
            fallback = response.json()
            rate = Decimal(str((fallback.get("rates") or {}).get(target) or 0))
            if rate > 0:
                return rate
        except (httpx.HTTPError, ValueError):
            pass
        raise HTTPException(status_code=502, detail="Could not retrieve the live exchange rate")
    rate = Decimal(str((data.get("quote") or {}).get(target) or 0))
    if rate <= 0:
        raise HTTPException(status_code=404, detail=f"No live {base}/{target} exchange rate found")
    return rate
