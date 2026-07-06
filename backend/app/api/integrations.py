from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Account, Asset, Card, Holding, RecurringPayment, User
from app.schemas import GenericCreate, RecurringPaymentIn
from app.services.market import get_quote
from app.services.notifications import reminder_is_due, send_payment_reminder


router = APIRouter()


def owned(db: Session, model, object_id: int, user_id: int):
    item = db.query(model).filter(model.id == object_id, model.user_id == user_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item


def validate_payment_links(db: Session, user_id: int, account_id: int | None, card_id: int | None) -> None:
    account = owned(db, Account, account_id, user_id) if account_id else None
    card = owned(db, Card, card_id, user_id) if card_id else None
    if card and account and card.account_id != account.id:
        raise HTTPException(status_code=422, detail="The selected card does not belong to the selected account")


@router.get("/market/quote/{symbol}")
def market_quote(symbol: str, user: User = Depends(get_current_user)):
    return get_quote(symbol)


@router.post("/investments/refresh-prices")
def refresh_prices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(Holding, Asset)
        .join(Asset, Asset.id == Holding.asset_id)
        .filter(Holding.user_id == user.id)
        .all()
    )
    updated = []
    errors = []
    for holding, asset in rows:
        try:
            quote = get_quote(asset.symbol)
            holding.current_price = quote["current"]
            updated.append({"symbol": asset.symbol, "price": quote["current"]})
        except HTTPException as exc:
            errors.append({"symbol": asset.symbol, "detail": exc.detail})
    db.commit()
    return {"updated": updated, "errors": errors}


@router.get("/recurring-payments")
def list_recurring_payments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(RecurringPayment)
        .filter_by(user_id=user.id, is_active=True)
        .order_by(RecurringPayment.next_due_date)
        .all()
    )


@router.post("/recurring-payments")
def create_recurring_payment(
    payload: RecurringPaymentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    validate_payment_links(db, user.id, payload.account_id, payload.card_id)
    item = RecurringPayment(user_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/recurring-payments/{item_id}")
def update_recurring_payment(
    item_id: int,
    payload: RecurringPaymentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = owned(db, RecurringPayment, item_id, user.id)
    validate_payment_links(db, user.id, payload.account_id, payload.card_id)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/recurring-payments/{item_id}")
def archive_recurring_payment(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = owned(db, RecurringPayment, item_id, user.id)
    item.is_active = False
    db.commit()
    return {"ok": True}


@router.post("/recurring-payments/send-due")
def send_due_reminders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    due = (
        db.query(RecurringPayment)
        .filter_by(user_id=user.id, is_active=True)
        .filter(RecurringPayment.kind.notin_(("income", "revenue", "salary")))
        .all()
    )
    sent = []
    for payment in due:
        if reminder_is_due(payment):
            message_id = send_payment_reminder(user, payment)
            payment.last_notified_at = datetime.now(timezone.utc)
            sent.append({"id": payment.id, "name": payment.name, "message_id": message_id})
    db.commit()
    return {"sent": sent, "count": len(sent)}
