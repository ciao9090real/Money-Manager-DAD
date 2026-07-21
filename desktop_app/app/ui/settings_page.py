from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.core.app_info import APP_VERSION
from app.core.database_security import DB_ERROR_TYPES
from app.core.paths import app_data_dir, backup_dir, database_path
from app.services.backup_service import BackupService
from app.services.export_service import ExportService
from app.services.import_service import ImportService
from app.sync.pairing_qr import pairing_qr_image
from app.sync.server import LocalSyncServer
from app.ui.backup_password_dialog import BackupPasswordDialog
from app.ui.backup_manager_dialog import BackupManagerDialog
from app.ui.category_manager import CategoryManagerDialog
from app.ui.components import (
    badge,
    actions_row,
    clear_layout,
    create_card,
    page_layout,
    primary_button,
    secondary_button,
    soft_button,
)
from app.ui.icons import LineIcon
from app.ui.recently_deleted_dialog import RecentlyDeletedDialog
from app.ui.theme import Colors


class SettingsPage(QWidget):
    def __init__(self, db: sqlite3.Connection, notify=None, on_changed=None):
        super().__init__()
        self.db = db
        self.notify = notify or (lambda _message: None)
        self.on_changed = on_changed or (lambda _tags: None)
        self.sync_server = LocalSyncServer()
        layout = page_layout(
            self,
            "Settings",
            "Storage, backups, exports, and local app preferences",
        )

        storage_card, storage_layout = create_card(
            "Encrypted local database",
            subtitle="Protected with SQLCipher and a key tied to your Windows account",
        )
        storage_body = QHBoxLayout()
        storage_body.setSpacing(16)
        storage_body.addWidget(self._icon_tile("folder"), 0, Qt.AlignmentFlag.AlignTop)
        storage_details = QVBoxLayout()
        storage_details.setSpacing(10)
        database_label = QLineEdit(str(database_path()))
        self.database_path_text = str(database_path())
        database_label.setReadOnly(True)
        database_label.setProperty("role", "mono")
        actions = QHBoxLayout()
        actions.setSpacing(9)
        open_folder = secondary_button("Open data folder", "folder")
        copy_path = secondary_button("Copy path", "copy")
        open_folder.clicked.connect(self.open_database_folder)
        copy_path.clicked.connect(self.copy_database_path)
        actions.addWidget(open_folder)
        actions.addWidget(copy_path)
        actions.addStretch()
        storage_details.addWidget(database_label)
        storage_details.addLayout(actions)
        storage_body.addLayout(storage_details, 1)
        storage_layout.addLayout(storage_body)
        layout.addWidget(storage_card)

        sync_card, sync_layout = create_card(
            "Android phone sync",
            subtitle="Pair over your local Wi-Fi; each device keeps its own database",
        )
        sync_top = QHBoxLayout()
        sync_top.setSpacing(12)
        sync_top.addWidget(self._icon_tile("devices"), 0, Qt.AlignmentFlag.AlignTop)
        sync_copy = QLabel(
            "Start phone sync, then scan one QR code in the Android app. "
            "Pairing uses local HTTPS and a one-time code."
        )
        sync_copy.setProperty("role", "subtitle")
        sync_copy.setWordWrap(True)
        sync_top.addWidget(sync_copy, 1)
        self.sync_status = badge("Off", "neutral")
        sync_top.addWidget(self.sync_status, 0, Qt.AlignmentFlag.AlignTop)
        sync_layout.addLayout(sync_top)

        self.sync_qr = QLabel("Start phone sync to create a QR code")
        self.sync_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sync_qr.setMinimumSize(280, 280)
        qr_row = QHBoxLayout()
        qr_row.addStretch()
        qr_row.addWidget(self.sync_qr)
        qr_row.addStretch()
        sync_layout.addLayout(qr_row)

        sync_actions = QHBoxLayout()
        sync_actions.setSpacing(9)
        self.start_sync_button = primary_button("Start phone sync", "devices")
        self.stop_sync_button = secondary_button("Stop", "close")
        self.refresh_code_button = secondary_button("New QR", "refresh")
        self.stop_sync_button.setEnabled(False)
        self.refresh_code_button.setEnabled(False)
        self.start_sync_button.clicked.connect(self.start_phone_sync)
        self.stop_sync_button.clicked.connect(self.stop_phone_sync)
        self.refresh_code_button.clicked.connect(self.refresh_pairing_code)
        sync_actions.addWidget(self.start_sync_button)
        sync_actions.addWidget(self.stop_sync_button)
        sync_actions.addWidget(self.refresh_code_button)
        sync_actions.addStretch()
        sync_layout.addLayout(sync_actions)
        layout.addWidget(sync_card)

        self.tools_grid = QGridLayout()
        self.tools_grid.setContentsMargins(0, 0, 0, 0)
        self.tools_grid.setHorizontalSpacing(16)
        self.tools_grid.setVerticalSpacing(16)

        backup_button = primary_button("Manage backups", "backup")
        backup_button.clicked.connect(self.manage_backups)
        encrypted_backup_button = secondary_button("Secure backup", "shield")
        encrypted_backup_button.setToolTip("Create a password-protected backup")
        encrypted_backup_button.clicked.connect(self.create_encrypted_backup)
        backup_card = self._tool_card(
            "Backup & recovery",
            "See, check, create, and restore backups with plain-language guidance.",
            "backup",
            actions_row(backup_button, encrypted_backup_button),
        )

        export_button = soft_button("Export CSV", "download")
        export_button.clicked.connect(self.export_transactions)
        import_button = secondary_button("Import CSV", "restore")
        import_button.clicked.connect(self.import_transactions)
        export_card = self._tool_card(
            "Import & export",
            "Move transactions to or from a spreadsheet with a safety preview.",
            "download",
            actions_row(import_button, export_button),
        )

        categories_button = soft_button("Manage categories", "tag")
        categories_button.clicked.connect(self.manage_categories)
        categories_card = self._tool_card(
            "Categories",
            "Organize, rename, archive, and restore income or expense categories.",
            "tag",
            categories_button,
        )

        deleted_button = soft_button("Open Recently Deleted", "restore")
        deleted_button.clicked.connect(self.manage_recently_deleted)
        deleted_card = self._tool_card(
            "Recently deleted",
            "Recover deleted transactions and recurring payments without bypassing sync history.",
            "restore",
            deleted_button,
        )

        self.tool_cards = [backup_card, export_card, categories_card, deleted_card]
        layout.addLayout(self.tools_grid)

        privacy_card, privacy_layout = create_card(
            "Private by design",
            subtitle="Money Manager works fully offline and does not require an account",
        )
        privacy_body = QHBoxLayout()
        privacy_body.setSpacing(16)
        privacy_body.addWidget(self._icon_tile("shield"), 0, Qt.AlignmentFlag.AlignTop)
        privacy_text = QVBoxLayout()
        privacy_text.setSpacing(8)
        description = QLabel(
            "No cloud database, advertising tracker, or remote finance service is connected. "
            "The Windows database and Android cache are encrypted. Backups and exports remain under your control."
        )
        description.setWordWrap(True)
        description.setProperty("role", "subtitle")
        chips = QHBoxLayout()
        chips.setSpacing(8)
        chips.addWidget(badge("Offline ready", "positive"))
        chips.addWidget(badge("Encrypted Windows database", "positive"))
        chips.addWidget(badge("Encrypted Android cache", "info"))
        chips.addWidget(badge(f"Version {APP_VERSION}", "neutral"))
        chips.addStretch()
        privacy_text.addWidget(description)
        privacy_text.addLayout(chips)
        privacy_body.addLayout(privacy_text, 1)
        privacy_layout.addLayout(privacy_body)
        layout.addWidget(privacy_card)
        layout.addStretch()
        self._layout_tools()

    def _icon_tile(self, icon_name: str) -> QFrame:
        tile = QFrame()
        tile.setProperty("role", "iconTile")
        tile.setFixedSize(44, 44)
        tile_layout = QHBoxLayout(tile)
        tile_layout.setContentsMargins(11, 11, 11, 11)
        tile_layout.addWidget(LineIcon(icon_name, Colors.PRIMARY, 22))
        return tile

    def _tool_card(self, title: str, description: str, icon_name: str, action) -> QFrame:
        card, card_layout = create_card(role="card")
        top = QHBoxLayout()
        top.addWidget(self._icon_tile(icon_name))
        top.addStretch()
        card_layout.addLayout(top)
        title_label = QLabel(title)
        title_label.setProperty("role", "sectionTitle")
        description_label = QLabel(description)
        description_label.setProperty("role", "sectionSubtitle")
        description_label.setWordWrap(True)
        card_layout.addWidget(title_label)
        card_layout.addWidget(description_label)
        card_layout.addStretch()
        card_layout.addWidget(action, 0, Qt.AlignmentFlag.AlignLeft)
        card.setMinimumHeight(190)
        return card

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_tools()

    def _layout_tools(self) -> None:
        if not hasattr(self, "tools_grid"):
            return
        columns = 2 if self.width() >= 760 else 1
        if getattr(self, "_tool_columns", None) == columns:
            return
        self._tool_columns = columns
        clear_layout(self.tools_grid)
        for column in range(2):
            self.tools_grid.setColumnStretch(column, 1 if column < columns else 0)
        for index, card in enumerate(self.tool_cards):
            self.tools_grid.addWidget(card, index // columns, index % columns)

    def open_database_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_data_dir())))
        self.notify("Database folder opened")

    def copy_database_path(self) -> None:
        QApplication.clipboard().setText(self.database_path_text)
        self.notify("Database path copied")

    def create_backup(self) -> None:
        """Dashboard shortcut: manual backups should always be portable and secure."""
        self.create_encrypted_backup()

    def create_local_recovery_backup(self) -> Path | None:
        try:
            target = BackupService(self.db).create_backup()
            self.notify("Recovery point created")
            return target
        except (OSError, RuntimeError, *DB_ERROR_TYPES) as exc:
            QMessageBox.warning(self, "Backup failed", str(exc))
            return None

    def manage_backups(self) -> None:
        BackupManagerDialog(
            self.db,
            on_changed=self.on_changed,
            notify=self.notify,
            parent=self,
        ).exec()

    def create_encrypted_backup(self) -> None:
        dialog = BackupPasswordDialog(confirm_password=True, parent=self)
        if not dialog.exec():
            return
        try:
            target = BackupService(self.db).create_encrypted_backup(
                dialog.password()
            )
            self.notify("Encrypted backup created")
            QMessageBox.information(
                self,
                "Encrypted backup created",
                f"The password-protected backup was saved to:\n\n{target}",
            )
        except (OSError, ValueError, RuntimeError, *DB_ERROR_TYPES) as exc:
            QMessageBox.warning(self, "Encrypted backup failed", str(exc))

    def restore_backup(self) -> None:
        source, _filter = QFileDialog.getOpenFileName(
            self,
            "Restore Money Manager backup",
            str(backup_dir()),
            "Money Manager backups (*.mmbak *.db);;Encrypted backup (*.mmbak);;SQLite backup (*.db);;All files (*)",
        )
        if not source:
            return
        service = BackupService(self.db)
        password = None
        if service.is_encrypted_backup(Path(source)):
            password_dialog = BackupPasswordDialog(
                confirm_password=False,
                parent=self,
            )
            if not password_dialog.exec():
                return
            password = password_dialog.password()
        answer = QMessageBox.warning(
            self,
            "Restore backup",
            "Restore this backup now? Your current database will be saved first, then all open pages will refresh.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            rollback = service.restore_backup(source, password=password)
            self.on_changed(
                {"dashboard", "accounts", "transactions", "investments", "loans", "upcoming"}
            )
            self.notify("Backup restored")
            QMessageBox.information(
                self,
                "Backup restored",
                f"The backup was restored successfully.\n\nYour previous database was saved to:\n{rollback}",
            )
        except (OSError, ValueError, RuntimeError, *DB_ERROR_TYPES) as exc:
            QMessageBox.warning(self, "Restore failed", str(exc))

    def export_transactions(self) -> None:
        documents = Path.home() / "Documents"
        initial = documents / f"Money Manager transactions {date.today():%Y-%m-%d}.csv"
        target, _filter = QFileDialog.getSaveFileName(
            self,
            "Export transactions",
            str(initial),
            "CSV spreadsheet (*.csv)",
        )
        if not target:
            return
        if not target.lower().endswith(".csv"):
            target += ".csv"
        try:
            exported = ExportService(self.db).export_transactions_csv(Path(target))
            self.notify("Export created")
            QMessageBox.information(
                self,
                "Export ready",
                f"Your spreadsheet was saved here:\n\n{exported}\n\n"
                "It contains one row per income, expense, or transfer and can be imported again later.",
            )
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def import_transactions(self) -> None:
        source, _filter = QFileDialog.getOpenFileName(
            self,
            "Import transactions from CSV",
            str(Path.home() / "Documents"),
            "CSV spreadsheet (*.csv);;All files (*)",
        )
        if not source:
            return
        service = ImportService(self.db)
        try:
            preview = service.preview_transactions_csv(Path(source))
        except (OSError, ValueError, *DB_ERROR_TYPES) as exc:
            QMessageBox.warning(self, "CSV could not be checked", str(exc))
            return
        if preview.errors:
            shown = "\n".join(preview.errors[:12])
            remaining = len(preview.errors) - 12
            if remaining > 0:
                shown += f"\n…and {remaining} more problem{'s' if remaining != 1 else ''}"
            QMessageBox.warning(
                self,
                "Fix the CSV before importing",
                "Nothing was imported. These rows need attention:\n\n" + shown,
            )
            return
        if preview.import_count == 0:
            QMessageBox.information(
                self,
                "Nothing new to import",
                f"All {preview.duplicate_count} transaction rows are already in Money Manager.",
            )
            return
        duplicate_note = (
            f"\n\n{preview.duplicate_count} exact duplicate"
            f"{'s' if preview.duplicate_count != 1 else ''} will be skipped."
            if preview.duplicate_count
            else ""
        )
        answer = QMessageBox.question(
            self,
            "Import checked transactions?",
            f"Money Manager found {preview.import_count} new transaction"
            f"{'s' if preview.import_count != 1 else ''} ready to import."
            f"{duplicate_note}\n\nA recovery point will be made first.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        rollback = self.create_local_recovery_backup()
        if rollback is None:
            return
        try:
            imported = service.import_transactions(preview)
        except (OSError, ValueError, *DB_ERROR_TYPES) as exc:
            QMessageBox.warning(
                self,
                "Import failed safely",
                f"No partial import was kept.\n\n{exc}",
            )
            return
        self.on_changed({"dashboard", "accounts", "transactions"})
        self.notify(f"Imported {imported} transactions")
        QMessageBox.information(
            self,
            "Import complete",
            f"Imported {imported} transaction{'s' if imported != 1 else ''}.\n\n"
            f"Your before-import recovery point is here:\n{rollback}",
        )

    def manage_categories(self) -> None:
        CategoryManagerDialog(self.db, self.on_changed, self.notify).exec()

    def manage_recently_deleted(self) -> None:
        RecentlyDeletedDialog(self.db, self.on_changed, self.notify).exec()

    def start_phone_sync(self) -> None:
        try:
            details = self.sync_server.start()
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Phone sync could not start", str(exc))
            return
        self._show_pairing_details(details)
        self.start_sync_button.setEnabled(False)
        self.stop_sync_button.setEnabled(True)
        self.refresh_code_button.setEnabled(True)
        self.sync_status.setText("On")
        self.sync_status.setProperty("tone", "positive")
        self.sync_status.style().unpolish(self.sync_status)
        self.sync_status.style().polish(self.sync_status)
        self.notify("Phone sync is ready on local Wi-Fi")

    def stop_phone_sync(self) -> None:
        self.sync_server.stop()
        self.start_sync_button.setEnabled(True)
        self.stop_sync_button.setEnabled(False)
        self.refresh_code_button.setEnabled(False)
        self.sync_status.setText("Off")
        self.sync_status.setProperty("tone", "neutral")
        self.sync_status.style().unpolish(self.sync_status)
        self.sync_status.style().polish(self.sync_status)
        self.sync_qr.clear()
        self.sync_qr.setText("Start phone sync to create a QR code")
        self.notify("Phone sync stopped")

    def refresh_pairing_code(self) -> None:
        if not self.sync_server.is_running:
            return
        self.sync_server.regenerate_pairing_code()
        self._show_pairing_details(self.sync_server.pairing_details())
        self.notify("A new pairing QR was created")

    def shutdown_sync(self) -> None:
        self.sync_server.stop()

    def _show_pairing_details(self, details: dict) -> None:
        self.sync_qr.setPixmap(QPixmap.fromImage(pairing_qr_image(details)))
        self.sync_qr.setToolTip("Scan with Money Manager for Android")
