from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from app.core.paths import ensure_app_dirs, export_dir
from app.utils.dates import timestamp_for_filename
from app.utils.money import cents_to_decimal


class ExportService:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def export_transactions_csv(self, target: Path | None = None) -> Path:
        ensure_app_dirs()
        target = Path(target) if target else (
            export_dir() / f"transactions_{timestamp_for_filename()}.csv"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        rows = self.db.execute(
            """
            SELECT
                t.date,
                CASE WHEN t.type = 'transfer_out' THEN 'transfer' ELSE t.type END AS type,
                a.name AS account,
                ABS(t.amount_cents) AS amount_cents,
                t.description,
                t.notes,
                c.name AS category,
                target_account.name AS target_account
            FROM transactions t
            JOIN accounts a ON a.id = t.account_id
            LEFT JOIN categories c ON c.id = t.category_id
            LEFT JOIN transactions transfer_pair
                ON transfer_pair.transfer_group_id = t.transfer_group_id
                AND transfer_pair.type = 'transfer_in'
                AND transfer_pair.deleted_at IS NULL
            LEFT JOIN accounts target_account ON target_account.id = transfer_pair.account_id
            WHERE t.deleted_at IS NULL AND a.deleted_at IS NULL
              AND t.type IN ('income', 'expense', 'transfer_out')
            ORDER BY t.date DESC, t.id DESC
            """
        ).fetchall()
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "date",
                    "type",
                    "account",
                    "amount",
                    "description",
                    "notes",
                    "category",
                    "target_account",
                ]
            )
            for row in rows:
                writer.writerow(
                    [
                        row["date"],
                        row["type"],
                        _spreadsheet_safe(row["account"]),
                        str(cents_to_decimal(row["amount_cents"])),
                        _spreadsheet_safe(row["description"]),
                        _spreadsheet_safe(row["notes"]),
                        _spreadsheet_safe(row["category"]),
                        _spreadsheet_safe(row["target_account"]),
                    ]
                )
        return target


def _spreadsheet_safe(value: object) -> str:
    """Prevent exported text from being interpreted as a spreadsheet formula."""
    text = str(value or "")
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text
