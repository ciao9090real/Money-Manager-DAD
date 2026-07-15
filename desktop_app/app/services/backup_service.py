from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from app.core.paths import backup_dir, database_path, ensure_app_dirs
from app.core.migrations import SCHEMA_VERSION, assert_database_integrity, migrate
from app.utils.dates import timestamp_for_filename


class BackupService:
    DAILY_RETENTION = 14

    def __init__(self, db: sqlite3.Connection, db_path: Path | None = None):
        self.db = db
        self.db_path = db_path or database_path()

    def create_backup(self) -> Path:
        ensure_app_dirs()
        target = backup_dir() / f"money_manager_backup_{timestamp_for_filename()}.db"
        self._write_backup(target)
        return target

    def ensure_daily_backup(self, retention: int = DAILY_RETENTION) -> Path | None:
        """Create at most one verified automatic backup per local calendar day."""
        ensure_app_dirs()
        target = backup_dir() / f"money_manager_daily_{date.today():%Y%m%d}.db"
        if target.exists():
            existing = self._open_source(target)
            try:
                assert_database_integrity(existing)
            except Exception:
                existing.close()
                target.unlink(missing_ok=True)
            else:
                existing.close()
                return None
        self._write_backup(target)
        self._rotate("money_manager_daily_", retention)
        return target

    def restore_backup(self, source: Path) -> Path:
        """Restore a verified SQLite backup and retain a rollback copy."""
        ensure_app_dirs()
        source = Path(source).expanduser().resolve()
        if not source.is_file():
            raise ValueError("Choose an existing Money Manager backup")
        if source == self.db_path.expanduser().resolve():
            raise ValueError("The active database cannot be restored over itself")
        if self.db.in_transaction:
            raise RuntimeError("Cannot restore while a database operation is in progress")

        candidate = self._open_source(source)
        try:
            assert_database_integrity(candidate)
            source_version = int(candidate.execute("PRAGMA user_version").fetchone()[0])
            if source_version > SCHEMA_VERSION:
                raise ValueError(
                    f"This backup needs a newer app (schema {source_version})"
                )
        finally:
            candidate.close()

        rollback = backup_dir() / (
            f"money_manager_before_restore_{timestamp_for_filename()}.db"
        )
        self._write_backup(rollback)
        try:
            self._restore_from(source)
        except Exception:
            self._restore_from(rollback)
            raise
        return rollback

    def _write_backup(self, target: Path) -> None:
        if self.db.in_transaction:
            raise RuntimeError("Cannot back up while a database operation is in progress")
        assert_database_integrity(self.db)
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

    def _restore_from(self, source: Path) -> None:
        candidate = self._open_source(source)
        try:
            candidate.backup(self.db)
        finally:
            candidate.close()
        self.db.execute("PRAGMA foreign_keys = ON")
        migrate(self.db)
        assert_database_integrity(self.db)

    @staticmethod
    def _open_source(source: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _rotate(prefix: str, retention: int) -> None:
        keep = max(1, int(retention))
        candidates = sorted(backup_dir().glob(f"{prefix}*.db"), reverse=True)
        for expired in candidates[keep:]:
            expired.unlink(missing_ok=True)
