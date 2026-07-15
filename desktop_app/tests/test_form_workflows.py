from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QFrame

import app.ui.recurring_form as recurring_form_module
import app.ui.transaction_form as transaction_form_module
from app.core.database import connect
from app.services.account_service import AccountService
from app.services.category_service import CategoryService
from app.ui.recurring_form import RecurringRuleForm
from app.ui.loan_form import LoanForm
from app.ui.transaction_form import TransactionForm


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
