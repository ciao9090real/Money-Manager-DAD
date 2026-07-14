from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from app.core.migrations import assert_database_integrity, migrate
from app.core.paths import database_path, ensure_app_dirs


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open one application connection.

    Call this function separately in every worker thread.  sqlite3's default
    thread check intentionally remains enabled so a UI connection cannot be
    reused accidentally by a report or synchronization worker.
    """
    ensure_app_dirs()
    db_path = path or database_path()
    connection = sqlite3.connect(db_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA busy_timeout = 10000")
    migrate(connection)
    connection.execute("PRAGMA optimize")
    assert_database_integrity(connection)
    return connection


@contextmanager
def unit_of_work(connection: sqlite3.Connection):
    """Commit a complete service operation once or roll it back completely."""
    if connection.in_transaction:
        savepoint = f"uow_{uuid4().hex}"
        connection.execute(f"SAVEPOINT {savepoint}")
        try:
            yield
        except Exception:
            connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            raise
        else:
            connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        return

    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
