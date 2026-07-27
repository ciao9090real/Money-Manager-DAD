from __future__ import annotations

import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.core.database import connect
from app.services.account_service import AccountService
from app.services.home_service import HomeService
from app.services.recurring_service import RecurringService
from app.ui.main_window import MainWindow
from app.ui.workspace import WorkspaceRoute


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_empty_home_uses_an_honest_account_onboarding_action(db):
    brief = HomeService(db).brief(date(2026, 7, 27))

    assert brief.summary.startswith("Nothing needs attention")
    assert brief.primary_action.id == "onboarding:account"
    assert brief.primary_action.route == WorkspaceRoute(
        "position", "accounts", action="add"
    )
    assert brief.attention_items == ()
    assert not brief.safe_spend_configured


def test_home_ranks_overdue_schedule_first_and_does_not_repeat_it(db):
    account = AccountService(db).create_account(
        "Everyday", "current_account", opening_balance="250"
    )
    recurring = RecurringService(db)
    recurring.create_rule(
        "Rent",
        "bill",
        "fixed",
        account.id,
        "monthly",
        "2026-07-26",
        amount="100",
        reminder_days=5,
    )
    recurring.create_rule(
        "Phone",
        "subscription",
        "fixed",
        account.id,
        "monthly",
        "2026-07-29",
        amount="20",
        reminder_days=5,
    )

    brief = HomeService(db).brief(date(2026, 7, 27))

    assert brief.primary_action.id.startswith("recurring:")
    assert brief.primary_action.title == "Rent is overdue"
    assert all(item.id != brief.primary_action.id for item in brief.attention_items)
    assert [item.title for item in brief.attention_items] == [
        "Phone is due in 2 days"
    ]
    assert [item.title for item in brief.upcoming] == ["Phone"]


def test_negative_account_outranks_a_due_soon_schedule(db):
    account = AccountService(db).create_account(
        "Everyday", "current_account", opening_balance="-10"
    )
    RecurringService(db).create_rule(
        "Internet",
        "bill",
        "fixed",
        account.id,
        "monthly",
        "2026-07-28",
        amount="50",
        reminder_days=3,
    )

    brief = HomeService(db).brief(date(2026, 7, 27))

    assert brief.primary_action.title == "Everyday is below zero"
    assert brief.primary_action.route.workspace == "position"
    assert brief.attention_items[0].title == "Internet is due tomorrow"


def test_main_window_routes_workspaces_to_existing_pages(qt_app, db):
    window = MainWindow(db)
    try:
        window.show()
        qt_app.processEvents()
        assert [item.label for item in window.sidebar.nav_buttons] == [
            "Home",
            "Activity",
            "Plan",
            "Position",
            "Settings",
        ]
        assert window.stack.currentWidget() is window.home
        assert not window.workspace_bar.isVisible()

        window.navigate(WorkspaceRoute("activity", "recurring"))
        qt_app.processEvents()
        assert window.stack.currentWidget() is window.upcoming
        assert window.workspace_bar.isVisible()
        assert window.sidebar.nav_buttons[1].property("selected") == "true"

        window.navigate(WorkspaceRoute("position", "overview"))
        qt_app.processEvents()
        assert window.stack.currentWidget() is window.position
        assert window.workspace_bar.workspace_label.text() == "POSITION"
    finally:
        window.close()
