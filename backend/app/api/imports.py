from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.crud import ensure_owner
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Account, Bank, Card, ImportBatch, ImportedRow, ImportTemplate, Transaction, User
from app.schemas import ImportMapRequest
from app.services.imports import dumps, loads, normalize_row, read_statement_bytes


router = APIRouter()


@router.post("/imports/upload")
async def upload_import(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    filename = file.filename or "statement.csv"
    if not filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only CSV and XLSX files are supported")
    content = await file.read()
    rows = read_statement_bytes(filename, content)
    batch = ImportBatch(user_id=user.id, filename=filename, file_type=filename.rsplit(".", 1)[-1].lower(), total_rows=len(rows))
    db.add(batch)
    db.flush()
    for index, raw in enumerate(rows, start=1):
        db.add(ImportedRow(import_batch_id=batch.id, row_number=index, raw_data_json=dumps(raw)))
    db.commit()
    return {"batch_id": batch.id, "total_rows": len(rows), "columns": list(rows[0].keys()) if rows else []}


@router.get("/imports/{batch_id}/preview")
def preview_import(batch_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    batch = db.query(ImportBatch).filter_by(id=batch_id, user_id=user.id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    rows = db.query(ImportedRow).filter_by(import_batch_id=batch.id).order_by(ImportedRow.row_number).limit(50).all()
    return {"batch": batch, "rows": [{"id": row.id, "row_number": row.row_number, "raw": loads(row.raw_data_json), "parsed": loads(row.parsed_data_json), "status": row.status, "error": row.error_message} for row in rows]}


@router.post("/imports/{batch_id}/map")
def map_import(batch_id: int, payload: ImportMapRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    batch = db.query(ImportBatch).filter_by(id=batch_id, user_id=user.id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    ensure_owner(db, Bank, payload.bank_id, user.id)
    ensure_owner(db, Account, payload.account_id, user.id)
    batch.bank_id = payload.bank_id
    batch.account_id = payload.account_id
    batch.card_id = payload.card_id
    batch.status = "mapped"
    duplicate_count = 0
    error_count = 0
    rows = db.query(ImportedRow).filter_by(import_batch_id=batch.id).all()
    for row in rows:
        try:
            parsed = normalize_row(loads(row.raw_data_json), payload.account_id, payload.mapping, payload.date_format, payload.decimal_separator, payload.thousands_separator)
            existing = db.query(Transaction).filter_by(user_id=user.id, original_hash=parsed["original_hash"]).first()
            row.parsed_data_json = dumps(parsed)
            row.status = "duplicate" if existing else "ready"
            row.error_message = None
            duplicate_count += 1 if existing else 0
        except Exception as exc:
            row.status = "error"
            row.error_message = str(exc)
            error_count += 1
    batch.duplicate_rows = duplicate_count
    batch.error_rows = error_count
    if payload.save_template_name:
        db.add(
            ImportTemplate(
                user_id=user.id,
                bank_id=payload.bank_id,
                name=payload.save_template_name,
                file_type=batch.file_type,
                mapping_json=dumps(payload.mapping),
                date_column=payload.mapping.get("date"),
                value_date_column=payload.mapping.get("value_date"),
                description_column=payload.mapping.get("description"),
                amount_column=payload.mapping.get("amount"),
                debit_column=payload.mapping.get("debit"),
                credit_column=payload.mapping.get("credit"),
                currency_column=payload.mapping.get("currency"),
                balance_column=payload.mapping.get("balance"),
                date_format=payload.date_format,
                decimal_separator=payload.decimal_separator,
                thousands_separator=payload.thousands_separator,
            )
        )
    db.commit()
    return {"batch_id": batch.id, "ready_rows": len(rows) - duplicate_count - error_count, "duplicate_rows": duplicate_count, "error_rows": error_count}


@router.post("/imports/{batch_id}/confirm")
def confirm_import(batch_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    batch = db.query(ImportBatch).filter_by(id=batch_id, user_id=user.id).first()
    if not batch or not batch.bank_id or not batch.account_id:
        raise HTTPException(status_code=404, detail="Mapped import batch not found")
    account = ensure_owner(db, Account, batch.account_id, user.id)
    card = ensure_owner(db, Card, batch.card_id, user.id) if batch.card_id else None
    imported = 0
    for row in db.query(ImportedRow).filter_by(import_batch_id=batch.id, status="ready").all():
        parsed = loads(row.parsed_data_json)
        duplicate = db.query(Transaction).filter_by(user_id=user.id, original_hash=parsed["original_hash"]).first()
        if duplicate:
            row.status = "duplicate"
            batch.duplicate_rows += 1
            continue
        tx = Transaction(
            user_id=user.id,
            bank_id=batch.bank_id,
            account_id=batch.account_id,
            card_id=batch.card_id,
            date=date.fromisoformat(parsed["date"]),
            value_date=date.fromisoformat(parsed["value_date"]) if parsed.get("value_date") else None,
            description=parsed["description"],
            amount=parsed["amount"],
            currency=parsed["currency"],
            type=parsed["type"],
            source="import",
            import_batch_id=batch.id,
            original_hash=parsed["original_hash"],
        )
        db.add(tx)
        account.current_balance = Decimal(account.current_balance or 0) + Decimal(str(parsed["amount"]))
        if card:
            card.current_balance = Decimal(card.current_balance or 0) + Decimal(str(parsed["amount"]))
        db.flush()
        row.transaction_id = tx.id
        row.status = "imported"
        imported += 1
    batch.imported_rows = imported
    batch.status = "confirmed"
    db.commit()
    return {"batch_id": batch.id, "imported_rows": imported, "duplicate_rows": batch.duplicate_rows, "error_rows": batch.error_rows}


@router.delete("/imports/{batch_id}")
def cancel_import(batch_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    batch = db.query(ImportBatch).filter_by(id=batch_id, user_id=user.id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    if batch.status == "confirmed":
        raise HTTPException(status_code=400, detail="Confirmed imports cannot be cancelled")
    db.query(ImportedRow).filter_by(import_batch_id=batch.id).delete()
    db.delete(batch)
    db.commit()
    return {"ok": True}


@router.get("/imports/templates")
def list_templates(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(ImportTemplate).filter_by(user_id=user.id).order_by(ImportTemplate.name).all()


@router.post("/imports/templates")
def create_template(payload: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = ImportTemplate(user_id=user.id, **payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
