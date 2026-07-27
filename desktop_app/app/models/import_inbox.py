from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ImportBatch:
    id: str
    source_name: str
    source_hash: str
    source_type: str
    sheet_name: str | None
    payment_method_id: str | None
    period_start: str | None
    period_end: str | None
    mapping_json: str
    status: str
    created_at: str
    updated_at: str
    deleted_at: str | None
    revision: int


@dataclass(frozen=True)
class ImportInboxRow:
    id: str
    batch_id: str
    source_row_number: int
    raw_payload_json: str
    date: str | None
    transaction_type: str | None
    account_id: str | None
    target_account_id: str | None
    payment_method_id: str | None
    category_id: str | None
    amount: Decimal | None
    description: str
    notes: str | None
    status: str
    issue_code: str | None
    issue_text: str | None
    duplicate_transaction_id: str | None
    posted_transaction_id: str | None
    fingerprint: str | None
    created_at: str
    updated_at: str
    deleted_at: str | None
    revision: int


@dataclass(frozen=True)
class ImportBatchSummary:
    batch: ImportBatch
    total_count: int
    ready_count: int
    needs_category_count: int
    duplicate_count: int
    ignored_count: int
    posted_count: int
    error_count: int

    @property
    def unresolved_count(self) -> int:
        return self.ready_count + self.needs_category_count + self.error_count

    @property
    def resolved_count(self) -> int:
        return self.duplicate_count + self.ignored_count + self.posted_count
