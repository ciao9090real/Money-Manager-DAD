from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
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

from app.services.trash_service import TrashService
from app.ui.components import create_card, empty_state, primary_button, secondary_button, style_table


class RecentlyDeletedDialog(QDialog):
    def __init__(self, db: sqlite3.Connection, on_changed=None, notify=None):
        super().__init__()
        self.service = TrashService(db)
        self.on_changed = on_changed or (lambda _tags: None)
        self.notify = notify or (lambda _message: None)
        self.setWindowTitle("Recently deleted")
        self.setProperty("role", "sheet")
        self.setMinimumSize(720, 500)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        title = QLabel("Recently deleted")
        title.setProperty("role", "dialogTitle")
        subtitle = QLabel(
            "Restore deleted transactions and recurring payments. Items remain as sync-safe tombstones until restored."
        )
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        self.restore_button = primary_button("Restore selected", "restore")
        self.restore_button.clicked.connect(self.restore_selected)
        self.count_label = QLabel()
        self.count_label.setProperty("role", "count")
        header = QHBoxLayout()
        header.addWidget(self.count_label)
        header.addStretch()
        header.addWidget(self.restore_button)

        card, card_layout = create_card()
        card_layout.addLayout(header)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Item", "Details", "Deleted"])
        style_table(self.table)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._sync_actions)
        self.table.itemDoubleClicked.connect(lambda _item: self.restore_selected())
        self.empty = empty_state(
            "Nothing in Recently Deleted",
            "Deleted transactions and recurring payments will appear here.",
        )
        card_layout.addWidget(self.empty)
        card_layout.addWidget(self.table, 1)
        root.addWidget(card, 1)

        close = secondary_button("Close")
        close.clicked.connect(self.accept)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(close)
        root.addLayout(actions)
        self.refresh()

    def refresh(self) -> None:
        items = self.service.list_items()
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            label = QTableWidgetItem(item.label)
            label.setData(Qt.ItemDataRole.UserRole, (item.entity_type, item.entity_id))
            self.table.setItem(row, 0, label)
            self.table.setItem(row, 1, QTableWidgetItem(item.detail))
            deleted = item.deleted_at.replace("T", " ").replace("Z", "")[:19]
            self.table.setItem(row, 2, QTableWidgetItem(deleted))
        self.count_label.setText(f"{len(items)} item{'s' if len(items) != 1 else ''}")
        self.table.setVisible(bool(items))
        self.empty.setVisible(not items)
        self._sync_actions()

    def restore_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        entity_type, entity_id = item.data(Qt.ItemDataRole.UserRole)
        answer = QMessageBox.question(
            self,
            "Restore item",
            f"Restore {item.text()}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.restore(entity_type, entity_id)
        except (ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Could not restore item", str(exc))
            return
        self.on_changed({"dashboard", "transactions", "upcoming"})
        self.notify("Item restored")
        self.refresh()

    def _sync_actions(self) -> None:
        self.restore_button.setEnabled(self.table.currentRow() >= 0)
