from __future__ import annotations

import sqlite3
from decimal import Decimal

from app.repositories.account_repository import AccountRepository
from app.repositories.transaction_repository import TransactionRepository
from app.utils.dates import month_bounds


class DashboardService:
    LIABILITY_TYPES = {"credit_card", "loan", "mortgage", "liability"}
    LIQUID_TYPES = {"bank", "current_account", "savings_account", "cash", "wallet", "benefit"}

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.accounts = AccountRepository(db)
        self.transactions = TransactionRepository(db)

    def summary(self) -> dict:
        account_rows = self.accounts.list_with_balances(include_inactive=False)
        account_summary = [
            {
                "id": account.id,
                "name": account.name,
                "type": account.type,
                "balance": balance,
            }
            for account, balance in account_rows
            if account.id is not None
        ]
        asset_total = sum(
            (row["balance"] for row in account_summary if row["type"] not in self.LIABILITY_TYPES),
            Decimal("0"),
        )
        liability_total = sum(
            (row["balance"] for row in account_summary if row["type"] in self.LIABILITY_TYPES),
            Decimal("0"),
        )
        # Liability balances use a negative sign convention, so paying debt
        # moves the balance toward zero and all postings keep their usual signs.
        net_worth = asset_total + liability_total
        liquidity = sum(
            (row["balance"] for row in account_summary if row["type"] in self.LIQUID_TYPES),
            Decimal("0"),
        )
        start_date, end_date = month_bounds()
        monthly_income, monthly_expenses = self.transactions.monthly_totals(start_date, end_date)
        monthly_net_flow = monthly_income - monthly_expenses
        return {
            "net_worth": net_worth,
            "liquidity": liquidity,
            "monthly_income": monthly_income,
            "monthly_expenses": monthly_expenses,
            "monthly_net_flow": monthly_net_flow,
            "recent_transactions": self.transactions.list(limit=10),
            "accounts": account_summary,
        }
