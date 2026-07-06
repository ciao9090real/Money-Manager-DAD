import hashlib
import io
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd


def read_statement_bytes(filename: str, content: bytes, encoding: str = "utf-8", skip_rows: int = 0) -> list[dict[str, Any]]:
    lower = filename.lower()
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        df = pd.read_excel(io.BytesIO(content), skiprows=skip_rows)
    else:
        try:
            df = pd.read_csv(io.BytesIO(content), encoding=encoding, skiprows=skip_rows)
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(content), encoding="latin-1", skiprows=skip_rows)
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records")


def parse_amount(value: Any, decimal_separator: str = ".", thousands_separator: str | None = None) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    text = str(value).strip().replace(" ", "")
    if thousands_separator:
        text = text.replace(thousands_separator, "")
    if decimal_separator == ",":
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount: {value}") from exc


def parse_date(value: Any, date_format: str | None = None) -> date:
    if value is None or value == "":
        raise ValueError("Missing date")
    if date_format:
        return pd.to_datetime(value, format=date_format).date()
    return pd.to_datetime(value, dayfirst=False).date()


def normalize_description(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def original_hash(account_id: int, tx_date: date, amount: Decimal, description: str) -> str:
    source = f"{account_id}|{tx_date.isoformat()}|{amount.quantize(Decimal('0.01'))}|{normalize_description(description)}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def normalize_row(raw: dict[str, Any], account_id: int, mapping: dict[str, str | None], date_format: str | None, decimal_separator: str, thousands_separator: str | None) -> dict[str, Any]:
    def pick(field: str) -> Any:
        column = mapping.get(field)
        return raw.get(column) if column else None

    debit = pick("debit")
    credit = pick("credit")
    amount_value = pick("amount")
    if amount_value is None and (debit is not None or credit is not None):
        debit_amount = parse_amount(debit, decimal_separator, thousands_separator) if debit not in (None, "") else Decimal("0")
        credit_amount = parse_amount(credit, decimal_separator, thousands_separator) if credit not in (None, "") else Decimal("0")
        amount = credit_amount - debit_amount
    else:
        amount = parse_amount(amount_value, decimal_separator, thousands_separator)

    tx_date = parse_date(pick("date"), date_format)
    description = str(pick("description") or "").strip()
    if not description:
        raise ValueError("Missing description")
    currency = str(pick("currency") or "EUR").strip().upper()
    value_date_raw = pick("value_date")
    parsed = {
        "date": tx_date.isoformat(),
        "value_date": parse_date(value_date_raw, date_format).isoformat() if value_date_raw else None,
        "description": description,
        "amount": str(amount),
        "currency": currency,
        "type": "income" if amount >= 0 else "expense",
        "original_hash": original_hash(account_id, tx_date, amount, description),
    }
    return parsed


def dumps(data: Any) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


def loads(text: str | None) -> Any:
    return json.loads(text) if text else None
