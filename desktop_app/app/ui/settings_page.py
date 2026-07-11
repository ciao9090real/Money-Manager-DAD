from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from app.core.paths import database_path
from app.services.backup_service import BackupService
from app.services.export_service import ExportService


class SettingsPage(QWidget):
    def __init__(self, db: sqlite3.Connection):
        super().__init__()
        self.db = db
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Database location"))
        layout.addWidget(QLabel(str(database_path())))
        backup_button = QPushButton("Create backup")
        export_button = QPushButton("Export transactions CSV")
        backup_button.clicked.connect(self.create_backup)
        export_button.clicked.connect(self.export_transactions)
        layout.addWidget(backup_button)
        layout.addWidget(export_button)
        layout.addStretch()

    def create_backup(self) -> None:
        try:
            target = BackupService(self.db).create_backup()
            QMessageBox.information(self, "Backup created", str(target))
        except OSError as exc:
            QMessageBox.warning(self, "Backup failed", str(exc))

    def export_transactions(self) -> None:
        try:
            target = ExportService(self.db).export_transactions_csv()
            QMessageBox.information(self, "Export created", str(target))
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

