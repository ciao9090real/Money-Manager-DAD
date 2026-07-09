from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Account, Card, Holding, InsurancePolicy, Transaction


LIQUIDITY_ACCOUNT_TYPES = {
    "current_account",
    "savings_account",
    "cash",
    "wallet",
    "benefit",
    "checking",
    "savings",
}

DEBT_ACCOUNT_TYPES = {"loan", "mortgage", "credit_card_liability"}


def account_type(account: Account) -> str:
    return (account.account_type or account.type or "").strip().lower()


def build_dashboard_report(db: Session, user_id: int) -> dict:
    accounts = db.query(Account).filter_by(user_id=user_id, is_active=True).all()
    cards = db.query(Card).filter_by(user_id=user_id, is_active=True).all()
    liquidity = sum(
        Decimal(account.current_balance or 0)
        for account in accounts
        if account_type(account) in LIQUIDITY_ACCOUNT_TYPES
    )
    liquidity += sum(Decimal(card.current_balance or 0) for card in cards if card.type == "prepaid")
    investments = sum(
        Decimal(holding.quantity or 0) * Decimal(holding.current_price or 0)
        for holding in db.query(Holding).filter_by(user_id=user_id).all()
    )
    insurance = sum(
        Decimal(policy.insured_amount or 0)
        for policy in db.query(InsurancePolicy).filter_by(user_id=user_id, is_active=True).all()
    )
    debt = sum(
        abs(Decimal(account.current_balance or 0))
        for account in accounts
        if account_type(account) in DEBT_ACCOUNT_TYPES and Decimal(account.current_balance or 0) < 0
    )
    month_start = date.today().replace(day=1)
    income = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user_id,
        Transaction.date >= month_start,
        Transaction.amount > 0,
    ).scalar()
    expenses = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user_id,
        Transaction.date >= month_start,
        Transaction.amount < 0,
    ).scalar()
    recent = db.query(Transaction).filter_by(user_id=user_id).order_by(Transaction.date.desc()).limit(8).all()
    net_worth = liquidity + investments + insurance - debt
    savings_rate = (
        float((Decimal(income or 0) + Decimal(expenses or 0)) / Decimal(income or 1) * 100)
        if Decimal(income or 0)
        else 0
    )
    return {
        "net_worth": net_worth,
        "total_liquidity": liquidity,
        "total_investments": investments,
        "insurance_value": insurance,
        "total_debt": debt,
        "monthly_income": income or Decimal("0"),
        "monthly_expenses": abs(Decimal(expenses or 0)),
        "savings_rate": round(savings_rate, 2),
        "recent_transactions": recent,
        "account_balances": accounts,
        "card_balances": cards,
    }
