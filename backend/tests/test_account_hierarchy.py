from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.crud import (
    account_depth,
    account_tree,
    build_account_tree,
    create_account as api_create_account,
    create_transaction,
    ensure_owner,
    signed_transaction_amount,
    update_transaction,
    validate_account_parent,
)
from app.db.session import Base
from app.models import Account, Bank, Transaction, User
from app.schemas import AccountIn, TransactionIn
from app.services.dashboard import build_dashboard_report


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


def add_account(db, user_id: int, bank_id: int, account_id: int, name: str, parent_id: int | None = None, balance=0, account_type="current_account"):
    account = Account(
        id=account_id,
        user_id=user_id,
        bank_id=bank_id,
        parent_account_id=parent_id,
        name=name,
        type=account_type,
        account_type=account_type,
        account_level=1,
        currency="EUR",
        current_balance=Decimal(str(balance)),
    )
    db.add(account)
    db.commit()
    return account


def get_user(db, user_id: int = 1) -> User:
    return db.query(User).filter_by(id=user_id).one()


def test_user_cannot_access_another_users_account(db):
    bank = create_user_bank(db, 1)
    create_user_bank(db, 2, "other@example.com")
    account = add_account(db, 1, bank.id, 10, "Current")

    with pytest.raises(HTTPException) as error:
        ensure_owner(db, Account, account.id, 2)

    assert error.value.status_code == 404


def test_account_can_be_root_or_child_and_tree_rolls_up(db):
    bank = create_user_bank(db, 1)
    root = add_account(db, 1, bank.id, 10, "Main Bank", balance=100)
    child = add_account(db, 1, bank.id, 11, "Current Account", parent_id=root.id, balance=50)

    assert validate_account_parent(db, 1, bank.id, None) == 1
    assert validate_account_parent(db, 1, bank.id, root.id) == 2

    tree = build_account_tree([root, child])
    assert len(tree) == 1
    assert tree[0]["children"][0]["id"] == child.id
    assert tree[0]["rollup_balance"] == Decimal("150")


def test_circular_parent_relationship_is_rejected(db):
    bank = create_user_bank(db, 1)
    root = add_account(db, 1, bank.id, 10, "Root")
    child = add_account(db, 1, bank.id, 11, "Child", parent_id=root.id)
    root.parent_account_id = child.id
    db.commit()

    with pytest.raises(HTTPException):
        account_depth(db, root)


def test_creating_root_account_normalizes_type_and_level(db):
    bank = create_user_bank(db, 1)
    account = api_create_account(
        AccountIn(bank_id=bank.id, name="Everyday", type="checking", current_balance=Decimal("25")),
        db,
        get_user(db),
    )

    assert account.parent_account_id is None
    assert account.account_level == 1
    assert account.type == "current_account"
    assert account.account_type == "current_account"


def test_creating_child_account_sets_level(db):
    bank = create_user_bank(db, 1)
    root = add_account(db, 1, bank.id, 10, "Root")

    child = api_create_account(
        AccountIn(bank_id=bank.id, parent_account_id=root.id, name="Pocket", account_type="wallet"),
        db,
        get_user(db),
    )

    assert child.parent_account_id == root.id
    assert child.account_level == 2
    assert child.account_type == "wallet"


def test_account_hierarchy_deeper_than_three_levels_is_rejected(db):
    bank = create_user_bank(db, 1)
    root = add_account(db, 1, bank.id, 10, "Root")
    child = add_account(db, 1, bank.id, 11, "Child", parent_id=root.id)
    grandchild = add_account(db, 1, bank.id, 12, "Grandchild", parent_id=child.id)

    with pytest.raises(HTTPException) as error:
        validate_account_parent(db, 1, bank.id, grandchild.id)

    assert error.value.status_code == 422


def test_account_tree_returns_only_current_user_accounts(db):
    bank = create_user_bank(db, 1)
    other_bank = create_user_bank(db, 2, "other@example.com")
    own = add_account(db, 1, bank.id, 10, "Own")
    add_account(db, 2, other_bank.id, 20, "Other")

    tree = account_tree(db=db, user=get_user(db))

    assert [node["id"] for node in tree] == [own.id]


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


def test_income_updates_account_balance(db):
    bank = create_user_bank(db, 1)
    account = add_account(db, 1, bank.id, 10, "Current", balance=100)

    create_transaction(
        TransactionIn(bank_id=bank.id, account_id=account.id, date="2026-07-07", description="Salary", amount=Decimal("25"), type="income"),
        db,
        get_user(db),
    )

    db.refresh(account)
    assert account.current_balance == Decimal("125.00")


def test_expense_updates_account_balance(db):
    bank = create_user_bank(db, 1)
    account = add_account(db, 1, bank.id, 10, "Current", balance=100)

    create_transaction(
        TransactionIn(bank_id=bank.id, account_id=account.id, date="2026-07-07", description="Groceries", amount=Decimal("25"), type="expense"),
        db,
        get_user(db),
    )

    db.refresh(account)
    assert account.current_balance == Decimal("75.00")


def test_transfer_updates_both_balances_and_preserves_net_worth(db):
    bank = create_user_bank(db, 1)
    source = add_account(db, 1, bank.id, 10, "Current", balance=100)
    target = add_account(db, 1, bank.id, 11, "Savings", balance=50, account_type="savings_account")
    before = build_dashboard_report(db, 1)["net_worth"]

    outgoing = create_transaction(
        TransactionIn(
            bank_id=bank.id,
            account_id=source.id,
            transfer_account_id=target.id,
            date="2026-07-07",
            amount=Decimal("30"),
            type="transfer",
        ),
        db,
        get_user(db),
    )

    db.refresh(source)
    db.refresh(target)
    linked = db.query(Transaction).filter_by(transfer_group_id=outgoing.transfer_group_id).all()
    assert len(linked) == 2
    assert sorted(transaction.amount for transaction in linked) == [Decimal("-30.00"), Decimal("30.00")]
    assert source.current_balance == Decimal("70.00")
    assert target.current_balance == Decimal("80.00")
    assert build_dashboard_report(db, 1)["net_worth"] == before


def test_transfer_accounts_must_be_different(db):
    bank = create_user_bank(db, 1)
    account = add_account(db, 1, bank.id, 10, "Current", balance=100)

    with pytest.raises(HTTPException) as error:
        create_transaction(
            TransactionIn(
                bank_id=bank.id,
                account_id=account.id,
                transfer_account_id=account.id,
                date="2026-07-07",
                amount=Decimal("10"),
                type="transfer",
            ),
            db,
            get_user(db),
        )

    assert error.value.status_code == 422


def test_transfer_target_account_must_belong_to_current_user(db):
    bank = create_user_bank(db, 1)
    other_bank = create_user_bank(db, 2, "other@example.com")
    source = add_account(db, 1, bank.id, 10, "Current", balance=100)
    target = add_account(db, 2, other_bank.id, 20, "Other", balance=50)

    with pytest.raises(HTTPException) as error:
        create_transaction(
            TransactionIn(
                bank_id=bank.id,
                account_id=source.id,
                transfer_account_id=target.id,
                date="2026-07-07",
                amount=Decimal("10"),
                type="transfer",
            ),
            db,
            get_user(db),
        )

    assert error.value.status_code == 404


def test_transfer_editing_is_blocked(db):
    bank = create_user_bank(db, 1)
    source = add_account(db, 1, bank.id, 10, "Current", balance=100)
    target = add_account(db, 1, bank.id, 11, "Savings", balance=50, account_type="savings_account")
    outgoing = create_transaction(
        TransactionIn(
            bank_id=bank.id,
            account_id=source.id,
            transfer_account_id=target.id,
            date="2026-07-07",
            amount=Decimal("10"),
            type="transfer",
        ),
        db,
        get_user(db),
    )

    with pytest.raises(HTTPException) as error:
        update_transaction(
            outgoing.id,
            TransactionIn(bank_id=bank.id, account_id=source.id, date="2026-07-08", amount=Decimal("12"), type="expense"),
            db,
            get_user(db),
        )

    assert error.value.status_code == 409


def test_dashboard_counts_normalized_and_legacy_liquidity_types(db):
    bank = create_user_bank(db, 1)
    add_account(db, 1, bank.id, 10, "Current", balance=100, account_type="current_account")
    add_account(db, 1, bank.id, 11, "Savings", balance=50, account_type="savings_account")
    add_account(db, 1, bank.id, 12, "Cash", balance=10, account_type="cash")
    add_account(db, 1, bank.id, 13, "Wallet", balance=5, account_type="wallet")
    add_account(db, 1, bank.id, 14, "Benefit", balance=15, account_type="benefit")
    legacy_checking = add_account(db, 1, bank.id, 15, "Legacy Checking", balance=20, account_type="checking")
    legacy_checking.account_type = ""
    legacy_checking.type = "checking"
    legacy_savings = add_account(db, 1, bank.id, 16, "Legacy Savings", balance=30, account_type="savings")
    legacy_savings.account_type = ""
    legacy_savings.type = "savings"
    ignored = add_account(db, 1, bank.id, 17, "Invest", balance=1000, account_type="investment")
    ignored.type = "current_account"
    db.commit()

    report = build_dashboard_report(db, 1)

    assert report["total_liquidity"] == Decimal("230.00")
    assert report["net_worth"] == Decimal("230.00")


def test_zero_data_dashboard_returns_zero_totals(db):
    create_user_bank(db, 1)

    report = build_dashboard_report(db, 1)

    assert report["net_worth"] == Decimal("0")
    assert report["total_liquidity"] == Decimal("0")
    assert report["total_investments"] == Decimal("0")
    assert report["insurance_value"] == Decimal("0")
    assert report["total_debt"] == Decimal("0")
    assert report["monthly_income"] == Decimal("0")
    assert report["monthly_expenses"] == Decimal("0")
    assert report["savings_rate"] == 0
