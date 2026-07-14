from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.core.database import connect
from app.ui.main_window import MainWindow
from app.ui.styles import app_stylesheet


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(app_stylesheet())
    db = connect()
    try:
        window = MainWindow(db)
        window.show()
        return app.exec()
    finally:
        db.execute("PRAGMA optimize")
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
