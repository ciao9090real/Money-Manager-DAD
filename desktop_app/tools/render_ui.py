from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.database import connect
from app.services.account_service import AccountService
from app.services.investment_service import InvestmentService
from app.services.payment_method_service import PaymentMethodService
from app.services.recurring_service import RecurringService
from app.services.transaction_service import TransactionService
from app.services.category_service import CategoryService
from app.ui.account_form import AccountForm
from app.ui.main_window import MainWindow
from app.ui.investment_form import InvestmentForm
from app.ui.recurring_form import RecurringRuleForm
from app.ui.transaction_form import TransactionForm


def main() -> None:
    output = Path(__file__).resolve().parents[2] / "artifacts"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="money_manager_ui_") as directory:
        db = connect(Path(directory) / "preview.db")
        try:
            seed(db)
            app = QApplication.instance() or QApplication([])
            window = MainWindow(db)
            window.resize(1440, 900)
            window.show()
            app.processEvents()
            for index, name in enumerate(
                (
                    "dashboard",
                    "accounts",
                    "transactions",
                    "investments",
                    "upcoming",
                    "settings",
                )
            ):
                window._select_page(index)
                app.processEvents()
                window.grab().save(str(output / f"ui-{name}.png"))
            window.resize(1000, 720)
            app.processEvents()
            for index, name in (
                (0, "dashboard-compact"),
                (2, "transactions-compact"),
                (3, "investments-compact"),
                (4, "upcoming-compact"),
            ):
                window._select_page(index)
                app.processEvents()
                window.grab().save(str(output / f"ui-{name}.png"))
            account_service = AccountService(db)
            payment_service = PaymentMethodService(db)
            account_form = AccountForm(account_service.list_accounts())
            account_form.show()
            app.processEvents()
            account_form.grab().save(str(output / "ui-account-form.png"))
            account_form.close()
            transaction_form = TransactionForm(
                account_service.list_accounts(),
                CategoryService(db).list_categories(),
                payment_service.list_payment_methods(),
                category_service=CategoryService(db),
            )
            transaction_form.show()
            app.processEvents()
            transaction_form.grab().save(str(output / "ui-transaction-form.png"))
            transaction_form.close()
            recurring_form = RecurringRuleForm(
                account_service.list_accounts(),
                CategoryService(db).list_categories(),
                payment_service.list_payment_methods(),
                category_service=CategoryService(db),
            )
            recurring_form.show()
            app.processEvents()
            recurring_form.grab().save(str(output / "ui-recurring-form.png"))
            recurring_form.close()
            investment_form = InvestmentForm(
                [
                    account
                    for account in account_service.list_accounts()
                    if account.type in InvestmentService.FUNDING_ACCOUNT_TYPES
                ]
            )
            investment_form.show()
            app.processEvents()
            investment_form.grab().save(str(output / "ui-investment-form.png"))
            investment_form.close()
            recurring_service = RecurringService(db)
            for rule in recurring_service.list_rules():
                recurring_service.delete_rule(rule.id)
            window.invalidate({"upcoming"})
            window._select_page(4)
            app.processEvents()
            window.grab().save(str(output / "ui-upcoming-empty.png"))
            window.close()
        finally:
            db.close()


def seed(db) -> None:
    accounts = AccountService(db)
    transactions = TransactionService(db)
    recurring = RecurringService(db)
    investments = InvestmentService(db)
    payments = PaymentMethodService(db)
    bank = accounts.create_account("Everyday Banking", "bank")
    current = accounts.create_account(
        "Main Current", "current_account", parent_id=bank.id, opening_balance="2840.50"
    )
    savings = accounts.create_account(
        "Rainy Day Fund", "savings_account", parent_id=bank.id, opening_balance="12400"
    )
    wallet = accounts.create_account("Cash Wallet", "cash", opening_balance="185.20")
    brokerage = accounts.create_account("Long-term Portfolio", "investment", opening_balance="7650")
    card = payments.create_payment_method("Everyday card", current.id, "debit_card")
    transactions.add_income(
        current.id, "3200", "2026-07-01", "Monthly salary", "Salary", card.id
    )
    transactions.add_expense(
        current.id, "86.40", "2026-07-13", "Weekly groceries", "Groceries", card.id
    )
    transactions.add_expense(
        current.id, "42.90", "2026-07-12", "Dinner with family", "Dining", card.id
    )
    transactions.add_expense(
        current.id, "64.00", "2026-07-10", "Electric bill", "Utilities", card.id
    )
    transactions.add_expense(
        wallet.id, "18.50", "2026-07-09", "Coffee and lunch", "Dining"
    )
    transactions.add_transfer(
        current.id, savings.id, "500", "2026-07-08", "Monthly savings"
    )
    transactions.add_adjustment(
        brokerage.id, "124.35", "2026-07-07", "Portfolio valuation"
    )
    investments.create_investment(
        "Global equity index",
        "etf",
        current.id,
        "1000",
        "2026-07-06",
        current_value="1108.40",
        symbol="VWCE",
    )
    recurring.create_rule(
        "Cloud storage",
        "subscription",
        "fixed",
        current.id,
        "monthly",
        "2026-07-18",
        amount="12.99",
        reminder_days=3,
    )
    recurring.create_rule(
        "Electricity",
        "bill",
        "variable",
        current.id,
        "monthly",
        "2026-07-22",
        amount="75",
        reminder_days=5,
    )


if __name__ == "__main__":
    main()
