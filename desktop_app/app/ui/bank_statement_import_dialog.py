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
    QSplitter,
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
from app.ui.components import apply_soft_shadow
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

        self.setWindowTitle("Reconciliation Studio")
        self.setMinimumSize(960, 680)
        self.resize(1120, 760)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        title = QLabel("Reconciliation Studio")
        title.setProperty("role", "pageTitle")
        subtitle = QLabel(
            "Map a bank export into an inbox. Nothing reaches your ledger until you review and post it."
        )
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)
        source_label = QLabel(f"Source  ·  {self.source.name}")
        source_label.setProperty("role", "statementSource")
        source_label.setToolTip(str(self.source))
        source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(source_label)

        workflow = QFrame()
        workflow.setProperty("role", "workflowRail")
        workflow_layout = QHBoxLayout(workflow)
        workflow_layout.setContentsMargins(5, 5, 5, 5)
        workflow_layout.setSpacing(5)
        self.workflow_steps: list[QLabel] = []
        for index, text in enumerate(
            ("1  Map columns", "2  Review rows", "3  Send to inbox")
        ):
            step = QLabel(text)
            step.setProperty("role", "workflowStep")
            step.setProperty("active", index == 0)
            step.setAlignment(Qt.AlignmentFlag.AlignCenter)
            workflow_layout.addWidget(step, 1)
            self.workflow_steps.append(step)
        layout.addWidget(workflow)

        mapping_frame = QFrame()
        mapping_frame.setProperty("role", "card")
        mapping_frame.setMinimumWidth(360)
        mapping_frame.setMaximumWidth(430)
        mapping_layout = QGridLayout(mapping_frame)
        mapping_layout.setContentsMargins(18, 16, 18, 18)
        mapping_layout.setHorizontalSpacing(12)
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
            self._field("Worksheet", self.sheet), 1, 0, 1, 2
        )
        mapping_layout.addLayout(
            self._field("Period starts", self.period_start), 2, 0
        )
        mapping_layout.addLayout(
            self._field("Period ends", self.period_end), 2, 1
        )
        mapping_layout.addLayout(
            self._field("Date column", self.date_column), 3, 0
        )
        mapping_layout.addLayout(
            self._field("Description column", self.description_column), 3, 1
        )
        mapping_layout.addLayout(
            self._field("Amount layout", self.amount_layout), 4, 0, 1, 2
        )
        mapping_layout.addLayout(
            self._field("Amount column", self.amount_column),
            5,
            0,
            1,
            2,
        )
        mapping_layout.addLayout(
            self._field("Positive amounts mean", self.amount_sign),
            6,
            0,
            1,
            2,
        )
        mapping_layout.addLayout(
            self._field("Debit / money out", self.debit_column), 7, 0
        )
        mapping_layout.addLayout(
            self._field("Credit / money in", self.credit_column), 7, 1
        )
        for column in range(2):
            mapping_layout.setColumnStretch(column, 1)

        preview_frame = QFrame()
        preview_frame.setProperty("role", "importPreviewCard")
        apply_soft_shadow(preview_frame, blur_radius=24, y_offset=4, alpha=16)
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(18, 16, 18, 16)
        preview_layout.setSpacing(12)

        preview_top = QHBoxLayout()
        preview_copy = QVBoxLayout()
        preview_title = QLabel("Live review")
        preview_title.setProperty("role", "sectionTitle")
        self.preview_status = QLabel("Choose the mapping, then check the file.")
        self.preview_status.setProperty("role", "subtitle")
        self.preview_status.setWordWrap(True)
        preview_copy.addWidget(preview_title)
        preview_copy.addWidget(self.preview_status)
        preview_top.addLayout(preview_copy, 1)
        self.check_button = QPushButton("Check transactions")
        self.check_button.setProperty("variant", "primary")
        self.check_button.clicked.connect(self._check_file)
        preview_top.addWidget(self.check_button, 0, Qt.AlignmentFlag.AlignTop)
        preview_layout.addLayout(preview_top)

        summary = QFrame()
        summary.setProperty("role", "importSummary")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.setSpacing(8)
        self.ready_count = self._summary_badge("0 ready", "positive")
        self.duplicate_count = self._summary_badge("0 duplicates", "neutral")
        self.ignored_count = self._summary_badge("0 ignored", "muted")
        self.issue_count = self._summary_badge("0 issues", "neutral")
        for item in (
            self.ready_count,
            self.duplicate_count,
            self.ignored_count,
            self.issue_count,
        ):
            summary_layout.addWidget(item)
        summary_layout.addStretch()
        preview_layout.addWidget(summary)

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
        preview_layout.addWidget(self.preview_table, 1)

        workspace = QSplitter(Qt.Orientation.Horizontal)
        workspace.setChildrenCollapsible(False)
        workspace.addWidget(mapping_frame)
        workspace.addWidget(preview_frame)
        workspace.setStretchFactor(0, 0)
        workspace.setStretchFactor(1, 1)
        workspace.setSizes([390, 680])
        layout.addWidget(workspace, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        self.import_button = buttons.addButton(
            "Send to import inbox",
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

    @staticmethod
    def _summary_badge(text: str, tone: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "badge")
        label.setProperty("tone", tone)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _set_workflow_step(self, active_index: int) -> None:
        for index, step in enumerate(self.workflow_steps):
            step.setProperty("active", index == active_index)
            step.style().unpolish(step)
            step.style().polish(step)

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
        self.preview_table.setRowCount(0)
        self.ready_count.setText("0 ready")
        self.duplicate_count.setText("0 duplicates")
        self.ignored_count.setText("0 ignored")
        self.issue_count.setText("0 issues")
        self.issue_count.setProperty("tone", "neutral")
        self.issue_count.style().unpolish(self.issue_count)
        self.issue_count.style().polish(self.issue_count)
        self._set_workflow_step(0)
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
            self.issue_count.setText("1 issue")
            self.issue_count.setProperty("tone", "negative")
            self.issue_count.style().unpolish(self.issue_count)
            self.issue_count.style().polish(self.issue_count)
            self.preview_status.setText(str(exc))
            return
        self.preview = preview
        self._show_preview(preview)

    def _show_preview(self, preview: StatementImportPreview) -> None:
        self._set_workflow_step(1)
        self.ready_count.setText(f"{preview.import_count} ready")
        self.duplicate_count.setText(
            f"{preview.duplicate_count} duplicate"
            f"{'s' if preview.duplicate_count != 1 else ''}"
        )
        self.ignored_count.setText(f"{preview.outside_period_count} ignored")
        self.issue_count.setText(
            f"{len(preview.errors)} issue"
            f"{'s' if len(preview.errors) != 1 else ''}"
        )
        self.issue_count.setProperty(
            "tone", "negative" if preview.errors else "neutral"
        )
        self.issue_count.style().unpolish(self.issue_count)
        self.issue_count.style().polish(self.issue_count)
        preview_items = list(preview.rows) + list(preview.issues)
        self.preview_table.setRowCount(min(len(preview_items), 100))
        for index, row in enumerate(preview_items[:100]):
            if hasattr(row, "message"):
                raw = dict(row.raw_payload)
                values = (
                    raw.get("date", ""),
                    "Issue",
                    row.message,
                    "",
                    "Needs fixing",
                )
            else:
                values = (
                    row.date,
                    row.transaction_type.title(),
                    row.description,
                    format_money(row.amount),
                    "Already imported" if row.duplicate else "Ready for review",
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
        if len(preview_items) > 100:
            details.append("first 100 rows shown")
        if preview.errors:
            shown = "\n".join(preview.errors[:5])
            remaining = len(preview.errors) - 5
            if remaining:
                shown += f"\n…and {remaining} more"
            self.preview_status.setText(
                "These rows will enter the inbox as issues and cannot post until "
                "they are resolved or ignored:\n" + shown
            )
            self.import_button.setEnabled(bool(preview.rows or preview.issues))
            return
        self.preview_status.setText(
            f"{preview.payment_method_name} · "
            f"{preview.period_start} to {preview.period_end} · "
            + " · ".join(details)
        )
        self.import_button.setEnabled(bool(preview.rows or preview.issues))

    def _accept_checked(self) -> None:
        if self.preview is None:
            return
        if not self.preview.rows and not self.preview.issues:
            QMessageBox.information(
                self,
                "Nothing to review",
                "No statement rows were found for this period.",
            )
            return
        self._set_workflow_step(2)
        self.accept()


def _normalized_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
