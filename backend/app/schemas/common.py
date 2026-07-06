from decimal import Decimal
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = ""


class UserRead(ORMModel):
    id: int
    email: EmailStr
    full_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8)


class SettingsRead(ORMModel):
    id: int
    favorite_language: str
    default_currency: str
    theme: str
    date_format: str
    number_format: str
    profile_photo_url: str | None = None
    notifications_enabled: bool


class SettingsUpdate(BaseModel):
    favorite_language: str | None = None
    default_currency: str | None = None
    theme: str | None = None
    date_format: str | None = None
    number_format: str | None = None
    profile_photo_url: str | None = None
    notifications_enabled: bool | None = None


class ProfileUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None


class BankIn(BaseModel):
    name: str
    country: str | None = None
    website: str | None = None
    notes: str | None = None


class AccountIn(BaseModel):
    bank_id: int
    name: str
    type: str = "checking"
    currency: str = "EUR"
    iban_last4: str | None = Field(default=None, max_length=4)
    opening_balance: Decimal = Decimal("0")
    current_balance: Decimal = Decimal("0")


class CardIn(BaseModel):
    bank_id: int
    account_id: int
    name: str
    type: str = "debit"
    network: str | None = None
    last4: str = Field(min_length=4, max_length=4)
    expiry_month: int | None = Field(default=None, ge=1, le=12)
    expiry_year: int | None = Field(default=None, ge=2000, le=2200)
    credit_limit: Decimal | None = Field(default=None, ge=0)
    current_balance: Decimal = Decimal("0")


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: str = "expense"
    icon: str | None = None
    color: str | None = None


class RecurringPaymentIn(BaseModel):
    account_id: int | None = None
    card_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    kind: str = "subscription"
    amount: Decimal = Decimal("0")
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    frequency: str = "monthly"
    next_due_date: date
    notify_days_before: int = Field(default=3, ge=0, le=30)


class TransactionIn(BaseModel):
    bank_id: int
    account_id: int
    card_id: int | None = None
    date: str
    value_date: str | None = None
    description: str
    merchant_name: str | None = None
    amount: Decimal
    currency: str = "EUR"
    type: str = "expense"
    category_id: int | None = None
    notes: str | None = None


class ImportMapRequest(BaseModel):
    bank_id: int
    account_id: int
    card_id: int | None = None
    mapping: dict[str, str | None]
    date_format: str | None = None
    decimal_separator: str = "."
    thousands_separator: str | None = None
    save_template_name: str | None = None


class GenericCreate(BaseModel):
    data: dict[str, Any]
