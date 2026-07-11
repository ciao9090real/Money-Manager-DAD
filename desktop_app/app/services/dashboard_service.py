from __future__ import annotations

import sqlite3
from decimal import Decimal

from app.services.account_service import AccountService
from app.repositories.transaction_repository import TransactionRepository
from app.utils.dates import month_prefix


class DashboardService:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.accounts = AccountService(db)
        self.transactions = TransactionRepository(db)

    def summary(self) -> dict:
        account_rows = self.accounts.list_accounts(include_inactive=False)
        account_summary = [
            {
                "id": account.id,
                "name": account.name,
                "type": account.type,
                "balance": self.accounts.account_balance(int(account.id)),
            }
            for account in account_rows
            if account.id is not None
        ]
        liquidity = sum((row["balance"] for row in account_summary), Decimal("0"))
        month_transactions = self.transactions.list_for_month(month_prefix())
        monthly_income = sum((tx.amount for tx in month_transactions if tx.type == "income"), Decimal("0"))
        monthly_expenses = abs(sum((tx.amount for tx in month_transactions if tx.type == "expense"), Decimal("0")))
        monthly_net_flow = monthly_income - monthly_expenses
        return {
            "net_worth": liquidity,
            "liquidity": liquidity,
            "monthly_income": monthly_income,
            "monthly_expenses": monthly_expenses,
            "monthly_net_flow": monthly_net_flow,
            "recent_transactions": self.transactions.list(limit=10),
            "accounts": account_summary,
        }

