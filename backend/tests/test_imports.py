from datetime import date
from decimal import Decimal

from app.services.imports import normalize_row, original_hash, parse_amount


def test_parse_decimal_comma():
    assert parse_amount("1.234,56", decimal_separator=",", thousands_separator=".") == Decimal("1234.56")


def test_normalize_debit_credit_row():
    row = {"Booking": "2026-01-10", "Text": "Coffee shop", "Debit": "4,50", "Credit": "", "Currency": "EUR"}
    parsed = normalize_row(
        row,
        account_id=7,
        mapping={"date": "Booking", "description": "Text", "debit": "Debit", "credit": "Credit", "currency": "Currency"},
        date_format="%Y-%m-%d",
        decimal_separator=",",
        thousands_separator=".",
    )
    assert parsed["amount"] == "-4.50"
    assert parsed["type"] == "expense"


def test_duplicate_hash_is_stable_for_whitespace_and_case():
    first = original_hash(1, date(2026, 1, 1), Decimal("-12.50"), " Grocery  Store ")
    second = original_hash(1, date(2026, 1, 1), Decimal("-12.50"), "grocery store")
    assert first == second
