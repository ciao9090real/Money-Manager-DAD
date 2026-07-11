from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.migrations import migrate
from app.core.paths import database_path, ensure_app_dirs


def connect(path: Path | None = None) -> sqlite3.Connection:
    ensure_app_dirs()
    db_path = path or database_path()
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    return connection

