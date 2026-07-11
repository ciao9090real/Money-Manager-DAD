from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from app.core.paths import backup_dir, database_path, ensure_app_dirs
from app.utils.dates import timestamp_for_filename


class BackupService:
    def __init__(self, db: sqlite3.Connection, db_path: Path | None = None):
        self.db = db
        self.db_path = db_path or database_path()

    def create_backup(self) -> Path:
        ensure_app_dirs()
        self.db.commit()
        target = backup_dir() / f"money_manager_backup_{timestamp_for_filename()}.db"
        shutil.copy2(self.db_path, target)
        return target

