from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    settings: Mapped["UserSettings"] = relationship(back_populates="user", cascade="all, delete-orphan")
    recurring_payments: Mapped[list["RecurringPayment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSettings(Base, TimestampMixin):
    __tablename__ = "user_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    favorite_language: Mapped[str] = mapped_column(String(16), default="en")
    default_currency: Mapped[str] = mapped_column(String(3), default="EUR")
    theme: Mapped[str] = mapped_column(String(16), default="system")
    date_format: Mapped[str] = mapped_column(String(32), default="YYYY-MM-DD")
    number_format: Mapped[str] = mapped_column(String(32), default="1,234.56")
    profile_photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    user: Mapped[User] = relationship(back_populates="settings")


class Bank(Base, TimestampMixin):
    __tablename__ = "banks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    accounts: Mapped[list["Account"]] = relationship(back_populates="bank")
    cards: Mapped[list["Card"]] = relationship(back_populates="bank")


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("banks.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(40), default="checking")
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    iban_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    bank: Mapped[Bank] = relationship(back_populates="accounts")
    cards: Mapped[list["Card"]] = relationship(back_populates="account")


class Card(Base, TimestampMixin):
    __tablename__ = "cards"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("banks.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(40), default="debit")
    network: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last4: Mapped[str] = mapped_column(String(4))
    expiry_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expiry_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    bank: Mapped[Bank] = relationship(back_populates="cards")
    account: Mapped[Account] = relationship(back_populates="cards")


class Category(Base, TimestampMixin):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(40), default="expense")
    icon: Mapped[str | None] = mapped_column(String(40), nullable=True)
    color: Mapped[str | None] = mapped_column(String(24), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("user_id", "original_hash", name="uq_user_original_hash"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("banks.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey("cards.id"), nullable=True, index=True)
    date: Mapped[date] = mapped_column(Date)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text)
    merchant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    original_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    original_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    type: Mapped[str] = mapped_column(String(40), default="expense")
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    subcategory_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_transfer: Mapped[bool] = mapped_column(Boolean, default=False)
    transfer_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_recurring_candidate: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"), nullable=True)
    original_hash: Mapped[str] = mapped_column(String(64), index=True)


class ImportTemplate(Base, TimestampMixin):
    __tablename__ = "import_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("banks.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(12))
    date_column: Mapped[str | None] = mapped_column(String(120), nullable=True)
    value_date_column: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description_column: Mapped[str | None] = mapped_column(String(120), nullable=True)
    amount_column: Mapped[str | None] = mapped_column(String(120), nullable=True)
    debit_column: Mapped[str | None] = mapped_column(String(120), nullable=True)
    credit_column: Mapped[str | None] = mapped_column(String(120), nullable=True)
    currency_column: Mapped[str | None] = mapped_column(String(120), nullable=True)
    balance_column: Mapped[str | None] = mapped_column(String(120), nullable=True)
    date_format: Mapped[str | None] = mapped_column(String(40), nullable=True)
    decimal_separator: Mapped[str] = mapped_column(String(1), default=".")
    thousands_separator: Mapped[str | None] = mapped_column(String(1), nullable=True)
    skip_rows: Mapped[int] = mapped_column(Integer, default=0)
    encoding: Mapped[str] = mapped_column(String(40), default="utf-8")
    mapping_json: Mapped[str] = mapped_column(Text, default="{}")


class ImportBatch(Base, TimestampMixin):
    __tablename__ = "import_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    bank_id: Mapped[int | None] = mapped_column(ForeignKey("banks.id"), nullable=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey("cards.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)


class ImportedRow(Base):
    __tablename__ = "imported_rows"
    id: Mapped[int] = mapped_column(primary_key=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    raw_data_json: Mapped[str] = mapped_column(Text)
    parsed_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Portfolio(Base, TimestampMixin):
    __tablename__ = "portfolios"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    broker_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)


class InvestmentSummary(Base, TimestampMixin):
    __tablename__ = "investment_summaries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), unique=True, index=True)
    total_invested: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    net_invested: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    worth_today: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    asset_type: Mapped[str] = mapped_column(String(40))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    isin: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Holding(Base):
    __tablename__ = "holdings"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0)
    average_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    current_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class InvestmentTransaction(Base):
    __tablename__ = "investment_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    linked_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    date: Mapped[date] = mapped_column(Date)
    type: Mapped[str] = mapped_column(String(40))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    fees: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    taxes: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InsurancePolicy(Base, TimestampMixin):
    __tablename__ = "insurance_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider_name: Mapped[str] = mapped_column(String(255))
    policy_name: Mapped[str] = mapped_column(String(255))
    policy_type: Mapped[str] = mapped_column(String(40))
    policy_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    premium_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    premium_frequency: Mapped[str] = mapped_column(String(40), default="monthly")
    insured_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    beneficiary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linked_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InsurancePayment(Base, TimestampMixin):
    __tablename__ = "insurance_payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("insurance_policies.id"), index=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    due_date: Mapped[date] = mapped_column(Date)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(32), default="due")


class RecurringPayment(Base, TimestampMixin):
    __tablename__ = "recurring_payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey("cards.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32), default="subscription")
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    frequency: Mapped[str] = mapped_column(String(32), default="monthly")
    next_due_date: Mapped[date] = mapped_column(Date, index=True)
    notify_days_before: Mapped[int] = mapped_column(Integer, default=3)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    user: Mapped[User] = relationship(back_populates="recurring_payments")
