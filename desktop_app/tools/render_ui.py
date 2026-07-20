from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from app.core.database import connect
from app.services.account_service import AccountService
from app.services.budget_service import BudgetService
from app.services.investment_service import InvestmentService
from app.services.loan_service import LoanService
from app.services.payment_method_service import PaymentMethodService
from app.services.recurring_service import RecurringService
from app.services.transaction_service import TransactionService
from app.services.category_service import CategoryService
from app.ui.account_form import AccountForm
from app.ui.backup_password_dialog import BackupPasswordDialog
from app.ui.budget_form import BudgetForm
from app.ui.main_window import MainWindow
from app.ui.investment_form import InvestmentForm
from app.ui.loan_form import LoanForm, LoanPaymentDialog
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
            for index, name in enumerate(window.page_keys):
                window._select_page(index)
                app.processEvents()
                window.grab().save(str(output / f"ui-{name}.png"))
            window._select_page(window.page_keys.index("investments"))
            window.investments.history_selector.setCurrentIndex(
                window.investments.history_selector.count() - 1
            )
            window.investments.updates_selector.setCurrentIndex(1)
            app.processEvents()
            window.grab().save(str(output / "ui-investment-detail.png"))
            window.investments._set_history_interval("updates")
            app.processEvents()
            window.grab().save(str(output / "ui-investment-updates.png"))
            window.investments._set_history_interval("monthly")
            window._select_page(window.page_keys.index("loans"))
            window.loans.set_filter("borrowed")
            window.loans.table.selectRow(0)
            window.loans.extra_payment.setText("75")
            window.loans.calculate_payoff()
            app.processEvents()
            window.grab().save(str(output / "ui-loan-payoff.png"))
            window.resize(1000, 720)
            QTest.qWait(window.sidebar.width_animation.duration() + 40)
            app.processEvents()
            for index, key in enumerate(window.page_keys):
                name = f"{key}-compact"
                window._select_page(index)
                app.processEvents()
                window.grab().save(str(output / f"ui-{name}.png"))
            window.resize(1440, 900)
            window._select_page(0)
            dashboard_scroll = window.dashboard.page_scroll.verticalScrollBar()
            dashboard_scroll.setValue(dashboard_scroll.maximum())
            app.processEvents()
            window.grab().save(str(output / "ui-dashboard-lower.png"))
            dashboard_scroll.setValue(0)
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
            budget_form = BudgetForm(
                [
                    category
                    for category in CategoryService(db).list_categories()
                    if category.type == "expense"
                ]
            )
            budget_form.show()
            app.processEvents()
            budget_form.grab().save(str(output / "ui-budget-form.png"))
            budget_form.close()
            recurring_form = RecurringRuleForm(
                account_service.list_accounts(),
                CategoryService(db).list_categories(),
                payment_service.list_payment_methods(),
                category_service=CategoryService(db),
            )
            recurring_form.show()
            app.processEvents()
            recurring_form.grab().save(str(output / "ui-recurring-form.png"))
            recurring_form.transaction_type.setCurrentIndex(
                recurring_form.transaction_type.findData("income")
            )
            app.processEvents()
            recurring_form.grab().save(str(output / "ui-recurring-income-form.png"))
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
            backup_password = BackupPasswordDialog(confirm_password=True)
            backup_password.show()
            app.processEvents()
            backup_password.grab().save(str(output / "ui-backup-password.png"))
            backup_password.close()
            loan_service = LoanService(db)
            loan_form = LoanForm(
                [
                    account
                    for account in account_service.list_accounts()
                    if account.type in loan_service.FUNDING_ACCOUNT_TYPES
                ]
            )
            loan_form.show()
            app.processEvents()
            loan_form.grab().save(str(output / "ui-loan-form.png"))
            loan_form.close()
            loan_snapshot = loan_service.list_snapshots()[0]
            payment_form = LoanPaymentDialog(
                loan_snapshot,
                [
                    account
                    for account in account_service.list_accounts()
                    if account.type in loan_service.FUNDING_ACCOUNT_TYPES
                ],
            )
            payment_form.show()
            app.processEvents()
            payment_form.grab().save(str(output / "ui-loan-payment-form.png"))
            payment_form.close()
            recurring_service = RecurringService(db)
            for rule in recurring_service.list_rules():
                recurring_service.delete_rule(rule.id)
            window.invalidate({"upcoming"})
            window._select_page(window.page_keys.index("upcoming"))
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
    loans = LoanService(db)
    payments = PaymentMethodService(db)
    budgets = BudgetService(db)
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
    expense_categories = {
        category.name: category.id
        for category in CategoryService(db).list_categories()
        if category.type == "expense"
    }
    budgets.set_budget(
        expense_categories["Groceries"], "420", rollover=True, start_date="2026-06-01"
    )
    budgets.set_budget(
        expense_categories["Dining"], "180", start_date="2026-07-01"
    )
    budgets.set_budget(
        expense_categories["Utilities"], "140", start_date="2026-07-01"
    )
    transactions.add_transfer(
        current.id, savings.id, "500", "2026-07-08", "Monthly savings"
    )
    transactions.add_adjustment(
        brokerage.id, "124.35", "2026-07-07", "Portfolio valuation"
    )
    index_fund = investments.create_investment(
        "Global equity index",
        "etf",
        current.id,
        "1000",
        "2026-03-06",
        current_value="1108.40",
        symbol="VWCE",
    )
    investments.update_value(index_fund.investment.id, "1136.20", "2026-04-10")
    investments.add_funds(index_fund.investment.id, current.id, "250", "2026-05-08")
    investments.update_value(index_fund.investment.id, "1392.80", "2026-06-12")
    investments.update_value(index_fund.investment.id, "1424.75", "2026-07-14")
    investments.create_investment(
        "European bond ladder",
        "bond",
        savings.id,
        "650",
        "2026-05-08",
        current_value="662.30",
    )
    loans.create_loan(
        "borrowed",
        "Car loan",
        "Community bank",
        current.id,
        "8500",
        "2026-06-01",
        due_date="2029-06-01",
        interest_rate="4.25",
    )
    loans.create_loan(
        "lent",
        "Family loan",
        "Alex",
        savings.id,
        "1200",
        "2026-05-10",
        due_date="2027-05-10",
    )
    recurring.create_rule(
        "Monthly wage",
        "other",
        "fixed",
        current.id,
        "monthly",
        "2026-08-01",
        amount="3200",
        transaction_type="income",
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
