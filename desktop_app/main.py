from __future__ import annotations

import sqlite3
import sys

from PySide6.QtWidgets import QApplication

from app.core.app_info import APP_NAME, APP_VERSION
from app.core.database import connect
from app.services.backup_service import BackupService
from app.ui.main_window import MainWindow
from app.ui.styles import app_stylesheet


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyleSheet(app_stylesheet())
    db = connect()
    try:
        backup_error = None
        try:
            BackupService(db).ensure_daily_backup()
        except (OSError, RuntimeError, sqlite3.Error) as exc:
            backup_error = str(exc)
        window = MainWindow(db)
        window.show()
        if backup_error:
            window.show_status(f"Automatic backup failed: {backup_error}")
        return app.exec()
    finally:
        db.execute("PRAGMA optimize")
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
