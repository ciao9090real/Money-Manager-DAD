from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.core.database import connect
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    db = connect()
    window = MainWindow(db)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

