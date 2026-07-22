from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.core.app_info import APP_NAME, APP_VERSION
from app.core.database import connect
from app.core.database_security import DB_ERROR_TYPES
from app.services.backup_service import BackupService
from app.services.auth_service import AuthService
from app.services.net_worth_service import NetWorthService
from app.ui.auth_dialogs import PasswordSetupDialog, UnlockDialog
from app.ui.main_window import MainWindow
from app.ui.styles import app_stylesheet


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyleSheet(app_stylesheet())
    db = connect()
    net_worth = None
    try:
        auth = AuthService(db)
        if auth.is_configured():
            if UnlockDialog(auth).exec() != UnlockDialog.DialogCode.Accepted:
                return 0
        elif PasswordSetupDialog(auth).exec() != PasswordSetupDialog.DialogCode.Accepted:
            return 0

        net_worth = NetWorthService(db)
        backup_error = None
        try:
            BackupService(db).ensure_daily_backup()
        except (OSError, RuntimeError, *DB_ERROR_TYPES) as exc:
            backup_error = str(exc)
        snapshot_error = None
        try:
            net_worth.record_snapshot()
        except (ValueError, *DB_ERROR_TYPES) as exc:
            snapshot_error = str(exc)
        window = None

        def lock_application() -> None:
            if window is None or not window.isVisible():
                return
            window.hide()
            unlock = UnlockDialog(auth)
            if unlock.exec() == UnlockDialog.DialogCode.Accepted:
                window.showNormal()
                window.raise_()
                window.activateWindow()
            else:
                window.close()
                app.quit()

        window = MainWindow(
            db,
            auth_service=auth,
            on_lock_requested=lock_application,
        )
        window.show()
        maintenance_errors = [
            message for message in (backup_error, snapshot_error) if message
        ]
        if maintenance_errors:
            window.show_status("Local maintenance warning: " + "; ".join(maintenance_errors))
        return app.exec()
    finally:
        if net_worth is not None:
            try:
                net_worth.record_snapshot()
            except (ValueError, *DB_ERROR_TYPES):
                pass
        db.execute("PRAGMA optimize")
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
