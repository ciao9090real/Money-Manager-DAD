from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict

from app.core.database import unit_of_work
from app.models.import_inbox import ImportBatch, ImportBatchSummary, ImportInboxRow
from app.repositories.category_repository import CategoryRepository
from app.repositories.import_repository import ImportRepository
from app.services.import_service import (
    ImportPreview,
    StatementImportPreview,
    TransactionImportRow,
)
from app.services.transaction_service import TransactionService
from app.utils.money import decimal_to_cents


class ImportInboxService:
    RESOLVED_STATUSES = {"posted", "ignored", "duplicate"}

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.imports = ImportRepository(db)
        self.categories = CategoryRepository(db)
        self.transactions = TransactionService(db)

    def stage_preview(self, preview: ImportPreview) -> ImportBatch:
        if not preview.rows and not preview.issues:
            raise ValueError("There are no statement rows to send to the inbox")
        source = preview.source.expanduser().resolve()
        if not source.is_file():
            raise ValueError("The source file is no longer available")
        digest = hashlib.sha256()
        with source.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        source_hash = digest.hexdigest()
        statement = (
            preview if isinstance(preview, StatementImportPreview) else None
        )
        mapping = (
            asdict(statement.mapping)
            if statement is not None and statement.mapping is not None
            else {}
        )
        source_type = (
            "bank_statement"
            if statement is not None
            else "money_manager_csv"
        )
        with unit_of_work(self.db):
            batch = self.imports.create_batch(
                source_name=source.name,
                source_hash=source_hash,
                source_type=source_type,
                sheet_name=statement.sheet_name if statement else None,
                payment_method_id=(
                    statement.payment_method_id if statement else None
                ),
                period_start=statement.period_start if statement else None,
                period_end=statement.period_end if statement else None,
                mapping_json=json.dumps(
                    mapping, sort_keys=True, separators=(",", ":")
                ),
            )
            for row in preview.rows:
                self._stage_row(batch.id, row)
            for issue in preview.issues:
                self.imports.create_row(
                    batch_id=batch.id,
                    source_row_number=issue.row_number,
                    raw_payload_json=json.dumps(
                        dict(issue.raw_payload),
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    date=None,
                    transaction_type=None,
                    account_id=None,
                    target_account_id=None,
                    payment_method_id=(
                        statement.payment_method_id if statement else None
                    ),
                    category_id=None,
                    amount=None,
                    description="",
                    notes=None,
                    status="error",
                    issue_code="parse_error",
                    issue_text=issue.message,
                    fingerprint=None,
                )
            return batch

    def list_batches(self) -> list[ImportBatchSummary]:
        return self.imports.list_batches()

    def list_rows(self, batch_id: str) -> list[ImportInboxRow]:
        self._batch(batch_id)
        return self.imports.list_rows(batch_id)

    def set_category(
        self, row_ids: list[str] | tuple[str, ...], category_id: str | None
    ) -> int:
        if not row_ids:
            return 0
        category = self.categories.get(category_id) if category_id else None
        if category_id and (not category or not category.is_active):
            raise ValueError("Choose an active category")
        changed = 0
        with unit_of_work(self.db):
            for row_id in row_ids:
                row = self._row(row_id)
                if row.status in self.RESOLVED_STATUSES:
                    continue
                if row.transaction_type not in {"income", "expense"}:
                    continue
                if category and category.type != row.transaction_type:
                    raise ValueError(
                        "Category type must match every selected transaction"
                    )
                status = "ready" if category else "needs_category"
                self.imports.update_row(
                    row.id,
                    category_id=category.id if category else None,
                    status=status,
                )
                changed += 1
        return changed

    def ignore_rows(self, row_ids: list[str] | tuple[str, ...]) -> int:
        changed = 0
        with unit_of_work(self.db):
            for row_id in row_ids:
                row = self._row(row_id)
                if row.status in self.RESOLVED_STATUSES:
                    continue
                self.imports.update_row(
                    row.id,
                    category_id=row.category_id,
                    status="ignored",
                    issue_code=row.issue_code,
                    issue_text=row.issue_text,
                )
                changed += 1
        return changed

    def restore_rows(self, row_ids: list[str] | tuple[str, ...]) -> int:
        changed = 0
        with unit_of_work(self.db):
            for row_id in row_ids:
                row = self._row(row_id)
                if row.status != "ignored":
                    continue
                if self._batch(row.batch_id).status != "review":
                    raise ValueError("This import batch is already closed")
                status = self._actionable_status(row)
                self.imports.update_row(
                    row.id,
                    category_id=row.category_id,
                    status=status,
                    issue_code=row.issue_code,
                    issue_text=row.issue_text,
                )
                changed += 1
        return changed

    def post_ready(
        self,
        batch_id: str,
        *,
        include_uncategorized: bool = False,
    ) -> int:
        batch = self._batch(batch_id)
        if batch.status != "review":
            raise ValueError("This import batch is already closed")
        candidates = self._postable_rows(
            batch_id, include_uncategorized=include_uncategorized
        )
        if not candidates:
            raise ValueError("There are no ready rows to post")
        with unit_of_work(self.db):
            for row in candidates:
                transaction_id = self._post_row(row)
                self.imports.update_row(
                    row.id,
                    category_id=row.category_id,
                    status="posted",
                    posted_transaction_id=transaction_id,
                )
            self._update_batch_completion(batch_id)
        return len(candidates)

    def postable_count(
        self,
        batch_id: str,
        *,
        include_uncategorized: bool = False,
    ) -> int:
        batch = self._batch(batch_id)
        if batch.status != "review":
            raise ValueError("This import batch is already closed")
        count = len(
            self._postable_rows(
                batch_id,
                include_uncategorized=include_uncategorized,
            )
        )
        if count == 0:
            raise ValueError("There are no ready rows to post")
        return count

    def cancel_batch(self, batch_id: str) -> None:
        batch = self._batch(batch_id)
        if batch.status != "review":
            raise ValueError("Only an open import can be cancelled")
        with unit_of_work(self.db):
            for row in self.imports.list_rows(batch_id):
                if row.status not in self.RESOLVED_STATUSES:
                    self.imports.update_row(
                        row.id,
                        category_id=row.category_id,
                        status="ignored",
                        issue_code=row.issue_code,
                        issue_text=row.issue_text,
                    )
            self.imports.update_batch_status(batch_id, "cancelled")

    def summary(self) -> dict[str, int]:
        batches = self.list_batches()
        open_batches = [item for item in batches if item.batch.status == "review"]
        return {
            "open_batches": len(open_batches),
            "ready": sum(item.ready_count for item in open_batches),
            "needs_category": sum(
                item.needs_category_count for item in open_batches
            ),
            "errors": sum(item.error_count for item in open_batches),
        }

    def _stage_row(self, batch_id: str, row: TransactionImportRow) -> None:
        if row.duplicate:
            status = "duplicate"
        elif row.transaction_type in {"income", "expense"} and not row.category_id:
            status = "needs_category"
        elif row.transaction_type == "transfer" and not row.target_account_id:
            status = "error"
        else:
            status = "ready"
        issue_code = "missing_target" if status == "error" else None
        issue_text = (
            "Choose a target account before posting this transfer"
            if status == "error"
            else None
        )
        canonical = "|".join(
            (
                row.date,
                row.transaction_type,
                row.account_id,
                row.target_account_id or "",
                str(decimal_to_cents(row.amount)),
                row.description.strip().casefold(),
            )
        )
        raw_payload = {
            "date": row.date,
            "type": row.transaction_type,
            "account": row.account_name,
            "target_account": row.target_account_name or "",
            "amount": str(row.amount),
            "description": row.description,
        }
        self.imports.create_row(
            batch_id=batch_id,
            source_row_number=row.row_number,
            raw_payload_json=json.dumps(
                raw_payload, sort_keys=True, separators=(",", ":")
            ),
            date=row.date,
            transaction_type=row.transaction_type,
            account_id=row.account_id,
            target_account_id=row.target_account_id,
            payment_method_id=row.payment_method_id,
            category_id=row.category_id,
            amount=row.amount,
            description=row.description,
            notes=row.notes,
            status=status,
            issue_code=issue_code,
            issue_text=issue_text,
            fingerprint=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )

    def _post_row(self, row: ImportInboxRow) -> str:
        if (
            not row.date
            or not row.transaction_type
            or not row.account_id
            or row.amount is None
        ):
            raise ValueError(f"Row {row.source_row_number} is incomplete")
        if row.transaction_type == "income":
            transaction = self.transactions.add_income(
                row.account_id,
                row.amount,
                row.date,
                row.description,
                category_id=row.category_id,
                payment_method_id=row.payment_method_id,
                notes=row.notes,
            )
            assert transaction.id is not None
            return transaction.id
        if row.transaction_type == "expense":
            transaction = self.transactions.add_expense(
                row.account_id,
                row.amount,
                row.date,
                row.description,
                category_id=row.category_id,
                payment_method_id=row.payment_method_id,
                notes=row.notes,
            )
            assert transaction.id is not None
            return transaction.id
        if not row.target_account_id:
            raise ValueError(
                f"Row {row.source_row_number} needs a target account"
            )
        outgoing, _incoming = self.transactions.add_transfer(
            row.account_id,
            row.target_account_id,
            row.amount,
            row.date,
            row.description,
            notes=row.notes,
        )
        assert outgoing.id is not None
        return outgoing.id

    def _postable_rows(
        self,
        batch_id: str,
        *,
        include_uncategorized: bool,
    ) -> list[ImportInboxRow]:
        return [
            row
            for row in self.imports.list_rows(batch_id)
            if row.status == "ready"
            or (
                include_uncategorized
                and row.status == "needs_category"
            )
        ]

    def _actionable_status(self, row: ImportInboxRow) -> str:
        if row.issue_code:
            return "error"
        if row.transaction_type in {"income", "expense"} and not row.category_id:
            return "needs_category"
        return "ready"

    def _update_batch_completion(self, batch_id: str) -> None:
        rows = self.imports.list_rows(batch_id)
        if rows and all(row.status in self.RESOLVED_STATUSES for row in rows):
            self.imports.update_batch_status(batch_id, "posted")

    def _batch(self, batch_id: str) -> ImportBatch:
        batch = self.imports.get_batch(batch_id)
        if not batch:
            raise ValueError("Import batch not found")
        return batch

    def _row(self, row_id: str) -> ImportInboxRow:
        row = self.imports.get_row(row_id)
        if not row:
            raise ValueError("Import row not found")
        return row
