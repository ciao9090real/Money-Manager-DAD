from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QApplication, QFrame

import app.ui.recurring_form as recurring_form_module
import app.ui.transaction_form as transaction_form_module
from app.core.database import connect
from app.services.account_service import AccountService
from app.services.category_service import CategoryService
from app.services.investment_service import InvestmentService
from app.services.loan_service import LoanService
from app.services.recurring_service import RecurringService
from app.ui.dashboard_page import DashboardPage
from app.ui.date_picker import DatePicker
from app.ui.investment_form import (
    AddInvestmentFundsDialog,
    InvestmentForm,
    UpdateInvestmentValueDialog,
)
from app.ui.investments_page import InvestmentsPage
from app.ui.recurring_form import RecurringRuleForm
from app.ui.loan_form import LoanForm
from app.ui.loans_page import LoansPage
from app.ui.transaction_form import TransactionForm
from app.utils.money import format_money


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_transaction_form_adds_and_selects_category_inline(
    qt_app, tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        accounts = AccountService(db)
        account = accounts.create_account("Current", "current_account")
        categories = CategoryService(db)
        form = TransactionForm(
            [account],
            [],
            [],
            category_service=categories,
        )
        form.type.setCurrentIndex(form.type.findData("expense"))
        created = categories.create_category("Groceries", "expense")
        monkeypatch.setattr(
            transaction_form_module,
            "create_category_dialog",
            lambda *_args: created,
        )

        form._add_category()

        assert not form.add_category_button.isHidden()
        assert form.category.currentData() == created.id
        form.close()
    finally:
        db.close()


def test_recurring_form_adds_expense_category_inline(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        accounts = AccountService(db)
        account = accounts.create_account("Current", "current_account")
        categories = CategoryService(db)
        form = RecurringRuleForm(
            [account],
            [],
            [],
            category_service=categories,
        )
        created = categories.create_category("Subscriptions", "expense")
        monkeypatch.setattr(
            recurring_form_module,
            "create_category_dialog",
            lambda *_args: created,
        )

        form._add_category()

        assert not form.add_category_button.isHidden()
        assert form.category.currentData() == created.id
        form.close()
    finally:
        db.close()


def test_recurring_income_form_uses_income_specific_controls(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        account = AccountService(db).create_account("Current", "current_account")
        categories = CategoryService(db)
        income_category = categories.create_category("Salary", "income")
        expense_category = categories.create_category("Bills", "expense")
        form = RecurringRuleForm(
            [account],
            [income_category, expense_category],
            [],
            category_service=categories,
        )

        form.transaction_type.setCurrentIndex(
            form.transaction_type.findData("income")
        )

        assert form.form.labelForField(form.account).text() == "Receive into"
        assert form.kind.currentText() == "Wage / income"
        assert form.category.findData(income_category.id) >= 0
        assert form.category.findData(expense_category.id) == -1
        assert not form.form.isRowVisible(form.payment_method)
        form.close()
    finally:
        db.close()


def test_dashboard_forecast_shows_downward_message(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        account = AccountService(db).create_account(
            "Current", "current_account", opening_balance="1000"
        )
        RecurringService(db).create_rule(
            "Large bill",
            "bill",
            "fixed",
            account.id,
            "monthly",
            "2026-08-01",
            amount="600",
        )
        dashboard = DashboardPage(db)

        dashboard.refresh()

        assert "forecast to decrease" in dashboard.forecast_message.text()
        assert dashboard.forecast_status.property("tone") == "negative"
        dashboard.close()
        dashboard.deleteLater()
        qt_app.processEvents()
    finally:
        db.close()


def test_loan_form_switches_borrowed_and_lent_wording(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        account = AccountService(db).create_account("Current", "current_account")
        form = LoanForm([account])
        form.direction.setCurrentIndex(form.direction.findData("lent"))

        assert form.form.labelForField(form.counterparty).text() == "Borrower"
        assert form.form.labelForField(form.account).text() == "Pay from"
        assert any(
            frame.property("role") == "formSurface"
            for frame in form.findChildren(QFrame)
        )
        form.close()
    finally:
        db.close()


def test_loans_page_renders_payoff_comparison(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        account = AccountService(db).create_account(
            "Current", "current_account", opening_balance="20000"
        )
        today = QDate.currentDate()
        LoanService(db).create_loan(
            "borrowed",
            "Car loan",
            "Bank",
            account.id,
            "10000",
            today.toString("yyyy-MM-dd"),
            due_date=today.addYears(2).toString("yyyy-MM-dd"),
            interest_rate="6",
        )
        page = LoansPage(db, lambda _pages: None)
        page.refresh()
        page.table.selectRow(0)
        page.extra_payment.setText("50")

        page.calculate_payoff()

        assert page.payoff_metric_values["payoff_date"].text() != "—"
        assert page.payoff_metric_values["interest_saved"].text() != format_money(0)
        assert page.amortization_table.rowCount() > 0
        assert page.amortization_table.rowCount() <= page.AMORTIZATION_PAGE_SIZE
        page.close()
        page.deleteLater()
        qt_app.processEvents()
    finally:
        db.close()


def test_value_updates_selector_is_independent_from_chart_selector(
    qt_app,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        account = AccountService(db).create_account(
            "Current",
            "current_account",
            opening_balance="1000",
        )
        investments = InvestmentService(db)
        first = investments.create_investment(
            "Equity",
            "etf",
            account.id,
            "100",
            "2026-07-01",
        )
        second = investments.create_investment(
            "Bonds",
            "bond",
            account.id,
            "200",
            "2026-07-02",
        )
        investments.update_value(second.investment.id, "210", "2026-07-03")
        page = InvestmentsPage(db, lambda _pages: None)
        page.refresh()

        assert page.table.currentRow() == 0
        assert page.delete_button.isEnabled()
        selected_investment_id = page.table.item(0, 0).data(Qt.ItemDataRole.UserRole)
        assert page.updates_selector.currentData() == selected_investment_id
        assert page.updates_selector.findData("portfolio") == -1

        page.history_selector.setCurrentIndex(
            page.history_selector.findData(first.investment.id)
        )
        page.updates_selector.setCurrentIndex(
            page.updates_selector.findData(second.investment.id)
        )
        page.updates_table.selectRow(0)
        qt_app.processEvents()

        assert page.history_selector.currentData() == first.investment.id
        assert page.updates_selector.currentData() == second.investment.id
        assert "Bonds" in page.updates_caption.text()
        assert page.edit_update_button.isEnabled()
        assert page.delete_update_button.isEnabled()
        assert page.clear_logs_button.isEnabled()
        page.updates_table.selectRow(1)
        qt_app.processEvents()
        assert page.delete_update_button.isEnabled()
        page.close()
        page.deleteLater()
        qt_app.processEvents()
    finally:
        db.close()


def test_investment_forms_cap_dates_at_today(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    dialogs = []
    try:
        account = AccountService(db).create_account(
            "Current",
            "current_account",
            opening_balance="1000",
        )
        snapshot = InvestmentService(db).create_investment(
            "Equity",
            "etf",
            account.id,
            "100",
            QDate.currentDate().toString("yyyy-MM-dd"),
        )
        dialogs = [
            InvestmentForm([account]),
            AddInvestmentFundsDialog(snapshot, [account]),
            UpdateInvestmentValueDialog(snapshot),
        ]

        assert all(
            dialog.date.maximumDate() == QDate.currentDate()
            for dialog in dialogs
        )
        assert all(isinstance(dialog.date, DatePicker) for dialog in dialogs)
        assert all(dialog.date.lineEdit().isReadOnly() for dialog in dialogs)
    finally:
        for dialog in dialogs:
            dialog.close()
        db.close()
