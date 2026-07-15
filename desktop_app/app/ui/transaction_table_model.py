from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from app.models.transaction import Transaction
from app.ui.components import pretty_type
from app.ui.theme import Colors
from app.utils.money import format_money
from app.utils.dates import format_display_date


class TransactionTableModel(QAbstractTableModel):
    HEADERS = ("Date", "Type", "Account", "Category", "Description", "Amount")

    def __init__(self):
        super().__init__()
        self.transactions: list[Transaction] = []
        self.account_names: dict[str | None, str] = {}
        self.category_names: dict[str | None, str] = {}

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.transactions)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.transactions):
            return None
        transaction = self.transactions[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            values = (
                format_display_date(transaction.date),
                pretty_type(transaction.type),
                self.account_names.get(transaction.account_id, "Inactive account"),
                self.category_names.get(transaction.category_id, ""),
                transaction.description or "No description",
                format_money(transaction.amount),
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
        self.transactions = list(transactions)
        self.account_names = account_names
        self.category_names = category_names
        self.endResetModel()

    def append(self, transactions: list[Transaction]) -> None:
        if not transactions:
            return
        start = len(self.transactions)
        self.beginInsertRows(QModelIndex(), start, start + len(transactions) - 1)
        self.transactions.extend(transactions)
        self.endInsertRows()

    def transaction_at(self, row: int) -> Transaction | None:
        if 0 <= row < len(self.transactions):
            return self.transactions[row]
        return None
