from __future__ import annotations

import sqlite3
from decimal import Decimal

from app.repositories.account_repository import AccountRepository
from app.repositories.loan_repository import LoanRepository
from app.repositories.payment_method_repository import PaymentMethodRepository
from app.repositories.transaction_repository import TransactionRepository
from app.utils.dates import month_bounds


class DashboardService:
    LIABILITY_TYPES = {"credit_card", "loan", "mortgage", "liability"}
    LIQUID_TYPES = {"bank", "current_account", "savings_account", "cash", "wallet", "benefit"}
    INVESTMENT_TYPES = {"investment", "property", "brokerage"}

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.accounts = AccountRepository(db)
        self.loans = LoanRepository(db)
        self.payment_methods = PaymentMethodRepository(db)
        self.transactions = TransactionRepository(db)

    def summary(self) -> dict:
        return self.global_snapshot()

    def global_snapshot(self) -> dict:
        account_rows = self.accounts.list_with_balances(include_inactive=False)
        account_summary = self._account_summary(account_rows)
        loan_rows = self.loans.list_with_balances(include_settled=False)
        borrowed_loans = sum(
            (outstanding for loan, _paid, outstanding in loan_rows if loan.direction == "borrowed"),
            Decimal("0"),
        )
        loan_receivables = sum(
            (outstanding for loan, _paid, outstanding in loan_rows if loan.direction == "lent"),
            Decimal("0"),
        )
        asset_total = sum(
            (
                row["balance"]
                for row in account_summary
                if row["type"] not in self.LIABILITY_TYPES and row["balance"] > 0
            ),
            Decimal("0"),
        ) + loan_receivables
        liability_debt = sum(
            (
                abs(row["balance"])
                for row in account_summary
                if row["type"] in self.LIABILITY_TYPES and row["balance"] < 0
            ),
            Decimal("0"),
        )
        bank_overdraft = sum(
            (
                abs(row["balance"])
                for row in account_summary
                if row["type"] in self.LIQUID_TYPES and row["balance"] < 0
            ),
            Decimal("0"),
        )
        debt_total = liability_debt + bank_overdraft + borrowed_loans
        net_worth = (
            sum((row["balance"] for row in account_summary), Decimal("0"))
            + loan_receivables
            - borrowed_loans
        )
        liquidity = sum(
            (row["balance"] for row in account_summary if row["type"] in self.LIQUID_TYPES),
            Decimal("0"),
        )
        investments_property = sum(
            (row["balance"] for row in account_summary if row["type"] in self.INVESTMENT_TYPES),
            Decimal("0"),
        )
        start_date, end_date = month_bounds()
        monthly_income, monthly_expenses = self.transactions.monthly_totals(start_date, end_date)
        monthly_net_flow = monthly_income - monthly_expenses
        return {
            "net_worth": net_worth,
            "total_assets": asset_total,
            "liquidity": liquidity,
            "investments_property": investments_property,
            "bank_overdraft": bank_overdraft,
            "liability_debt": liability_debt,
            "borrowed_loans": borrowed_loans,
            "loan_receivables": loan_receivables,
            "total_debt": debt_total,
            "monthly_income": monthly_income,
            "monthly_expenses": monthly_expenses,
            "monthly_net_flow": monthly_net_flow,
            "recent_transactions": self.transactions.list(
                limit=10,
                exclude_adjustments=True,
            ),
            "accounts": account_summary,
        }

    def scope_summary(
        self,
        scope_id: str | None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        if not scope_id or scope_id == "all":
            snapshot = self.global_snapshot()
            return {
                **snapshot,
                "scope_id": "all",
                "scope_label": "All accounts",
                "selected_balance": snapshot["net_worth"],
                "included_accounts": [row["name"] for row in snapshot["accounts"]],
                "child_account_count": len(snapshot["accounts"]),
                "payment_method_count": len(self.payment_methods.list(include_inactive=False)),
            }

        selected = self.accounts.get(scope_id)
        if not selected or not selected.is_active:
            return self.scope_summary("all", start_date, end_date)

        account_ids = self._account_scope_ids(scope_id)
        account_rows = [
            (account, balance)
            for account, balance in self.accounts.list_with_balances(include_inactive=False)
            if account.id in account_ids
        ]
        account_summary = self._account_summary(account_rows)
        period_start, period_end = self._period_bounds(start_date, end_date)
        income, expenses = self.transactions.monthly_totals(
            period_start,
            period_end,
            account_ids=account_ids,
        )
        methods = [
            method
            for method in self.payment_methods.list(include_inactive=False)
            if method.account_id in account_ids
        ]
        return {
            "scope_id": scope_id,
            "scope_label": selected.name,
            "selected_balance": sum((row["balance"] for row in account_summary), Decimal("0")),
            "liquidity": sum(
                (row["balance"] for row in account_summary if row["type"] in self.LIQUID_TYPES),
                Decimal("0"),
            ),
            "monthly_income": income,
            "monthly_expenses": expenses,
            "monthly_net_flow": income - expenses,
            "child_account_count": max(len(account_ids) - 1, 0),
            "payment_method_count": len(methods),
            "included_accounts": [row["name"] for row in account_summary],
            "recent_transactions": self.transactions.list(
                limit=10,
                account_ids=account_ids,
                exclude_adjustments=True,
            ),
            "accounts": account_summary,
            "payment_methods": methods,
        }

    def _account_summary(self, account_rows: list[tuple[object, Decimal]]) -> list[dict]:
        return [
            {
                "id": account.id,
                "name": account.name,
                "type": account.type,
                "parent_id": account.parent_id,
                "balance": balance,
            }
            for account, balance in account_rows
            if account.id is not None
        ]

    def _account_scope_ids(self, account_id: str) -> list[str]:
        accounts = self.accounts.list(include_inactive=False)
        children: dict[str, list[str]] = {}
        for account in accounts:
            if account.parent_id is not None and account.id is not None:
                children.setdefault(account.parent_id, []).append(account.id)
        ids: list[str] = []
        stack = [account_id]
        while stack:
            current_id = stack.pop()
            if current_id in ids:
                continue
            ids.append(current_id)
            stack.extend(children.get(current_id, []))
        return ids

    def _period_bounds(self, start_date: str | None, end_date: str | None) -> tuple[str, str]:
        if start_date and end_date:
            return start_date, end_date
        return month_bounds()
