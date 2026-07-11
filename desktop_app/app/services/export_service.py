from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from app.core.paths import ensure_app_dirs, export_dir
from app.utils.dates import timestamp_for_filename


class ExportService:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def export_transactions_csv(self) -> Path:
        ensure_app_dirs()
        target = export_dir() / f"transactions_{timestamp_for_filename()}.csv"
        rows = self.db.execute(
            """
            SELECT t.date, t.type, a.name AS account, t.amount, t.description, t.notes
            FROM transactions t
            JOIN accounts a ON a.id = t.account_id
            ORDER BY t.date DESC, t.id DESC
            """
        ).fetchall()
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["date", "type", "account", "amount", "description", "notes"])
            for row in rows:
                writer.writerow([row["date"], row["type"], row["account"], row["amount"], row["description"], row["notes"]])
        return target

