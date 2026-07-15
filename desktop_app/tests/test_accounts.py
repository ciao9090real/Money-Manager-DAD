from __future__ import annotations

import pytest

from app.core.database import connect
from app.services.account_service import AccountService


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


def test_database_initialization(db):
    tables = {
        row["name"]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    assert {
        "accounts",
        "payment_methods",
        "categories",
        "transactions",
        "recurring_rules",
        "investments",
        "settings",
    }.issubset(tables)


def test_creating_account(db):
    service = AccountService(db)
    account = service.create_account("Main Bank", "bank", opening_balance="100")

    assert account.id is not None
    assert account.name == "Main Bank"
    assert service.account_balance(account.id) == account.opening_balance


def test_creating_child_account(db):
    service = AccountService(db)
    root = service.create_account("Main Bank", "bank")
    child = service.create_account("Current Account", "current_account", parent_id=root.id)

    tree = service.account_tree()
    assert tree[0]["account"].id == root.id
    assert tree[0]["children"][0]["account"].id == child.id


def test_rejecting_circular_account_parent(db):
    service = AccountService(db)
    root = service.create_account("Main Bank", "bank")
    child = service.create_account("Current Account", "current_account", parent_id=root.id)

    with pytest.raises(ValueError, match="Circular"):
        service.update_account(root.id, "Main Bank", "bank", child.id, "0")


def test_rejecting_account_depth_over_three(db):
    service = AccountService(db)
    root = service.create_account("Root", "bank")
    child = service.create_account("Child", "current_account", parent_id=root.id)
    grandchild = service.create_account("Grandchild", "wallet", parent_id=child.id)

    with pytest.raises(ValueError, match="three levels"):
        service.create_account("Too deep", "wallet", parent_id=grandchild.id)
