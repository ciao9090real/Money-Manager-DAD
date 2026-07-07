from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.crud import account_depth, build_account_tree, ensure_owner, signed_transaction_amount, validate_account_parent
from app.db.session import Base
from app.models import Account, Bank, User
from app.schemas import TransactionIn


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def create_user_bank(db, user_id: int, email: str = "user@example.com") -> Bank:
    user = User(id=user_id, email=email, full_name="", password_hash="hash")
    bank = Bank(id=user_id, user_id=user_id, name=f"Bank {user_id}")
    db.add_all([user, bank])
    db.commit()
    return bank


def create_account(db, user_id: int, bank_id: int, account_id: int, name: str, parent_id: int | None = None, balance=0):
    account = Account(
        id=account_id,
        user_id=user_id,
        bank_id=bank_id,
        parent_account_id=parent_id,
        name=name,
        type="current_account",
        account_type="current_account",
        account_level=1,
        currency="EUR",
        current_balance=Decimal(str(balance)),
    )
    db.add(account)
    db.commit()
    return account


def test_user_cannot_access_another_users_account(db):
    bank = create_user_bank(db, 1)
    create_user_bank(db, 2, "other@example.com")
    account = create_account(db, 1, bank.id, 10, "Current")

    with pytest.raises(HTTPException) as error:
        ensure_owner(db, Account, account.id, 2)

    assert error.value.status_code == 404


def test_account_can_be_root_or_child_and_tree_rolls_up(db):
    bank = create_user_bank(db, 1)
    root = create_account(db, 1, bank.id, 10, "Main Bank", balance=100)
    child = create_account(db, 1, bank.id, 11, "Current Account", parent_id=root.id, balance=50)

    assert validate_account_parent(db, 1, bank.id, None) == 1
    assert validate_account_parent(db, 1, bank.id, root.id) == 2

    tree = build_account_tree([root, child])
    assert len(tree) == 1
    assert tree[0]["children"][0]["id"] == child.id
    assert tree[0]["rollup_balance"] == Decimal("150")


def test_circular_parent_relationship_is_rejected(db):
    bank = create_user_bank(db, 1)
    root = create_account(db, 1, bank.id, 10, "Root")
    child = create_account(db, 1, bank.id, 11, "Child", parent_id=root.id)
    root.parent_account_id = child.id
    db.commit()

    with pytest.raises(HTTPException):
        account_depth(db, root)


def test_transaction_amount_signing_is_reliable():
    base = {
        "bank_id": 1,
        "account_id": 1,
        "date": "2026-07-07",
        "description": "Manual",
        "amount": Decimal("25"),
    }

    assert signed_transaction_amount(TransactionIn(**base, type="income")) == Decimal("25")
    assert signed_transaction_amount(TransactionIn(**base, type="expense")) == Decimal("-25")
    legacy_expense = {**base, "amount": Decimal("-25")}
    assert signed_transaction_amount(TransactionIn(**legacy_expense, type="expense")) == Decimal("-25")
    assert signed_transaction_amount(TransactionIn(**base, type="transfer")) == Decimal("-25")
