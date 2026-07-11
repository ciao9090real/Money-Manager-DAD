from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.database import connect
from app.core.paths import backup_dir
from app.services.backup_service import BackupService
from app.services.dashboard_service import DashboardService


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


def test_dashboard_with_zero_data(db):
    summary = DashboardService(db).summary()

    assert summary["net_worth"] == Decimal("0")
    assert summary["liquidity"] == Decimal("0")
    assert summary["monthly_income"] == Decimal("0")
    assert summary["monthly_expenses"] == Decimal("0")
    assert summary["monthly_net_flow"] == Decimal("0")
    assert summary["recent_transactions"] == []
    assert summary["accounts"] == []


def test_backup_creates_database_copy(db):
    target = BackupService(db).create_backup()

    assert target.exists()
    assert target.parent == backup_dir()
    assert target.name.startswith("money_manager_backup_")
    assert target.suffix == ".db"

