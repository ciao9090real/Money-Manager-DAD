from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.paths import backup_dir, database_path, ensure_app_dirs
from app.core.migrations import assert_database_integrity
from app.utils.dates import timestamp_for_filename


class BackupService:
    def __init__(self, db: sqlite3.Connection, db_path: Path | None = None):
        self.db = db
        self.db_path = db_path or database_path()

    def create_backup(self) -> Path:
        ensure_app_dirs()
        if self.db.in_transaction:
            raise RuntimeError("Cannot back up while a database operation is in progress")
        assert_database_integrity(self.db)
        target = backup_dir() / f"money_manager_backup_{timestamp_for_filename()}.db"
        destination = sqlite3.connect(target)
        try:
            self.db.backup(destination)
            destination.execute("PRAGMA foreign_keys = ON")
            assert_database_integrity(destination)
        except Exception:
            destination.close()
            target.unlink(missing_ok=True)
            raise
        else:
            destination.close()
        return target
