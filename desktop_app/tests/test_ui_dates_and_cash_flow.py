from __future__ import annotations

import os
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTableView, QToolTip

from app.core.database import connect
from app.services.account_service import AccountService
from app.services.recurring_service import RecurringService
from app.services.transaction_service import TransactionService
from app.ui.charts import CashFlowChart
from app.ui.date_picker import DatePicker
from app.ui.main_window import MainWindow
from app.ui.transactions_page import TransactionsPage
from app.ui.upcoming_page import UpcomingPage
from app.ui.styles import app_stylesheet


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_date_picker_opens_calendar_from_the_whole_field(qt_app):
    qt_app.setStyleSheet(app_stylesheet())
    picker = DatePicker(QDate(2026, 4, 15))
    picker.resize(180, 42)
    picker.show()
    QTest.qWait(20)

    assert picker.lineEdit().isReadOnly()
    QTest.mouseClick(
        picker,
        Qt.MouseButton.LeftButton,
        pos=picker.rect().center(),
    )
    QTest.qWait(20)

    assert picker.calendarWidget().isVisible()
    calendar = picker.calendarWidget()
    calendar_view = calendar.findChild(QTableView, "qt_calendar_calendarview")
    assert calendar.minimumHeight() == 240
    assert calendar_view is not None
    visible_rows_height = sum(
        calendar_view.rowHeight(row)
        for row in range(calendar_view.model().rowCount())
    )
    assert visible_rows_height <= calendar_view.viewport().height() + 2
    picker.calendarWidget().hide()
    picker.close()


def test_cash_flow_bar_hover_and_click_expose_month_and_type(qt_app):
    chart = CashFlowChart()
    chart.resize(760, 240)
    chart.set_data(
        [("2026-04", "Apr", Decimal("100"), Decimal("45.50"))]
    )
    selected = []
    chart.period_selected.connect(
        lambda month, transaction_type: selected.append((month, transaction_type))
    )
    chart.show()
    QTest.qWait(20)
    chart.repaint()
    qt_app.processEvents()

    income_region = next(
        region for region in chart._bar_regions if region[2] == "income"
    )
    point = income_region[0].center().toPoint()
    QTest.mouseMove(chart, point)
    qt_app.processEvents()

    assert chart._hovered_bar == ("2026-04", "income")
    assert "100.00" in QToolTip.text()

    QTest.mouseClick(chart, Qt.MouseButton.LeftButton, pos=point)
    assert selected == [("2026-04", "income")]
    chart.close()


def test_transaction_month_filter_is_inclusive_and_type_specific(
    qt_app, tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        account = AccountService(db).create_account("Current", "current_account")
        transactions = TransactionService(db)
        transactions.add_expense(account.id, "10", "2026-04-01", "First")
        transactions.add_expense(account.id, "20", "2026-04-30", "Last")
        transactions.add_expense(account.id, "30", "2026-05-01", "Next")
        transactions.add_income(account.id, "100", "2026-04-15", "Wage")
        page = TransactionsPage(db, lambda _pages: None)

        page.set_month_filter("2026-04", "expense")
        page.resize(900, 650)
        page.show()
        qt_app.processEvents()

        assert page.date_range_enabled.isChecked()
        assert page.start_date.date() == QDate(2026, 4, 1)
        assert page.end_date.date() == QDate(2026, 4, 30)
        assert page.current_filter == "expense"
        assert page.table_model.rowCount() == 2
        assert {
            page.table_model.transaction_at(row).date
            for row in range(page.table_model.rowCount())
        } == {"2026-04-01", "2026-04-30"}
        date_bottom = (
            page.end_date.mapTo(page.controls, page.end_date.rect().bottomLeft()).y()
        )
        assert date_bottom <= page.controls.height()
        page.close()
    finally:
        db.close()


def test_upcoming_paused_rule_exposes_resume_only_after_selection(
    qt_app, tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        account = AccountService(db).create_account("Current", "current_account")
        recurring = RecurringService(db)
        rule = recurring.create_rule(
            "Spotify",
            "subscription",
            "fixed",
            account.id,
            "monthly",
            "2026-10-15",
            amount="18.99",
        )
        recurring.set_paused(rule.id, True)
        page = UpcomingPage(db, lambda _pages: None)
        page.resize(1000, 700)
        page.show()
        page.refresh()
        qt_app.processEvents()

        assert page.action_container.isHidden()

        page.table.selectRow(0)
        qt_app.processEvents()

        assert not page.action_container.isHidden()
        assert page.pause_button.text() == "Resume"
        assert page.pause_button.isEnabled()
        assert not page.record_button.isEnabled()
        assert not page.skip_button.isEnabled()
        page.close()
    finally:
        db.close()


def test_dashboard_period_selection_opens_filtered_transactions(
    qt_app, tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        window = MainWindow(db)
        window.dashboard.cash_flow_chart.period_selected.emit("2026-04", "expense")

        assert window.stack.currentWidget() is window.transactions
        assert window.transactions.current_filter == "expense"
        assert window.transactions.start_date.date() == QDate(2026, 4, 1)
        assert window.transactions.end_date.date() == QDate(2026, 4, 30)
        window.close()
    finally:
        db.close()
