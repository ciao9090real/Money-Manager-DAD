from __future__ import annotations

import re
import sqlite3
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.repositories.account_repository import AccountRepository
from app.services.import_service import (
    ImportService,
    SpreadsheetTable,
    StatementImportPreview,
    StatementMapping,
)
from app.utils.money import format_money


class BankStatementImportDialog(QDialog):
    def __init__(
        self,
        db: sqlite3.Connection,
        source: Path,
        parent=None,
    ):
        super().__init__(parent)
        self.service = ImportService(db)
        self.accounts = AccountRepository(db)
        self.source = Path(source)
        self.table: SpreadsheetTable | None = None
        self.preview: StatementImportPreview | None = None

        self.setWindowTitle("Import card statement")
        self.setMinimumSize(800, 680)
        self.resize(920, 760)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        title = QLabel("Import debit-card transactions")
        title.setProperty("role", "pageTitle")
        subtitle = QLabel(
            "Map the bank's columns, choose the statement period, then check every row before importing."
        )
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)
        source_label = QLabel(str(self.source))
        source_label.setProperty("role", "caption")
        source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(source_label)

        mapping_frame = QFrame()
        mapping_frame.setProperty("role", "card")
        mapping_layout = QGridLayout(mapping_frame)
        mapping_layout.setContentsMargins(18, 16, 18, 18)
        mapping_layout.setHorizontalSpacing(16)
        mapping_layout.setVerticalSpacing(12)

        self.card = QComboBox()
        for method in self.service.payment_methods.list():
            if method.type != "debit_card":
                continue
            account = self.accounts.get(method.account_id)
            if account is not None and account.is_active:
                self.card.addItem(f"{method.name}  ·  {account.name}", method.id)
        if self.card.count() == 0:
            raise ValueError(
                "Create an active debit-card payment method before importing a card statement"
            )

        self.sheet = QComboBox()
        for sheet_name in self.service.spreadsheet_sheets(self.source):
            self.sheet.addItem(sheet_name)

        today = date.today()
        self.period_start = QDateEdit(
            QDate(today.year, today.month, 1)
        )
        self.period_end = QDateEdit(QDate(today.year, today.month, today.day))
        for picker in (self.period_start, self.period_end):
            picker.setCalendarPopup(True)
            picker.setDisplayFormat("dd MMM yyyy")

        self.date_column = QComboBox()
        self.description_column = QComboBox()
        self.amount_layout = QComboBox()
        self.amount_layout.addItem("One amount column", "signed")
        self.amount_layout.addItem("Separate debit and credit columns", "split")
        self.amount_column = QComboBox()
        self.amount_sign = QComboBox()
        self.amount_sign.addItem("Use signs: + income, − expense", "signed")
        self.amount_sign.addItem("Treat every amount as an expense", "expense")
        self.amount_sign.addItem("Treat every amount as income", "income")
        self.debit_column = QComboBox()
        self.credit_column = QComboBox()

        mapping_layout.addLayout(
            self._field("Debit card", self.card), 0, 0, 1, 2
        )
        mapping_layout.addLayout(
            self._field("Worksheet", self.sheet), 0, 2, 1, 2
        )
        mapping_layout.addLayout(
            self._field("Period starts", self.period_start), 1, 0
        )
        mapping_layout.addLayout(
            self._field("Period ends", self.period_end), 1, 1
        )
        mapping_layout.addLayout(
            self._field("Date column", self.date_column), 1, 2
        )
        mapping_layout.addLayout(
            self._field("Description column", self.description_column), 1, 3
        )
        mapping_layout.addLayout(
            self._field("Amount layout", self.amount_layout), 2, 0, 1, 2
        )
        mapping_layout.addLayout(
            self._field("Amount column", self.amount_column),
            2,
            2,
            1,
            2,
        )
        mapping_layout.addLayout(
            self._field("Positive amounts mean", self.amount_sign),
            3,
            0,
            1,
            2,
        )
        mapping_layout.addLayout(
            self._field("Debit / money out", self.debit_column), 3, 2
        )
        mapping_layout.addLayout(
            self._field("Credit / money in", self.credit_column), 3, 3
        )
        for column in range(4):
            mapping_layout.setColumnStretch(column, 1)
        layout.addWidget(mapping_frame)

        preview_top = QHBoxLayout()
        preview_copy = QVBoxLayout()
        preview_title = QLabel("Safety preview")
        preview_title.setProperty("role", "sectionTitle")
        self.preview_status = QLabel("Choose the mapping, then check the file.")
        self.preview_status.setProperty("role", "subtitle")
        self.preview_status.setWordWrap(True)
        preview_copy.addWidget(preview_title)
        preview_copy.addWidget(self.preview_status)
        preview_top.addLayout(preview_copy, 1)
        self.check_button = QPushButton("Check transactions")
        self.check_button.setProperty("role", "primary")
        self.check_button.clicked.connect(self._check_file)
        preview_top.addWidget(self.check_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(preview_top)

        self.preview_table = QTableWidget(0, 5)
        self.preview_table.setHorizontalHeaderLabels(
            ["Date", "Type", "Description", "Amount", "Result"]
        )
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.preview_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.preview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.preview_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.preview_table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        self.import_button = buttons.addButton(
            "Import checked transactions",
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self._accept_checked)
        layout.addWidget(buttons)

        self.sheet.currentTextChanged.connect(self._load_sheet)
        self.amount_layout.currentIndexChanged.connect(self._update_amount_fields)
        for control in (
            self.card,
            self.date_column,
            self.description_column,
            self.amount_column,
            self.amount_sign,
            self.debit_column,
            self.credit_column,
        ):
            control.currentIndexChanged.connect(self._invalidate_preview)
        self.period_start.dateChanged.connect(self._invalidate_preview)
        self.period_end.dateChanged.connect(self._invalidate_preview)

        self._load_sheet(self.sheet.currentText())
        self._update_amount_fields()

    @staticmethod
    def _field(label: str, widget) -> QVBoxLayout:
        field = QVBoxLayout()
        field.setSpacing(5)
        caption = QLabel(label)
        caption.setProperty("role", "fieldLabel")
        field.addWidget(caption)
        field.addWidget(widget)
        return field

    def _load_sheet(self, sheet_name: str) -> None:
        try:
            self.table = self.service.read_spreadsheet(self.source, sheet_name)
        except (OSError, ValueError) as exc:
            self.table = None
            QMessageBox.warning(self, "Worksheet could not be read", str(exc))
            return
        headers = self.table.headers
        combos = (
            self.date_column,
            self.amount_column,
            self.debit_column,
            self.credit_column,
        )
        for combo in combos:
            combo.blockSignals(True)
            combo.clear()
            for index, header in enumerate(headers):
                combo.addItem(header, index)
            combo.blockSignals(False)
        self.description_column.blockSignals(True)
        self.description_column.clear()
        self.description_column.addItem("No description column", None)
        for index, header in enumerate(headers):
            self.description_column.addItem(header, index)
        self.description_column.blockSignals(False)

        self._select_suggestion(
            self.date_column,
            ("date", "booking date", "transaction date", "value date", "data"),
        )
        self._select_suggestion(
            self.description_column,
            (
                "description",
                "merchant",
                "details",
                "transaction",
                "narrative",
                "causale",
                "descrizione",
            ),
        )
        self._select_suggestion(
            self.amount_column,
            ("amount", "transaction amount", "value", "importo"),
        )
        self._select_suggestion(
            self.debit_column,
            ("debit", "withdrawal", "money out", "addebito", "uscite"),
        )
        self._select_suggestion(
            self.credit_column,
            ("credit", "deposit", "money in", "accredito", "entrate"),
        )
        self._invalidate_preview()

    @staticmethod
    def _select_suggestion(combo: QComboBox, suggestions: tuple[str, ...]) -> None:
        normalized_suggestions = {_normalized_header(item) for item in suggestions}
        for index in range(combo.count()):
            if _normalized_header(combo.itemText(index)) in normalized_suggestions:
                combo.setCurrentIndex(index)
                return

    def _update_amount_fields(self) -> None:
        split = self.amount_layout.currentData() == "split"
        self.amount_column.setEnabled(not split)
        self.amount_sign.setEnabled(not split)
        self.debit_column.setEnabled(split)
        self.credit_column.setEnabled(split)
        self._invalidate_preview()

    def _invalidate_preview(self, *_args) -> None:
        self.preview = None
        self.import_button.setEnabled(False)
        self.preview_status.setText(
            "Mapping changed. Check the file again before importing."
        )

    def _mapping(self) -> StatementMapping:
        date_column = self.date_column.currentData()
        return StatementMapping(
            payment_method_id=str(self.card.currentData() or ""),
            period_start=self.period_start.date().toString("yyyy-MM-dd"),
            period_end=self.period_end.date().toString("yyyy-MM-dd"),
            date_column=int(date_column) if date_column is not None else -1,
            description_column=self.description_column.currentData(),
            amount_mode=str(self.amount_layout.currentData()),
            amount_column=self.amount_column.currentData(),
            debit_column=self.debit_column.currentData(),
            credit_column=self.credit_column.currentData(),
            amount_sign=str(self.amount_sign.currentData()),
        )

    def _check_file(self) -> None:
        if self.table is None:
            return
        try:
            preview = self.service.preview_bank_statement(
                self.table, self._mapping()
            )
        except (OSError, ValueError, sqlite3.DatabaseError) as exc:
            self.preview = None
            self.import_button.setEnabled(False)
            self.preview_status.setText(str(exc))
            return
        self.preview = preview
        self._show_preview(preview)

    def _show_preview(self, preview: StatementImportPreview) -> None:
        self.preview_table.setRowCount(min(len(preview.rows), 100))
        for index, row in enumerate(preview.rows[:100]):
            values = (
                row.date,
                row.transaction_type.title(),
                row.description,
                format_money(row.amount),
                "Already imported" if row.duplicate else "Ready",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 3:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                self.preview_table.setItem(index, column, item)

        details = [
            f"{preview.import_count} new",
            f"{preview.duplicate_count} duplicate"
            f"{'s' if preview.duplicate_count != 1 else ''}",
        ]
        if preview.outside_period_count:
            details.append(
                f"{preview.outside_period_count} outside the period (ignored)"
            )
        if len(preview.rows) > 100:
            details.append("first 100 rows shown")
        if preview.errors:
            shown = "\n".join(preview.errors[:5])
            remaining = len(preview.errors) - 5
            if remaining:
                shown += f"\n…and {remaining} more"
            self.preview_status.setText(
                "Nothing can be imported until these rows are fixed:\n" + shown
            )
            self.import_button.setEnabled(False)
            return
        self.preview_status.setText(
            f"{preview.payment_method_name} · "
            f"{preview.period_start} to {preview.period_end} · "
            + " · ".join(details)
        )
        self.import_button.setEnabled(preview.import_count > 0)

    def _accept_checked(self) -> None:
        if self.preview is None or self.preview.errors:
            return
        if self.preview.import_count <= 0:
            QMessageBox.information(
                self,
                "Nothing new to import",
                "Every transaction in this period is already in Money Manager.",
            )
            return
        self.accept()


def _normalized_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
