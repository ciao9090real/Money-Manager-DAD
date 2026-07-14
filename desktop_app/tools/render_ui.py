from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.core.database import connect
from app.services.account_service import AccountService
from app.services.payment_method_service import PaymentMethodService
from app.services.transaction_service import TransactionService
from app.services.category_service import CategoryService
from app.ui.account_form import AccountForm
from app.ui.main_window import MainWindow
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
            for index, name in enumerate(("dashboard", "accounts", "transactions", "settings")):
                window._select_page(index)
                app.processEvents()
                window.grab().save(str(output / f"ui-{name}.png"))
            window.resize(1000, 720)
            app.processEvents()
            for index, name in ((0, "dashboard-compact"), (2, "transactions-compact")):
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
            )
            transaction_form.show()
            app.processEvents()
            transaction_form.grab().save(str(output / "ui-transaction-form.png"))
            transaction_form.close()
            window.close()
        finally:
            db.close()


def seed(db) -> None:
    accounts = AccountService(db)
    transactions = TransactionService(db)
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


if __name__ == "__main__":
    main()
