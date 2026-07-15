from __future__ import annotations

import sqlite3


class SettingsRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def get(self, key: str, default: str = "") -> str:
        row = self.db.execute(
            "SELECT value FROM settings WHERE key = ? AND deleted_at IS NULL", (key,)
        ).fetchone()
        return str(row["value"]) if row else default

    def set(self, key: str, value: str) -> None:
        self.db.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                deleted_at = NULL,
                revision = settings.revision + 1
            """,
            (key, value),
        )
