from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from app.core.database import connect
from app.services.account_service import AccountService
from app.ui.accounts_page import AccountsPage
from app.ui.styles import app_stylesheet
from app.ui.transactions_page import TransactionsPage
from app.ui.upcoming_page import UpcomingPage
from app.ui.workspace_pages import PositionOverviewPage, ReconciliationPage


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(app_stylesheet())
    return app


def test_empty_transactions_keep_all_copy_inside_the_card(
    qt_app, tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect(tmp_path / "empty-transactions.db")
    try:
        AccountService(db).create_account(
            "Main",
            "bank",
            opening_balance="10000",
        )
        page = TransactionsPage(db, lambda _pages: None)
        page.resize(1200, 650)
        page.show()
        page.refresh()
        qt_app.processEvents()

        assert page.start_date.width() >= 154
        assert page.end_date.width() >= 154
        assert page.activity_card.height() < 480
        for label in page.empty.findChildren(QLabel):
            if label.isVisible():
                bottom = label.mapTo(
                    page.activity_card,
                    label.rect().bottomLeft(),
                ).y()
                assert bottom <= page.activity_card.rect().bottom()

        page.resize(900, 650)
        qt_app.processEvents()
        assert not page._filters_side_by_side
        date_bottom = page.end_date.mapTo(
            page.activity_card,
            page.end_date.rect().bottomLeft(),
        ).y()
        assert date_bottom <= page.activity_card.rect().bottom()
        for label in page.empty.findChildren(QLabel):
            if label.isVisible():
                bottom = label.mapTo(
                    page.activity_card,
                    label.rect().bottomLeft(),
                ).y()
                assert bottom <= page.activity_card.rect().bottom()
        page.close()
    finally:
        db.close()


def test_sparse_account_views_do_not_expand_into_empty_cards(
    qt_app, tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect(tmp_path / "sparse-accounts.db")
    try:
        AccountService(db).create_account(
            "Main",
            "bank",
            opening_balance="10000",
        )

        accounts = AccountsPage(db, lambda _pages: None)
        accounts.resize(1300, 700)
        accounts.show()
        accounts.refresh()
        qt_app.processEvents()
        assert accounts.structure_card.height() < 360

        accounts.tree.setCurrentItem(accounts.tree.topLevelItem(0))
        qt_app.processEvents()
        assert not hasattr(accounts, "details_card")
        assert accounts.edit_button.isVisible()
        assert accounts.deactivate_button.isVisible()
        actions_bottom = accounts.deactivate_button.mapTo(
            accounts.structure_card,
            accounts.deactivate_button.rect().bottomLeft(),
        ).y()
        assert actions_bottom <= accounts.structure_card.rect().bottom()
        accounts.close()

        position = PositionOverviewPage(db)
        position.resize(1300, 700)
        position.show()
        position.refresh()
        qt_app.processEvents()
        assert position.accounts_card.height() < 280
        position.close()
    finally:
        db.close()


def test_empty_state_copy_is_never_vertically_compressed(
    qt_app, tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect(tmp_path / "empty-copy.db")
    try:
        pages = (
            ReconciliationPage(db),
            UpcomingPage(db, on_changed=lambda _pages: None),
        )
        for page in pages:
            page.resize(1200, 650)
            page.show()
            page.refresh()
            qt_app.processEvents()

            labels = [
                label
                for label in page.empty.findChildren(QLabel)
                if label.text()
            ]
            assert labels
            for label in labels:
                assert label.height() >= label.sizeHint().height()
            page.close()
    finally:
        db.close()
