from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.core.paths import app_data_dir, database_path
from app.services.backup_service import BackupService
from app.services.export_service import ExportService
from app.ui.category_manager import CategoryManagerDialog
from app.ui.components import (
    badge,
    create_card,
    page_layout,
    primary_button,
    secondary_button,
    soft_button,
)
from app.ui.icons import LineIcon


class SettingsPage(QWidget):
    def __init__(self, db: sqlite3.Connection, notify=None, on_changed=None):
        super().__init__()
        self.db = db
        self.notify = notify or (lambda _message: None)
        self.on_changed = on_changed or (lambda _tags: None)
        layout = page_layout(
            self,
            "Settings",
            "Storage, backups, exports, and local app preferences",
        )

        storage_card, storage_layout = create_card(
            "Local database",
            subtitle="Your financial data is stored only on this computer",
        )
        storage_body = QHBoxLayout()
        storage_body.setSpacing(16)
        storage_body.addWidget(self._icon_tile("folder"), 0, Qt.AlignmentFlag.AlignTop)
        storage_details = QVBoxLayout()
        storage_details.setSpacing(10)
        database_label = QLabel(str(database_path()))
        self.database_path_text = str(database_path())
        database_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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

        tools_grid = QGridLayout()
        tools_grid.setContentsMargins(0, 0, 0, 0)
        tools_grid.setHorizontalSpacing(18)
        tools_grid.setVerticalSpacing(18)

        backup_button = primary_button("Create backup", "backup")
        backup_button.clicked.connect(self.create_backup)
        backup_card = self._tool_card(
            "Backup & recovery",
            "Create a safe point-in-time copy including all WAL changes.",
            "backup",
            backup_button,
        )

        export_button = soft_button("Export CSV", "download")
        export_button.clicked.connect(self.export_transactions)
        export_card = self._tool_card(
            "Transaction export",
            "Create a portable CSV file for spreadsheets and analysis.",
            "download",
            export_button,
        )

        categories_button = soft_button("Manage categories", "tag")
        categories_button.clicked.connect(self.manage_categories)
        categories_card = self._tool_card(
            "Categories",
            "Organize, rename, archive, and restore income or expense categories.",
            "tag",
            categories_button,
        )

        tools_grid.addWidget(backup_card, 0, 0)
        tools_grid.addWidget(export_card, 0, 1)
        tools_grid.addWidget(categories_card, 0, 2)
        tools_grid.setColumnStretch(0, 1)
        tools_grid.setColumnStretch(1, 1)
        tools_grid.setColumnStretch(2, 1)
        layout.addLayout(tools_grid)

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
            "Backups and exports remain under your control."
        )
        description.setWordWrap(True)
        description.setProperty("role", "subtitle")
        chips = QHBoxLayout()
        chips.setSpacing(8)
        chips.addWidget(badge("Offline ready", "positive"))
        chips.addWidget(badge("SQLite + WAL", "info"))
        chips.addWidget(badge("Version 0.2.0", "neutral"))
        chips.addStretch()
        privacy_text.addWidget(description)
        privacy_text.addLayout(chips)
        privacy_body.addLayout(privacy_text, 1)
        privacy_layout.addLayout(privacy_body)
        layout.addWidget(privacy_card)
        layout.addStretch()

    def _icon_tile(self, icon_name: str) -> QFrame:
        tile = QFrame()
        tile.setProperty("role", "iconTile")
        tile.setFixedSize(44, 44)
        tile_layout = QHBoxLayout(tile)
        tile_layout.setContentsMargins(11, 11, 11, 11)
        tile_layout.addWidget(LineIcon(icon_name, "#5657d8", 22))
        return tile

    def _tool_card(self, title: str, description: str, icon_name: str, button) -> QFrame:
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
        card_layout.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
        card.setMinimumHeight(205)
        return card

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
        except (OSError, RuntimeError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Backup failed", str(exc))

    def export_transactions(self) -> None:
        try:
            target = ExportService(self.db).export_transactions_csv()
            self.notify("Export created")
            QMessageBox.information(self, "Export created", str(target))
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def manage_categories(self) -> None:
        CategoryManagerDialog(self.db, self.on_changed, self.notify).exec()
