from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from app.models.transaction import Transaction
from app.ui.components import pretty_type
from app.ui.theme import Colors
from app.utils.money import format_money
from app.utils.dates import format_display_date


@dataclass
class TransactionDisplayRow:
    primary: Transaction
    paired: Transaction | None = None

    def transactions(self) -> tuple[Transaction, ...]:
        return (self.primary,) if self.paired is None else (self.primary, self.paired)

    def selected_transaction(self) -> Transaction:
        return next(
            (item for item in self.transactions() if item.type == "transfer_out"),
            self.primary,
        )


def group_transaction_rows(
    transactions: list[Transaction],
) -> list[TransactionDisplayRow]:
    rows: list[TransactionDisplayRow] = []
    transfer_rows: dict[str, TransactionDisplayRow] = {}
    for transaction in transactions:
        group_id = transaction.transfer_group_id
        if not group_id:
            rows.append(TransactionDisplayRow(transaction))
            continue
        existing = transfer_rows.get(group_id)
        if existing:
            existing.paired = transaction
            continue
        display_row = TransactionDisplayRow(transaction)
        transfer_rows[group_id] = display_row
        rows.append(display_row)
    return rows


class TransactionTableModel(QAbstractTableModel):
    HEADERS = ("Date", "Type", "Account", "Category", "Description", "Amount")

    def __init__(self):
        super().__init__()
        self.source_transactions: list[Transaction] = []
        self.rows: list[TransactionDisplayRow] = []
        self.account_names: dict[str | None, str] = {}
        self.category_names: dict[str | None, str] = {}

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.rows):
            return None
        row = self.rows[index.row()]
        transaction = row.selected_transaction()
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            transfer = transaction.transfer_group_id is not None
            transaction_label = "Loan" if transaction.loan_id else pretty_type(transaction.type)
            values = (
                format_display_date(transaction.date),
                "Transfer" if transfer else transaction_label,
                self._account_label(row),
                "" if transfer else self.category_names.get(transaction.category_id, ""),
                transaction.description or "No description",
                format_money(abs(transaction.amount) if transfer else transaction.amount),
            )
            return values[column]
        if role == Qt.ItemDataRole.TextAlignmentRole and column == 5:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ForegroundRole and column == 5:
            if transaction.type in {"transfer_out", "transfer_in", "adjustment"}:
                return None
            if transaction.amount > 0:
                return QColor(Colors.POSITIVE)
            if transaction.amount < 0:
                return QColor(Colors.NEGATIVE)
        return None

    def replace(
        self,
        transactions: list[Transaction],
        account_names: dict[str | None, str],
        category_names: dict[str | None, str],
    ) -> None:
        self.beginResetModel()
        self.source_transactions = list(transactions)
        self.rows = group_transaction_rows(self.source_transactions)
        self.account_names = account_names
        self.category_names = category_names
        self.endResetModel()

    def append(self, transactions: list[Transaction]) -> None:
        if not transactions:
            return
        self.beginResetModel()
        self.source_transactions.extend(transactions)
        self.rows = group_transaction_rows(self.source_transactions)
        self.endResetModel()

    def transaction_at(self, row: int) -> Transaction | None:
        if 0 <= row < len(self.rows):
            return self.rows[row].selected_transaction()
        return None

    def _account_label(self, row: TransactionDisplayRow) -> str:
        items = row.transactions()
        outgoing = next((item for item in items if item.type == "transfer_out"), None)
        incoming = next((item for item in items if item.type == "transfer_in"), None)
        if outgoing and incoming:
            source = self.account_names.get(outgoing.account_id, "Inactive account")
            target = self.account_names.get(incoming.account_id, "Inactive account")
            return f"{source} → {target}"
        return self.account_names.get(row.primary.account_id, "Inactive account")
