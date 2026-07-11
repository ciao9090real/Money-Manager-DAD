from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMessageBox, QWidget

from app.core.paths import app_data_dir, database_path
from app.services.backup_service import BackupService
from app.services.export_service import ExportService
from app.ui.components import actions_row, badge, create_card, page_layout, primary_button, secondary_button


class SettingsPage(QWidget):
    def __init__(self, db: sqlite3.Connection, notify=None):
        super().__init__()
        self.db = db
        self.notify = notify or (lambda _message: None)
        layout = page_layout(self, "Settings", "Local storage, backups, and exports")

        storage_card, storage_layout = create_card("Local database")
        database_label = QLabel(str(database_path()))
        self.database_path_text = str(database_path())
        database_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        database_label.setProperty("role", "mono")
        open_folder = secondary_button("Open folder", "\u25a3")
        copy_path = secondary_button("Copy path")
        open_folder.clicked.connect(self.open_database_folder)
        copy_path.clicked.connect(self.copy_database_path)
        storage_layout.addWidget(QLabel("Your data stays on this PC."))
        storage_layout.addWidget(database_label)
        storage_layout.addWidget(actions_row(open_folder, copy_path))
        layout.addWidget(storage_card)

        tools_card, tools_layout = create_card("Maintenance")
        backup_button = primary_button("Create backup", "\u21bb")
        export_button = secondary_button("Export transactions CSV")
        backup_button.clicked.connect(self.create_backup)
        export_button.clicked.connect(self.export_transactions)
        tools_layout.addWidget(actions_row(backup_button, export_button))
        layout.addWidget(tools_card)

        info_card, info_layout = create_card("App info")
        info_row = QWidget()
        info_row_layout = QHBoxLayout(info_row)
        info_row_layout.setContentsMargins(0, 0, 0, 0)
        info_row_layout.setSpacing(8)
        info_row_layout.addWidget(badge("Local desktop mode", "info"))
        info_row_layout.addWidget(badge("SQLite storage", "neutral"))
        info_row_layout.addWidget(badge("Version 0.1.0", "neutral"))
        info_row_layout.addStretch()
        info_layout.addWidget(info_row)
        layout.addWidget(info_card)
        layout.addStretch()

    def open_database_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_data_dir())))
        self.notify("Database folder opened")

    def copy_database_path(self) -> None:
        QApplication.clipboard().setText(self.database_path_text)
        self.notify("Database path copied")

    def create_backup(self) -> None:
        try:
            target = BackupService(self.db).create_backup()
            self.notify("Backup created")
            QMessageBox.information(self, "Backup created", str(target))
        except OSError as exc:
            QMessageBox.warning(self, "Backup failed", str(exc))

    def export_transactions(self) -> None:
        try:
            target = ExportService(self.db).export_transactions_csv()
            self.notify("Export created")
            QMessageBox.information(self, "Export created", str(target))
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
