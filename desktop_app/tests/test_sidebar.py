from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.database import connect
from app.repositories.settings_repository import SettingsRepository
from app.ui.main_window import MainWindow
from app.ui.sidebar import Sidebar


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_collapsed_sidebar_keeps_icons_and_separates_expand_control(qt_app):
    sidebar = Sidebar(
        [("Dashboard", "dashboard"), ("Accounts", "accounts"), ("Settings", "settings")]
    )
    sidebar.show()
    sidebar.set_collapsed(True, animate=False)

    assert sidebar.width() == sidebar.COLLAPSED_WIDTH
    assert not sidebar.collapse_button.isVisible()
    assert sidebar.mark.isVisible()
    assert sidebar.expand_button.isVisible()
    mark_bottom = sidebar.mark.mapTo(sidebar, QPoint(0, sidebar.mark.height())).y()
    expand_top = sidebar.expand_button.mapTo(sidebar, QPoint(0, 0)).y()
    assert mark_bottom <= expand_top
    assert all(not item.text_label.isVisible() for item in sidebar.nav_buttons)
    assert all(item.icon_widget.isVisible() for item in sidebar.nav_buttons)

    sidebar.expand_button.click()
    QTest.qWait(sidebar.width_animation.duration() + 30)

    assert sidebar.width() == sidebar.EXPANDED_WIDTH
    assert all(item.text_label.isVisible() for item in sidebar.nav_buttons)
    sidebar.close()


def test_manual_sidebar_choice_is_persisted_and_disables_auto_mode(
    qt_app, tmp_path, monkeypatch
):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect()
    try:
        window = MainWindow(db)
        window.show()
        window.resize(1000, 700)
        QTest.qWait(window.sidebar.width_animation.duration() + 30)

        assert window.sidebar.collapsed
        assert SettingsRepository(db).get(window.SIDEBAR_SETTING, "") == ""

        window.sidebar.expand_button.click()
        QTest.qWait(window.sidebar.width_animation.duration() + 30)
        assert not window.sidebar.collapsed
        assert SettingsRepository(db).get(window.SIDEBAR_SETTING) == "0"

        window.resize(990, 700)
        QTest.qWait(30)
        assert not window.sidebar.collapsed
        window.close()
    finally:
        db.close()
