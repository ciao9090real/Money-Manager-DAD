from collections import defaultdict
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import (
    Account,
    Asset,
    Bank,
    Card,
    Category,
    Holding,
    InsurancePayment,
    InsurancePolicy,
    InvestmentSummary,
    InvestmentTransaction,
    Portfolio,
    RecurringPayment,
    Transaction,
    User,
)
from app.schemas import AccountIn, AccountTreeNode, BankIn, CardIn, CategoryIn, GenericCreate, TransactionIn
from app.services.dashboard import build_dashboard_report
from app.services.imports import normalize_description, original_hash
from app.services.market import get_exchange_rate


router = APIRouter()

ACCOUNT_TYPES = {
    "bank",
    "current_account",
    "savings_account",
    "cash",
    "wallet",
    "card_container",
    "payment_method",
    "investment",
    "insurance",
    "benefit",
    "checking",
    "savings",
    "brokerage",
    "loan",
    "mortgage",
    "other",
}


def add_calendar_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def recurring_occurrences(next_due_date: date, frequency: str, start: date, end: date) -> list[date]:
    dates: list[date] = []
    frequency = frequency.lower()
    if frequency == "weekly":
        occurrence = next_due_date
        if occurrence < start:
            occurrence += timedelta(days=((start - occurrence).days + 6) // 7 * 7)
        while occurrence <= end:
            dates.append(occurrence)
            occurrence += timedelta(days=7)
        return dates

    month_step = {"monthly": 1, "quarterly": 3, "yearly": 12}.get(frequency, 1)
    index = 0
    occurrence = next_due_date
    while occurrence < start:
        index += 1
        occurrence = add_calendar_months(next_due_date, month_step * index)
    while occurrence <= end:
        dates.append(occurrence)
        index += 1
        occurrence = add_calendar_months(next_due_date, month_step * index)
    return dates


def ensure_owner(db: Session, model, object_id: int, user_id: int):
    item = db.query(model).filter(model.id == object_id, model.user_id == user_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item


def update_fields(item, payload: dict):
    for key, value in payload.items():
        if value is not None and hasattr(item, key):
            setattr(item, key, value)
    return item


def ensure_account_bank(db: Session, account_id: int, bank_id: int, user_id: int) -> Account:
    account = ensure_owner(db, Account, account_id, user_id)
    if account.bank_id != bank_id:
        raise HTTPException(status_code=422, detail="The selected account does not belong to the selected bank")
    return account


def ensure_card_account(db: Session, card_id: int | None, account_id: int, user_id: int) -> Card | None:
    if not card_id:
        return None
    card = ensure_owner(db, Card, card_id, user_id)
    if card.account_id != account_id:
        raise HTTPException(status_code=422, detail="The selected card does not belong to the selected account")
    return card


def ensure_category_access(db: Session, category_id: int | None, user_id: int) -> Category | None:
    if not category_id:
        return None
    category = db.query(Category).filter(
        Category.id == category_id,
        or_(Category.user_id == user_id, Category.user_id.is_(None)),
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


def normalize_account_type(value: str | None, fallback: str | None = None) -> str:
    account_type = (value or fallback or "other").strip().lower()
    aliases = {
        "checking": "current_account",
        "savings": "savings_account",
        "cash_wallet": "wallet",
        "brokerage": "investment",
        "payment": "payment_method",
    }
    account_type = aliases.get(account_type, account_type)
    if account_type not in ACCOUNT_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported account type")
    return account_type


def account_depth(db: Session, account: Account) -> int:
    depth = 1
    seen = {account.id}
    parent_id = account.parent_account_id
    while parent_id:
        if parent_id in seen:
            raise HTTPException(status_code=422, detail="Circular account hierarchy detected")
        seen.add(parent_id)
        parent = db.query(Account).filter(Account.id == parent_id, Account.user_id == account.user_id).first()
        if not parent:
            break
        depth += 1
        parent_id = parent.parent_account_id
    return depth


def account_descendant_ids(db: Session, account_id: int, user_id: int) -> set[int]:
    children_by_parent: dict[int, list[int]] = defaultdict(list)
    rows = db.query(Account.id, Account.parent_account_id).filter(Account.user_id == user_id).all()
    for child_id, parent_id in rows:
        if parent_id:
            children_by_parent[parent_id].append(child_id)
    descendants: set[int] = set()
    stack = list(children_by_parent.get(account_id, []))
    while stack:
        child_id = stack.pop()
        if child_id in descendants:
            continue
        descendants.add(child_id)
        stack.extend(children_by_parent.get(child_id, []))
    return descendants


def validate_account_parent(
    db: Session,
    user_id: int,
    bank_id: int,
    parent_account_id: int | None,
    account_id: int | None = None,
) -> int:
    if not parent_account_id:
        return 1
    if account_id and parent_account_id == account_id:
        raise HTTPException(status_code=422, detail="An account cannot be its own parent")
    parent = ensure_owner(db, Account, parent_account_id, user_id)
    if parent.bank_id != bank_id:
        raise HTTPException(status_code=422, detail="Parent account must belong to the same bank")
    if not parent.is_active:
        raise HTTPException(status_code=422, detail="Parent account must be active")
    if account_id and parent_account_id in account_descendant_ids(db, account_id, user_id):
        raise HTTPException(status_code=422, detail="An account cannot be moved under one of its children")
    level = account_depth(db, parent) + 1
    if level > 3:
        raise HTTPException(status_code=422, detail="Account hierarchy can be at most three levels deep")
    return level


def refresh_account_levels(db: Session, user_id: int) -> None:
    accounts = db.query(Account).filter(Account.user_id == user_id).all()
    for account in accounts:
        account.account_level = account_depth(db, account)


def build_account_tree(accounts: list[Account]) -> list[dict]:
    nodes = {
        account.id: {
            "id": account.id,
            "bank_id": account.bank_id,
            "parent_account_id": account.parent_account_id,
            "name": account.name,
            "type": account.type,
            "account_type": account.account_type or account.type,
            "account_level": account.account_level or 1,
            "currency": account.currency,
            "current_balance": account.current_balance or Decimal("0"),
            "direct_balance": account.current_balance or Decimal("0"),
            "rollup_balance": account.current_balance or Decimal("0"),
            "display_order": account.display_order or 0,
            "is_active": account.is_active,
            "children": [],
        }
        for account in accounts
    }
    roots: list[dict] = []
    for account in accounts:
        node = nodes[account.id]
        parent = nodes.get(account.parent_account_id)
        if parent:
            parent["children"].append(node)
        else:
            roots.append(node)

    def sort_and_rollup(node: dict) -> Decimal:
        node["children"].sort(key=lambda child: (child["display_order"], child["account_level"], child["name"].lower()))
        total = Decimal(node["direct_balance"] or 0)
        for child in node["children"]:
            total += sort_and_rollup(child)
        node["rollup_balance"] = total
        return total

    roots.sort(key=lambda item: (item["display_order"], item["account_level"], item["name"].lower()))
    for root in roots:
        sort_and_rollup(root)
    return roots


def signed_transaction_amount(payload: TransactionIn) -> Decimal:
    amount = Decimal(payload.amount or 0)
    if amount == 0:
        raise HTTPException(status_code=422, detail="Transaction amount must be greater than zero")
    absolute = abs(amount)
    if payload.type == "income":
        return absolute
    if payload.type in {"expense", "investment"}:
        return -absolute
    if payload.type == "adjustment":
        return amount
    if payload.type == "transfer":
        return -absolute
    raise HTTPException(status_code=422, detail="Unsupported transaction type")


@router.get("/categories")
def list_categories(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(Category)
        .filter(or_(Category.user_id == user.id, Category.user_id.is_(None)))
        .order_by(Category.type, Category.name)
        .all()
    )


@router.post("/categories")
def create_category(payload: CategoryIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    category_type = payload.type.lower()
    if category_type not in {"income", "expense", "investment"}:
        raise HTTPException(status_code=422, detail="Category type must be income, expense, or investment")
    exists = db.query(Category).filter_by(user_id=user.id, name=payload.name.strip(), type=category_type).first()
    if exists:
        raise HTTPException(status_code=400, detail="You already have a category with that name")
    item = Category(user_id=user.id, **payload.model_dump(exclude={"type"}), type=category_type, is_system=False)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/categories/{item_id}")
def update_category(item_id: int, payload: CategoryIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(Category).filter_by(id=item_id, user_id=user.id, is_system=False).first()
    if not item:
        raise HTTPException(status_code=404, detail="Custom category not found")
    category_type = payload.type.lower()
    if category_type not in {"income", "expense", "investment"}:
        raise HTTPException(status_code=422, detail="Category type must be income, expense, or investment")
    item.name = payload.name.strip()
    item.type = category_type
    item.icon = payload.icon
    item.color = payload.color
    db.commit()
    db.refresh(item)
    return item


@router.delete("/categories/{item_id}")
def delete_category(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.query(Category).filter_by(id=item_id, user_id=user.id, is_system=False).first()
    if not item:
        raise HTTPException(status_code=404, detail="Custom category not found")
    db.query(Transaction).filter_by(user_id=user.id, category_id=item.id).update(
        {"category_id": None}, synchronize_session=False
    )
    db.query(Transaction).filter_by(user_id=user.id, subcategory_id=item.id).update(
        {"subcategory_id": None}, synchronize_session=False
    )
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/banks")
def list_banks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Bank).filter_by(user_id=user.id, is_active=True).order_by(Bank.name).all()


@router.post("/banks")
def create_bank(payload: BankIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = Bank(user_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/banks/{item_id}")
def get_bank(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ensure_owner(db, Bank, item_id, user.id)


@router.patch("/banks/{item_id}")
def update_bank(item_id: int, payload: BankIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ensure_owner(db, Bank, item_id, user.id)
    update_fields(item, payload.model_dump())
    db.commit()
    db.refresh(item)
    return item


@router.delete("/banks/{item_id}")
def archive_bank(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ensure_owner(db, Bank, item_id, user.id)
    item.is_active = False
    db.query(Account).filter_by(user_id=user.id, bank_id=item.id).update(
        {"is_active": False}, synchronize_session=False
    )
    db.query(Card).filter_by(user_id=user.id, bank_id=item.id).update(
        {"is_active": False}, synchronize_session=False
    )
    db.commit()
    return {"ok": True}


@router.get("/accounts")
def list_accounts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(Account)
        .filter_by(user_id=user.id, is_active=True)
        .order_by(Account.display_order, Account.account_level, Account.name)
        .all()
    )


@router.get("/accounts/tree", response_model=list[AccountTreeNode])
def account_tree(include_inactive: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Account).filter(Account.user_id == user.id)
    if not include_inactive:
        query = query.filter(Account.is_active.is_(True))
    accounts = query.order_by(Account.display_order, Account.account_level, Account.name).all()
    return build_account_tree(accounts)


def account_hierarchy_fields(db: Session, payload: AccountIn, user_id: int, account_id: int | None = None) -> dict:
    data = payload.model_dump()
    data["account_type"] = normalize_account_type(data.get("account_type"), data.get("type"))
    data["type"] = data["account_type"]
    parent_id = data.get("parent_account_id")
    data["account_level"] = validate_account_parent(db, user_id, payload.bank_id, parent_id, account_id)
    return data


@router.post("/accounts")
def create_account(payload: AccountIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_owner(db, Bank, payload.bank_id, user.id)
    item = Account(user_id=user.id, **account_hierarchy_fields(db, payload, user.id))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/accounts/{item_id}")
def get_account(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ensure_owner(db, Account, item_id, user.id)


@router.patch("/accounts/{item_id}")
def update_account(item_id: int, payload: AccountIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ensure_owner(db, Account, item_id, user.id)
    ensure_owner(db, Bank, payload.bank_id, user.id)
    update_fields(item, account_hierarchy_fields(db, payload, user.id, item.id))
    refresh_account_levels(db, user.id)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/accounts/{item_id}")
def archive_account(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ensure_owner(db, Account, item_id, user.id)
    item.is_active = False
    db.query(Card).filter_by(user_id=user.id, account_id=item.id).update(
        {"is_active": False}, synchronize_session=False
    )
    db.commit()
    return {"ok": True}


@router.get("/cards")
def list_cards(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Card).filter_by(user_id=user.id, is_active=True).order_by(Card.name).all()


@router.get("/accounts/{account_id}/cards")
def list_account_cards(account_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_owner(db, Account, account_id, user.id)
    return (
        db.query(Card)
        .filter_by(user_id=user.id, account_id=account_id, is_active=True)
        .order_by(Card.name)
        .all()
    )


@router.post("/cards")
def create_card(payload: CardIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_owner(db, Bank, payload.bank_id, user.id)
    ensure_account_bank(db, payload.account_id, payload.bank_id, user.id)
    item = Card(user_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/cards/{item_id}")
def get_card(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ensure_owner(db, Card, item_id, user.id)


@router.patch("/cards/{item_id}")
def update_card(item_id: int, payload: CardIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ensure_owner(db, Card, item_id, user.id)
    ensure_owner(db, Bank, payload.bank_id, user.id)
    ensure_account_bank(db, payload.account_id, payload.bank_id, user.id)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/cards/{item_id}")
def archive_card(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ensure_owner(db, Card, item_id, user.id)
    item.is_active = False
    db.commit()
    return {"ok": True}


@router.get("/transactions")
def list_transactions(
    q: str | None = None,
    account_id: int | None = None,
    card_id: int | None = None,
    bank_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Transaction).filter(Transaction.user_id == user.id)
    if account_id:
        query = query.filter(Transaction.account_id == account_id)
    if card_id:
        query = query.filter(Transaction.card_id == card_id)
    if bank_id:
        query = query.filter(Transaction.bank_id == bank_id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Transaction.description.ilike(like), Transaction.merchant_name.ilike(like)))
    return query.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(300).all()


@router.post("/transactions")
def create_transaction(payload: TransactionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ensure_owner(db, Bank, payload.bank_id, user.id)
    account = ensure_account_bank(db, payload.account_id, payload.bank_id, user.id)
    card = ensure_card_account(db, payload.card_id, payload.account_id, user.id)
    ensure_category_access(db, payload.category_id, user.id)
    try:
        tx_date = date.fromisoformat(payload.date)
        value_date = date.fromisoformat(payload.value_date) if payload.value_date else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Transaction date must be a valid YYYY-MM-DD date")
    signed_amount = signed_transaction_amount(payload)
    description = (payload.description or "").strip()
    if payload.type != "transfer" and not description:
        description = "Manual transaction"
    if payload.type == "transfer":
        if not payload.transfer_account_id:
            raise HTTPException(status_code=422, detail="Choose the account that receives this transfer")
        target = ensure_owner(db, Account, payload.transfer_account_id, user.id)
        if target.id == account.id:
            raise HTTPException(status_code=422, detail="Transfer accounts must be different")
        group_id = uuid4().hex
        amount = abs(Decimal(payload.amount or 0))
        if amount <= 0:
            raise HTTPException(status_code=422, detail="Transfer amount must be greater than zero")
        outgoing = Transaction(
            user_id=user.id,
            bank_id=account.bank_id,
            account_id=account.id,
            card_id=card.id if card else None,
            date=tx_date,
            value_date=value_date,
            description=description or f"Transfer to {target.name}",
            amount=-amount,
            currency=account.currency,
            type="transfer",
            category_id=None,
            notes=payload.notes,
            is_transfer=True,
            transfer_group_id=group_id,
            source="manual",
            original_hash=sha256(f"transfer:{user.id}:{group_id}:out".encode()).hexdigest(),
        )
        incoming = Transaction(
            user_id=user.id,
            bank_id=target.bank_id,
            account_id=target.id,
            card_id=None,
            date=tx_date,
            value_date=value_date,
            description=description or f"Transfer from {account.name}",
            amount=amount,
            currency=target.currency,
            type="transfer",
            category_id=None,
            notes=payload.notes,
            is_transfer=True,
            transfer_group_id=group_id,
            source="manual",
            original_hash=sha256(f"transfer:{user.id}:{group_id}:in".encode()).hexdigest(),
        )
        db.add_all([outgoing, incoming])
        account.current_balance = Decimal(account.current_balance or 0) - amount
        target.current_balance = Decimal(target.current_balance or 0) + amount
        if card:
            card.current_balance = Decimal(card.current_balance or 0) - amount
        db.commit()
        db.refresh(outgoing)
        return outgoing

    tx_hash = original_hash(payload.account_id, tx_date, signed_amount, normalize_description(description))
    item = Transaction(
        user_id=user.id,
        original_hash=tx_hash,
        date=tx_date,
        value_date=value_date,
        source="manual",
        **payload.model_dump(exclude={"date", "value_date", "amount", "description", "transfer_account_id"}),
        amount=signed_amount,
        description=description,
    )
    db.add(item)
    account.current_balance = Decimal(account.current_balance or 0) + signed_amount
    if card:
        card.current_balance = Decimal(card.current_balance or 0) + signed_amount
    db.commit()
    db.refresh(item)
    return item


@router.get("/transactions/{item_id}")
def get_transaction(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ensure_owner(db, Transaction, item_id, user.id)


@router.patch("/transactions/{item_id}")
def update_transaction(item_id: int, payload: TransactionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ensure_owner(db, Transaction, item_id, user.id)
    if item.source == "investment":
        raise HTTPException(status_code=409, detail="Edit this transaction from Investments so the holding stays in sync")
    if item.is_transfer or payload.type == "transfer":
        raise HTTPException(status_code=409, detail="Transfer editing is not available yet. Delete and recreate the transfer.")
    ensure_owner(db, Bank, payload.bank_id, user.id)
    old_account = ensure_owner(db, Account, item.account_id, user.id)
    new_account = ensure_account_bank(db, payload.account_id, payload.bank_id, user.id)
    old_card = ensure_owner(db, Card, item.card_id, user.id) if item.card_id else None
    new_card = ensure_card_account(db, payload.card_id, payload.account_id, user.id)
    ensure_category_access(db, payload.category_id, user.id)
    data = payload.model_dump()
    try:
        data["date"] = date.fromisoformat(data["date"])
        data["value_date"] = date.fromisoformat(data["value_date"]) if data.get("value_date") else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Transaction date must be a valid YYYY-MM-DD date")
    data["amount"] = signed_transaction_amount(payload)
    data["description"] = str(data.get("description") or "").strip() or "Manual transaction"
    data.pop("transfer_account_id", None)
    old_account.current_balance = Decimal(old_account.current_balance or 0) - Decimal(item.amount or 0)
    new_account.current_balance = Decimal(new_account.current_balance or 0) + Decimal(data["amount"])
    if old_card:
        old_card.current_balance = Decimal(old_card.current_balance or 0) - Decimal(item.amount or 0)
    if new_card:
        new_card.current_balance = Decimal(new_card.current_balance or 0) + Decimal(data["amount"])
    data["original_hash"] = original_hash(
        payload.account_id,
        data["date"],
        data["amount"],
        normalize_description(data["description"]),
    )
    update_fields(item, data)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/transactions/{item_id}")
def delete_transaction(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ensure_owner(db, Transaction, item_id, user.id)
    if item.source == "investment":
        raise HTTPException(status_code=409, detail="Delete this transaction from Investments so the holding stays in sync")
    items = [item]
    if item.is_transfer and item.transfer_group_id:
        items = db.query(Transaction).filter_by(
            user_id=user.id,
            transfer_group_id=item.transfer_group_id,
            is_transfer=True,
        ).all()
    for row in items:
        account = ensure_owner(db, Account, row.account_id, user.id)
        account.current_balance = Decimal(account.current_balance or 0) - Decimal(row.amount or 0)
        if row.card_id:
            card = ensure_owner(db, Card, row.card_id, user.id)
            card.current_balance = Decimal(card.current_balance or 0) - Decimal(row.amount or 0)
        db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("/transactions/bulk-update")
def bulk_update(ids: list[int], category_id: int | None = Query(default=None), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(Transaction).filter(Transaction.user_id == user.id, Transaction.id.in_(ids)).update(
        {"category_id": category_id}, synchronize_session=False
    )
    db.commit()
    return {"updated": len(ids)}


@router.get("/reports/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return build_dashboard_report(db, user.id)


@router.get("/reports/forecast")
def cashflow_forecast(
    months: int = Query(default=3, ge=3, le=6),
    bank_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    first_month = today.replace(day=1)
    final_month = add_calendar_months(first_month, months - 1)
    forecast_end = final_month.replace(day=monthrange(final_month.year, final_month.month)[1])
    account_query = db.query(Account).filter_by(user_id=user.id, is_active=True)
    if bank_id is not None:
        ensure_owner(db, Bank, bank_id, user.id)
        account_query = account_query.filter(Account.bank_id == bank_id)
    accounts = account_query.all()
    account_ids = [account.id for account in accounts]
    starting_balance = sum(Decimal(account.current_balance or 0) for account in accounts)
    currency = accounts[0].currency if accounts else "EUR"
    recurring_query = db.query(RecurringPayment).filter_by(user_id=user.id, is_active=True)
    if bank_id is not None:
        recurring_query = recurring_query.filter(RecurringPayment.account_id.in_(account_ids))
    recurring = recurring_query.order_by(RecurringPayment.next_due_date).all()
    buckets = {
        add_calendar_months(first_month, offset).strftime("%Y-%m"): {
            "income": Decimal("0"),
            "expenses": Decimal("0"),
            "items": [],
        }
        for offset in range(months)
    }
    income_kinds = {"income", "revenue", "salary"}
    for item in recurring:
        is_income = item.kind.lower() in income_kinds
        for occurrence in recurring_occurrences(item.next_due_date, item.frequency, today, forecast_end):
            bucket = buckets[occurrence.strftime("%Y-%m")]
            amount = abs(Decimal(item.amount or 0))
            if is_income:
                bucket["income"] += amount
            else:
                bucket["expenses"] += amount
            bucket["items"].append({
                "id": item.id,
                "name": item.name,
                "date": occurrence,
                "amount": amount,
                "flow": "income" if is_income else "expense",
                "frequency": item.frequency,
            })

    running_balance = starting_balance
    result = []
    for month, bucket in buckets.items():
        net = bucket["income"] - bucket["expenses"]
        running_balance += net
        result.append({
            "month": month,
            "income": bucket["income"],
            "expenses": bucket["expenses"],
            "net": net,
            "ending_balance": running_balance,
            "items": sorted(bucket["items"], key=lambda entry: entry["date"]),
        })
    total_income = sum((bucket["income"] for bucket in buckets.values()), Decimal("0"))
    total_expenses = sum((bucket["expenses"] for bucket in buckets.values()), Decimal("0"))
    return {
        "months": months,
        "currency": currency,
        "starting_balance": starting_balance,
        "projected_income": total_income,
        "projected_expenses": total_expenses,
        "projected_change": total_income - total_expenses,
        "ending_balance": running_balance,
        "timeline": result,
    }


@router.get("/reports/cashflow")
def cashflow_report(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    monthly = defaultdict(lambda: {"income": Decimal("0"), "expenses": Decimal("0")})
    transactions = db.query(Transaction).filter_by(user_id=user.id).order_by(Transaction.date).all()
    for transaction in transactions:
        bucket = monthly[transaction.date.strftime("%Y-%m")]
        amount = Decimal(transaction.amount or 0)
        if amount >= 0:
            bucket["income"] += amount
        else:
            bucket["expenses"] += abs(amount)
    return {
        "months": [
            {"month": month, **values, "net": values["income"] - values["expenses"]}
            for month, values in list(monthly.items())[-12:]
        ]
    }


@router.get("/reports/category-spending")
def category_spending_report(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    category_names = {
        category.id: category.name
        for category in db.query(Category).filter(or_(Category.user_id == user.id, Category.user_id.is_(None))).all()
    }
    totals = defaultdict(lambda: Decimal("0"))
    month_start = date.today().replace(day=1)
    transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.date >= month_start,
        Transaction.amount < 0,
    ).all()
    for transaction in transactions:
        totals[category_names.get(transaction.category_id, "Uncategorized")] += abs(Decimal(transaction.amount))
    return {
        "categories": [
            {"name": name, "amount": amount}
            for name, amount in sorted(totals.items(), key=lambda item: item[1], reverse=True)
        ]
    }


@router.get("/reports/net-worth")
def net_worth_report(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = dashboard(db, user)
    return {
        "net_worth": data["net_worth"],
        "breakdown": [
            {"name": "Cash and accounts", "amount": data["total_liquidity"]},
            {"name": "Investments", "amount": data["total_investments"]},
            {"name": "Insurance cover", "amount": data["insurance_value"]},
            {"name": "Debt", "amount": -data["total_debt"]},
        ],
    }


@router.get("/reports/investments")
def investment_report(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(Holding, Asset, Portfolio)
        .join(Asset, Asset.id == Holding.asset_id)
        .join(Portfolio, Portfolio.id == Holding.portfolio_id)
        .filter(Holding.user_id == user.id)
        .all()
    )
    return {
        "holdings": [
            {
                "id": holding.id,
                "portfolio": portfolio.name,
                "symbol": asset.symbol,
                "name": asset.name,
                "quantity": holding.quantity,
                "average_price": holding.average_price,
                "current_price": holding.current_price,
                "value": Decimal(holding.quantity) * Decimal(holding.current_price),
                "cost": Decimal(holding.quantity) * Decimal(holding.average_price),
                "currency": asset.currency,
            }
            for holding, asset, portfolio in rows
        ]
    }


@router.get("/reports/insurance")
def insurance_report(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    policies = db.query(InsurancePolicy).filter_by(user_id=user.id, is_active=True).all()
    frequency_multiplier = {"monthly": 12, "quarterly": 4, "yearly": 1, "annual": 1}
    return {
        "total_cover": sum(Decimal(policy.insured_amount or 0) for policy in policies),
        "annual_premiums": sum(
            Decimal(policy.premium_amount or 0) * frequency_multiplier.get(policy.premium_frequency, 1)
            for policy in policies
        ),
        "active_policies": len(policies),
    }


def create_generic(model, payload: GenericCreate, db: Session, user: User):
    data = payload.data.copy()
    item = model(user_id=user.id, **data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/investments/portfolios")
def portfolios(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Portfolio).filter_by(user_id=user.id).all()


@router.post("/investments/portfolios")
def create_portfolio(payload: GenericCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return create_generic(Portfolio, payload, db, user)


@router.patch("/investments/portfolios/{item_id}")
def update_portfolio(item_id: int, payload: GenericCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ensure_owner(db, Portfolio, item_id, user.id)
    if payload.data.get("broker_account_id"):
        ensure_owner(db, Account, int(payload.data["broker_account_id"]), user.id)
    update_fields(item, payload.data)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/investments/portfolios/{item_id}")
def delete_portfolio(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ensure_owner(db, Portfolio, item_id, user.id)
    if db.query(InvestmentTransaction).filter_by(user_id=user.id, portfolio_id=item.id).first():
        raise HTTPException(status_code=409, detail="Delete this portfolio's investment activity first")
    db.query(Holding).filter_by(user_id=user.id, portfolio_id=item.id).delete(synchronize_session=False)
    db.query(InvestmentSummary).filter_by(user_id=user.id, portfolio_id=item.id).delete(synchronize_session=False)
    db.delete(item)
    db.commit()
    return {"ok": True}


def investment_summary_response(portfolio: Portfolio, summary: InvestmentSummary | None):
    total_invested = Decimal(summary.total_invested or 0) if summary else Decimal("0")
    net_invested = Decimal(summary.net_invested or 0) if summary else Decimal("0")
    worth_today = Decimal(summary.worth_today or 0) if summary else Decimal("0")
    withdrawn = total_invested - net_invested
    profit_loss = worth_today - net_invested
    profit_percent = (profit_loss / net_invested * 100) if net_invested else Decimal("0")
    return {
        "portfolio_id": portfolio.id,
        "portfolio_name": portfolio.name,
        "currency": portfolio.currency,
        "total_invested": total_invested,
        "withdrawn": withdrawn,
        "net_invested": net_invested,
        "worth_today": worth_today,
        "profit_loss": profit_loss,
        "profit_percent": profit_percent,
    }


@router.get("/investments/summaries")
def investment_summaries(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    portfolios = db.query(Portfolio).filter_by(user_id=user.id).order_by(Portfolio.id).all()
    summaries = {
        item.portfolio_id: item
        for item in db.query(InvestmentSummary).filter_by(user_id=user.id).all()
    }
    return [investment_summary_response(portfolio, summaries.get(portfolio.id)) for portfolio in portfolios]


@router.put("/investments/portfolios/{item_id}/summary")
def update_investment_summary(
    item_id: int,
    payload: GenericCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    portfolio = ensure_owner(db, Portfolio, item_id, user.id)
    try:
        total_invested = Decimal(str(payload.data["total_invested"]))
        net_invested = Decimal(str(payload.data["net_invested"]))
        worth_today = Decimal(str(payload.data["worth_today"]))
    except (KeyError, ValueError, TypeError, InvalidOperation):
        raise HTTPException(status_code=422, detail="Total invested, total minus withdrawn, and worth today are required")
    if min(total_invested, net_invested, worth_today) < 0:
        raise HTTPException(status_code=422, detail="Investment values cannot be negative")
    if net_invested > total_invested:
        raise HTTPException(status_code=422, detail="Total minus withdrawn cannot exceed total invested")
    summary = db.query(InvestmentSummary).filter_by(user_id=user.id, portfolio_id=portfolio.id).first()
    if not summary:
        summary = InvestmentSummary(user_id=user.id, portfolio_id=portfolio.id)
        db.add(summary)
    summary.total_invested = total_invested
    summary.net_invested = net_invested
    summary.worth_today = worth_today
    db.commit()
    db.refresh(summary)
    return investment_summary_response(portfolio, summary)


@router.get("/investments/assets")
def assets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Asset).order_by(Asset.symbol).all()


@router.post("/investments/assets")
def create_asset(payload: GenericCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = Asset(**payload.data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/investments/holdings")
def holdings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Holding).filter_by(user_id=user.id).all()


def rebuild_holding(db: Session, user_id: int, portfolio_id: int, asset_id: int) -> None:
    rows = (
        db.query(InvestmentTransaction)
        .filter_by(user_id=user_id, portfolio_id=portfolio_id, asset_id=asset_id)
        .order_by(InvestmentTransaction.date, InvestmentTransaction.id)
        .all()
    )
    holding = db.query(Holding).filter_by(user_id=user_id, portfolio_id=portfolio_id, asset_id=asset_id).first()
    if not rows:
        if holding:
            db.delete(holding)
        return
    quantity = Decimal("0")
    average_price = Decimal("0")
    current_price = Decimal("0")
    for row in rows:
        row_quantity = Decimal(row.quantity or 0)
        row_price = Decimal(row.price or 0)
        if row.type == "buy":
            new_quantity = quantity + row_quantity
            average_price = ((quantity * average_price) + (row_quantity * row_price)) / new_quantity
            quantity = new_quantity
        else:
            if row_quantity > quantity:
                raise HTTPException(status_code=422, detail="Investment activity would sell more units than are held")
            quantity -= row_quantity
        current_price = row_price
    if not holding:
        holding = Holding(user_id=user_id, portfolio_id=portfolio_id, asset_id=asset_id)
        db.add(holding)
    holding.quantity = quantity
    holding.average_price = average_price
    holding.current_price = current_price


@router.get("/investments/transactions")
def investment_transactions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(InvestmentTransaction).filter_by(user_id=user.id).order_by(
        InvestmentTransaction.date.desc(), InvestmentTransaction.id.desc()
    ).all()
    linked_ids = [row.linked_transaction_id for row in rows if row.linked_transaction_id]
    linked = {
        transaction.id: transaction
        for transaction in db.query(Transaction).filter(Transaction.id.in_(linked_ids)).all()
    } if linked_ids else {}
    return [
        {
            "id": row.id,
            "portfolio_id": row.portfolio_id,
            "asset_id": row.asset_id,
            "account_id": linked.get(row.linked_transaction_id).account_id if linked.get(row.linked_transaction_id) else None,
            "date": row.date,
            "type": row.type,
            "quantity": row.quantity,
            "price": row.price,
            "fees": row.fees,
            "taxes": row.taxes,
            "currency": row.currency,
        }
        for row in rows
    ]


@router.post("/investments/transactions")
def create_investment_transaction(payload: GenericCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = payload.data.copy()
    try:
        portfolio_id = int(data["portfolio_id"])
        asset_id = int(data["asset_id"])
        account_id = int(data["account_id"])
        transaction_type = str(data["type"]).lower()
        quantity = Decimal(str(data["quantity"]))
        price = Decimal(str(data["price"]))
        transaction_date = date.fromisoformat(str(data["date"]))
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Portfolio, asset, funding account, date, quantity, and price are required")
    ensure_owner(db, Portfolio, portfolio_id, user.id)
    funding_account = ensure_owner(db, Account, account_id, user.id)
    asset = db.query(Asset).filter_by(id=asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if transaction_type not in {"buy", "sell"} or quantity <= 0 or price < 0:
        raise HTTPException(status_code=422, detail="Use a positive quantity and price, with type buy or sell")

    item = InvestmentTransaction(
        user_id=user.id,
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        date=transaction_date,
        type=transaction_type,
        quantity=quantity,
        price=price,
        fees=Decimal(str(data.get("fees", 0))),
        taxes=Decimal(str(data.get("taxes", 0))),
        currency=str(data.get("currency", "EUR")),
    )
    holding = db.query(Holding).filter_by(user_id=user.id, portfolio_id=portfolio_id, asset_id=asset_id).first()
    if not holding:
        holding = Holding(user_id=user.id, portfolio_id=portfolio_id, asset_id=asset_id)
        db.add(holding)
    old_quantity = Decimal(holding.quantity or 0)
    if transaction_type == "buy":
        new_quantity = old_quantity + quantity
        old_cost = old_quantity * Decimal(holding.average_price or 0)
        holding.average_price = (old_cost + quantity * price) / new_quantity
        holding.quantity = new_quantity
    else:
        if quantity > old_quantity:
            raise HTTPException(status_code=422, detail="You cannot sell more units than you hold")
        holding.quantity = old_quantity - quantity
    holding.current_price = price
    trade_currency = str(data.get("currency", "EUR")).upper()
    fees = Decimal(str(data.get("fees", 0)))
    taxes = Decimal(str(data.get("taxes", 0)))
    gross = quantity * price
    trade_cash = gross + fees + taxes if transaction_type == "buy" else gross - fees - taxes
    exchange_rate = get_exchange_rate(trade_currency, funding_account.currency)
    account_cash = trade_cash * exchange_rate
    signed_cash = -account_cash if transaction_type == "buy" else account_cash
    action = "Investment purchase" if transaction_type == "buy" else "Investment sale"
    category = db.query(Category).filter_by(user_id=None, name="Buy" if transaction_type == "buy" else "Sell", type="investment").first()
    cash_transaction = Transaction(
        user_id=user.id,
        bank_id=funding_account.bank_id,
        account_id=funding_account.id,
        date=transaction_date,
        description=f"{action}: {asset.symbol}",
        amount=signed_cash,
        currency=funding_account.currency,
        original_amount=-trade_cash if transaction_type == "buy" else trade_cash,
        original_currency=trade_currency,
        exchange_rate=exchange_rate,
        type="investment",
        category_id=category.id if category else None,
        source="investment",
        original_hash=sha256(f"investment:{user.id}:{uuid4().hex}".encode()).hexdigest(),
    )
    db.add(cash_transaction)
    db.flush()
    item.linked_transaction_id = cash_transaction.id
    funding_account.current_balance = Decimal(funding_account.current_balance or 0) + signed_cash
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/investments/transactions/{item_id}")
def update_investment_transaction(item_id: int, payload: GenericCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ensure_owner(db, InvestmentTransaction, item_id, user.id)
    data = payload.data.copy()
    try:
        portfolio_id = int(data["portfolio_id"])
        asset_id = int(data.get("asset_id", item.asset_id))
        account_id = int(data["account_id"])
        transaction_type = str(data["type"]).lower()
        quantity = Decimal(str(data["quantity"]))
        price = Decimal(str(data["price"]))
        transaction_date = date.fromisoformat(str(data["date"]))
        fees = Decimal(str(data.get("fees", 0)))
        taxes = Decimal(str(data.get("taxes", 0)))
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Portfolio, funding account, date, quantity, and price are required")
    ensure_owner(db, Portfolio, portfolio_id, user.id)
    funding_account = ensure_owner(db, Account, account_id, user.id)
    asset = db.query(Asset).filter_by(id=asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if transaction_type not in {"buy", "sell"} or quantity <= 0 or price < 0:
        raise HTTPException(status_code=422, detail="Use a positive quantity and price, with type buy or sell")

    old_pair = (item.portfolio_id, item.asset_id)
    linked = db.query(Transaction).filter_by(id=item.linked_transaction_id, user_id=user.id).first() if item.linked_transaction_id else None
    if linked:
        old_account = ensure_owner(db, Account, linked.account_id, user.id)
        old_account.current_balance = Decimal(old_account.current_balance or 0) - Decimal(linked.amount or 0)

    trade_currency = str(data.get("currency", item.currency or "EUR")).upper()
    gross = quantity * price
    trade_cash = gross + fees + taxes if transaction_type == "buy" else gross - fees - taxes
    exchange_rate = get_exchange_rate(trade_currency, funding_account.currency)
    signed_cash = -(trade_cash * exchange_rate) if transaction_type == "buy" else trade_cash * exchange_rate
    category = db.query(Category).filter_by(user_id=None, name="Buy" if transaction_type == "buy" else "Sell", type="investment").first()
    if not linked:
        linked = Transaction(
            user_id=user.id,
            original_hash=sha256(f"investment:{user.id}:{uuid4().hex}".encode()).hexdigest(),
            source="investment",
        )
        db.add(linked)
    linked.bank_id = funding_account.bank_id
    linked.account_id = funding_account.id
    linked.card_id = None
    linked.date = transaction_date
    linked.description = f"{'Investment purchase' if transaction_type == 'buy' else 'Investment sale'}: {asset.symbol}"
    linked.amount = signed_cash
    linked.currency = funding_account.currency
    linked.original_amount = -trade_cash if transaction_type == "buy" else trade_cash
    linked.original_currency = trade_currency
    linked.exchange_rate = exchange_rate
    linked.type = "investment"
    linked.category_id = category.id if category else None
    if not item.linked_transaction_id:
        db.flush()
        item.linked_transaction_id = linked.id
    funding_account.current_balance = Decimal(funding_account.current_balance or 0) + signed_cash

    item.portfolio_id = portfolio_id
    item.asset_id = asset_id
    item.date = transaction_date
    item.type = transaction_type
    item.quantity = quantity
    item.price = price
    item.fees = fees
    item.taxes = taxes
    item.currency = trade_currency
    db.flush()
    rebuild_holding(db, user.id, old_pair[0], old_pair[1])
    if old_pair != (portfolio_id, asset_id):
        rebuild_holding(db, user.id, portfolio_id, asset_id)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/investments/transactions/{item_id}")
def delete_investment_transaction(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ensure_owner(db, InvestmentTransaction, item_id, user.id)
    portfolio_id, asset_id = item.portfolio_id, item.asset_id
    linked = db.query(Transaction).filter_by(id=item.linked_transaction_id, user_id=user.id).first() if item.linked_transaction_id else None
    if linked:
        account = ensure_owner(db, Account, linked.account_id, user.id)
        account.current_balance = Decimal(account.current_balance or 0) - Decimal(linked.amount or 0)
        db.delete(linked)
    db.delete(item)
    db.flush()
    rebuild_holding(db, user.id, portfolio_id, asset_id)
    db.commit()
    return {"ok": True}


@router.get("/insurance/policies")
def policies(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(InsurancePolicy).filter_by(user_id=user.id, is_active=True).all()


@router.post("/insurance/policies")
def create_policy(payload: GenericCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = payload.data.copy()
    for field in ("start_date", "end_date"):
        if data.get(field):
            try:
                data[field] = date.fromisoformat(str(data[field]))
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid {field.replace('_', ' ')}")
        else:
            data[field] = None
    if data.get("linked_account_id"):
        ensure_owner(db, Account, int(data["linked_account_id"]), user.id)
        data["linked_account_id"] = int(data["linked_account_id"])
    try:
        return create_generic(InsurancePolicy, GenericCreate(data=data), db, user)
    except TypeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid policy details: {exc}")


@router.patch("/insurance/policies/{item_id}")
def update_policy(item_id: int, payload: GenericCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ensure_owner(db, InsurancePolicy, item_id, user.id)
    update_fields(item, payload.data)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/insurance/policies/{item_id}")
def archive_policy(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ensure_owner(db, InsurancePolicy, item_id, user.id)
    item.is_active = False
    db.commit()
    return {"ok": True}


@router.get("/insurance/payments")
def payments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(InsurancePayment).filter_by(user_id=user.id).all()


@router.post("/insurance/payments")
def create_payment(payload: GenericCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = payload.data.copy()
    policy_id = int(data.get("policy_id", 0))
    ensure_owner(db, InsurancePolicy, policy_id, user.id)
    try:
        data["due_date"] = date.fromisoformat(str(data["due_date"]))
        data["paid_date"] = date.fromisoformat(str(data["paid_date"])) if data.get("paid_date") else None
    except (KeyError, ValueError):
        raise HTTPException(status_code=422, detail="A valid due date is required")
    return create_generic(InsurancePayment, GenericCreate(data=data), db, user)
