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

    def export_transactions_csv(self) -> Path:
        ensure_app_dirs()
        target = export_dir() / f"transactions_{timestamp_for_filename()}.csv"
        rows = self.db.execute(
            """
            SELECT t.date, t.type, a.name AS account, t.amount_cents, t.description, t.notes
            FROM transactions t
            JOIN accounts a ON a.id = t.account_id
            WHERE t.deleted_at IS NULL AND a.deleted_at IS NULL
            ORDER BY t.date DESC, t.id DESC
            """
        ).fetchall()
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["date", "type", "account", "amount", "description", "notes"])
            for row in rows:
                writer.writerow(
                    [
                        row["date"],
                        row["type"],
                        row["account"],
                        str(cents_to_decimal(row["amount_cents"])),
                        row["description"],
                        row["notes"],
                    ]
                )
        return target
