from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.core.paths import backup_dir
from app.core.database_security import DB_ERROR_TYPES
from app.services.backup_service import BackupService
from app.ui.backup_password_dialog import BackupPasswordDialog
from app.ui.components import (
    create_card,
    empty_state,
    primary_button,
    secondary_button,
    style_table,
)


class BackupManagerDialog(QDialog):
    def __init__(self, db: sqlite3.Connection, on_changed=None, notify=None, parent=None):
        super().__init__(parent)
        self.service = BackupService(db)
        self.on_changed = on_changed or (lambda _tags: None)
        self.notify = notify or (lambda _message: None)
        self.setWindowTitle("Backups & recovery")
        self.setProperty("role", "sheet")
        self.setMinimumSize(880, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        title = QLabel("Backups & recovery")
        title.setProperty("role", "dialogTitle")
        subtitle = QLabel(
            "See every backup in one place, check that it opens, or restore it. "
            "Choose Secure backup for a copy you can keep on USB or cloud storage."
        )
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        self.create_button = primary_button("Create secure backup", "shield")
        self.verify_button = secondary_button("Check selected", "check")
        self.restore_button = secondary_button("Restore selected", "restore")
        self.folder_button = secondary_button("Open backup folder", "folder")
        self.create_button.clicked.connect(self.create_secure_backup)
        self.verify_button.clicked.connect(self.verify_selected)
        self.restore_button.clicked.connect(self.restore_selected)
        self.folder_button.clicked.connect(self.open_folder)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.create_button)
        actions.addWidget(self.verify_button)
        actions.addWidget(self.restore_button)
        actions.addStretch()
        actions.addWidget(self.folder_button)

        card, card_layout = create_card()
        card_layout.addLayout(actions)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Backup", "Created", "Protection", "Size", "Check"]
        )
        style_table(self.table)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._sync_actions)
        self.table.itemDoubleClicked.connect(lambda _item: self.verify_selected())
        self.empty = empty_state(
            "No backups yet",
            "Create a secure backup now. Automatic daily backups appear after normal app use.",
        )
        card_layout.addWidget(self.empty)
        card_layout.addWidget(self.table, 1)
        root.addWidget(card, 1)

        help_text = QLabel(
            "Locked = password-protected and not checked during this session. "
            "Windows account backups open only for this signed-in user. Older unprotected backups should not be copied to shared storage."
        )
        help_text.setProperty("role", "subtitle")
        help_text.setWordWrap(True)
        root.addWidget(help_text)

        close = secondary_button("Close")
        close.clicked.connect(self.accept)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(close)
        root.addLayout(footer)
        self.refresh()

    def refresh(self) -> None:
        backups = self.service.list_backups()
        self.table.setRowCount(len(backups))
        for row, backup in enumerate(backups):
            name = QTableWidgetItem(backup.kind)
            name.setData(Qt.ItemDataRole.UserRole, str(backup.path))
            name.setToolTip(str(backup.path))
            self.table.setItem(row, 0, name)
            created = datetime.fromtimestamp(backup.created_at).strftime(
                "%d %b %Y, %H:%M"
            )
            self.table.setItem(row, 1, QTableWidgetItem(created))
            self.table.setItem(row, 2, QTableWidgetItem(backup.protection))
            self.table.setItem(row, 3, QTableWidgetItem(_file_size(backup.size_bytes)))
            self.table.setItem(row, 4, QTableWidgetItem(backup.status))
        self.table.setVisible(bool(backups))
        self.empty.setVisible(not backups)
        self._sync_actions()

    def create_secure_backup(self) -> None:
        dialog = BackupPasswordDialog(confirm_password=True, parent=self)
        if not dialog.exec():
            return
        try:
            target = self.service.create_encrypted_backup(dialog.password())
        except (OSError, ValueError, RuntimeError, *DB_ERROR_TYPES) as exc:
            QMessageBox.warning(self, "Secure backup failed", str(exc))
            return
        self.notify("Secure backup created")
        self.refresh()
        QMessageBox.information(
            self,
            "Secure backup created",
            f"Your password-protected backup is ready:\n\n{target}\n\n"
            "Keep its password somewhere safe; Money Manager cannot recover it.",
        )

    def verify_selected(self) -> None:
        source = self._selected_path()
        if source is None:
            return
        password = self._password_if_needed(source)
        if password is False:
            return
        try:
            inspection = self.service.inspect_backup(
                source,
                password=password if isinstance(password, str) else None,
            )
        except (OSError, ValueError, *DB_ERROR_TYPES) as exc:
            QMessageBox.warning(
                self,
                "Backup needs attention",
                f"This backup could not be verified:\n\n{exc}",
            )
            return
        self.table.item(self.table.currentRow(), 4).setText("Ready")
        QMessageBox.information(
            self,
            "Backup is ready",
            f"The backup is intact and compatible (data version {inspection.schema_version}).",
        )

    def restore_selected(self) -> None:
        source = self._selected_path()
        if source is None:
            return
        password = self._password_if_needed(source)
        if password is False:
            return
        answer = QMessageBox.warning(
            self,
            "Restore this backup?",
            "Money Manager will first save your current database, then replace all current data with the selected backup.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            rollback = self.service.restore_backup(
                source,
                password=password if isinstance(password, str) else None,
            )
        except (OSError, ValueError, RuntimeError, *DB_ERROR_TYPES) as exc:
            QMessageBox.warning(self, "Restore failed", str(exc))
            return
        self.on_changed(
            {
                "dashboard",
                "accounts",
                "transactions",
                "budgets",
                "goals",
                "investments",
                "loans",
                "upcoming",
            }
        )
        self.notify("Backup restored")
        self.refresh()
        QMessageBox.information(
            self,
            "Backup restored",
            f"The backup was restored. Your previous database was kept here:\n\n{rollback}",
        )

    def open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(backup_dir())))

    def _selected_path(self) -> Path | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        return Path(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))

    def _password_if_needed(self, source: Path) -> str | bool | None:
        if not self.service.is_encrypted_backup(source):
            return None
        dialog = BackupPasswordDialog(confirm_password=False, parent=self)
        if not dialog.exec():
            return False
        return dialog.password()

    def _sync_actions(self) -> None:
        selected = self.table.currentRow() >= 0
        self.verify_button.setEnabled(selected)
        self.restore_button.setEnabled(selected)


def _file_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"
