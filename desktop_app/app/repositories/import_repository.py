from __future__ import annotations

import sqlite3
from decimal import Decimal
from uuid import uuid4

from app.models.import_inbox import (
    ImportBatch,
    ImportBatchSummary,
    ImportInboxRow,
)
from app.utils.money import cents_to_decimal, decimal_to_cents


UTC_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def _batch(row: sqlite3.Row) -> ImportBatch:
    return ImportBatch(
        id=row["id"],
        source_name=row["source_name"],
        source_hash=row["source_hash"],
        source_type=row["source_type"],
        sheet_name=row["sheet_name"],
        payment_method_id=row["payment_method_id"],
        period_start=row["period_start"],
        period_end=row["period_end"],
        mapping_json=row["mapping_json"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        revision=row["revision"],
    )


def _inbox_row(row: sqlite3.Row) -> ImportInboxRow:
    amount = (
        cents_to_decimal(row["amount_cents"])
        if row["amount_cents"] is not None
        else None
    )
    return ImportInboxRow(
        id=row["id"],
        batch_id=row["batch_id"],
        source_row_number=row["source_row_number"],
        raw_payload_json=row["raw_payload_json"],
        date=row["date"],
        transaction_type=row["transaction_type"],
        account_id=row["account_id"],
        target_account_id=row["target_account_id"],
        payment_method_id=row["payment_method_id"],
        category_id=row["category_id"],
        amount=amount,
        description=row["description"],
        notes=row["notes"],
        status=row["status"],
        issue_code=row["issue_code"],
        issue_text=row["issue_text"],
        duplicate_transaction_id=row["duplicate_transaction_id"],
        posted_transaction_id=row["posted_transaction_id"],
        fingerprint=row["fingerprint"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        revision=row["revision"],
    )


class ImportRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def create_batch(
        self,
        *,
        source_name: str,
        source_hash: str,
        source_type: str,
        sheet_name: str | None,
        payment_method_id: str | None,
        period_start: str | None,
        period_end: str | None,
        mapping_json: str,
    ) -> ImportBatch:
        batch_id = str(uuid4())
        self.db.execute(
            """
            INSERT INTO import_batches (
                id, source_name, source_hash, source_type, sheet_name,
                payment_method_id, period_start, period_end, mapping_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                source_name,
                source_hash,
                source_type,
                sheet_name,
                payment_method_id,
                period_start,
                period_end,
                mapping_json,
            ),
        )
        created = self.get_batch(batch_id)
        assert created is not None
        return created

    def create_row(
        self,
        *,
        batch_id: str,
        source_row_number: int,
        raw_payload_json: str,
        date: str | None,
        transaction_type: str | None,
        account_id: str | None,
        target_account_id: str | None,
        payment_method_id: str | None,
        category_id: str | None,
        amount: Decimal | None,
        description: str,
        notes: str | None,
        status: str,
        issue_code: str | None,
        issue_text: str | None,
        fingerprint: str | None,
    ) -> ImportInboxRow:
        row_id = str(uuid4())
        self.db.execute(
            """
            INSERT INTO import_rows (
                id, batch_id, source_row_number, raw_payload_json, date,
                transaction_type, account_id, target_account_id,
                payment_method_id, category_id, amount_cents, description,
                notes, status, issue_code, issue_text, fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_id,
                batch_id,
                int(source_row_number),
                raw_payload_json,
                date,
                transaction_type,
                account_id,
                target_account_id,
                payment_method_id,
                category_id,
                decimal_to_cents(amount) if amount is not None else None,
                description,
                notes,
                status,
                issue_code,
                issue_text,
                fingerprint,
            ),
        )
        created = self.get_row(row_id)
        assert created is not None
        return created

    def list_batches(self) -> list[ImportBatchSummary]:
        rows = self.db.execute(
            """
            SELECT b.*,
                   COUNT(r.id) AS total_count,
                   SUM(CASE WHEN r.status = 'ready' THEN 1 ELSE 0 END) AS ready_count,
                   SUM(CASE WHEN r.status = 'needs_category' THEN 1 ELSE 0 END)
                       AS needs_category_count,
                   SUM(CASE WHEN r.status = 'duplicate' THEN 1 ELSE 0 END)
                       AS duplicate_count,
                   SUM(CASE WHEN r.status = 'ignored' THEN 1 ELSE 0 END)
                       AS ignored_count,
                   SUM(CASE WHEN r.status = 'posted' THEN 1 ELSE 0 END)
                       AS posted_count,
                   SUM(CASE WHEN r.status = 'error' THEN 1 ELSE 0 END)
                       AS error_count
            FROM import_batches AS b
            LEFT JOIN import_rows AS r
              ON r.batch_id = b.id AND r.deleted_at IS NULL
            WHERE b.deleted_at IS NULL
            GROUP BY b.id
            ORDER BY b.status = 'review' DESC, b.created_at DESC, b.id DESC
            """
        ).fetchall()
        return [
            ImportBatchSummary(
                batch=_batch(row),
                total_count=int(row["total_count"] or 0),
                ready_count=int(row["ready_count"] or 0),
                needs_category_count=int(row["needs_category_count"] or 0),
                duplicate_count=int(row["duplicate_count"] or 0),
                ignored_count=int(row["ignored_count"] or 0),
                posted_count=int(row["posted_count"] or 0),
                error_count=int(row["error_count"] or 0),
            )
            for row in rows
        ]

    def get_batch(self, batch_id: str) -> ImportBatch | None:
        row = self.db.execute(
            """
            SELECT * FROM import_batches
            WHERE id = ? AND deleted_at IS NULL
            """,
            (batch_id,),
        ).fetchone()
        return _batch(row) if row else None

    def get_row(self, row_id: str) -> ImportInboxRow | None:
        row = self.db.execute(
            """
            SELECT * FROM import_rows
            WHERE id = ? AND deleted_at IS NULL
            """,
            (row_id,),
        ).fetchone()
        return _inbox_row(row) if row else None

    def list_rows(self, batch_id: str) -> list[ImportInboxRow]:
        return [
            _inbox_row(row)
            for row in self.db.execute(
                """
                SELECT * FROM import_rows
                WHERE batch_id = ? AND deleted_at IS NULL
                ORDER BY source_row_number, id
                """,
                (batch_id,),
            )
        ]

    def update_row(
        self,
        row_id: str,
        *,
        category_id: str | None,
        status: str,
        issue_code: str | None = None,
        issue_text: str | None = None,
        posted_transaction_id: str | None = None,
    ) -> ImportInboxRow:
        cursor = self.db.execute(
            f"""
            UPDATE import_rows
            SET category_id = ?, status = ?, issue_code = ?, issue_text = ?,
                posted_transaction_id = COALESCE(?, posted_transaction_id),
                updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (
                category_id,
                status,
                issue_code,
                issue_text,
                posted_transaction_id,
                row_id,
            ),
        )
        if cursor.rowcount != 1:
            raise ValueError("Import row not found")
        updated = self.get_row(row_id)
        assert updated is not None
        return updated

    def update_batch_status(self, batch_id: str, status: str) -> ImportBatch:
        cursor = self.db.execute(
            f"""
            UPDATE import_batches
            SET status = ?, updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NULL
            """,
            (status, batch_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("Import batch not found")
        updated = self.get_batch(batch_id)
        assert updated is not None
        return updated
