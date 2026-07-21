from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from app.core.database import unit_of_work
from app.repositories.account_repository import AccountRepository
from app.repositories.category_repository import CategoryRepository
from app.services.transaction_service import TransactionService
from app.utils.dates import require_iso_date
from app.utils.money import decimal_to_cents, require_positive


@dataclass(frozen=True)
class TransactionImportRow:
    row_number: int
    date: str
    transaction_type: str
    account_id: str
    account_name: str
    amount: Decimal
    description: str
    notes: str | None
    category_id: str | None = None
    target_account_id: str | None = None
    target_account_name: str | None = None
    duplicate: bool = False


@dataclass(frozen=True)
class ImportPreview:
    source: Path
    rows: tuple[TransactionImportRow, ...]
    errors: tuple[str, ...]

    @property
    def duplicate_count(self) -> int:
        return sum(row.duplicate for row in self.rows)

    @property
    def import_count(self) -> int:
        return len(self.rows) - self.duplicate_count


class ImportService:
    REQUIRED_COLUMNS = frozenset({"date", "type", "account", "amount"})

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.accounts = AccountRepository(db)
        self.categories = CategoryRepository(db)
        self.transactions = TransactionService(db)

    def preview_transactions_csv(self, source: Path) -> ImportPreview:
        source = Path(source).expanduser().resolve()
        if not source.is_file():
            raise ValueError("Choose an existing CSV file")

        account_names: dict[str, list[object]] = {}
        for account in self.accounts.list():
            account_names.setdefault(account.name.casefold(), []).append(account)
        category_names = {
            (category.type, category.name.casefold()): category
            for category in self.categories.list()
        }

        parsed: list[TransactionImportRow] = []
        errors: list[str] = []
        try:
            with source.open("r", newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                columns = {
                    str(column or "").strip().casefold(): column
                    for column in (reader.fieldnames or ())
                }
                missing = sorted(self.REQUIRED_COLUMNS - columns.keys())
                if missing:
                    raise ValueError(
                        "CSV is missing required columns: " + ", ".join(missing)
                    )
                for row_number, raw in enumerate(reader, start=2):
                    try:
                        parsed.append(
                            self._parse_row(
                                row_number,
                                raw,
                                columns,
                                account_names,
                                category_names,
                            )
                        )
                    except ValueError as exc:
                        errors.append(f"Row {row_number}: {exc}")
        except UnicodeDecodeError as exc:
            raise ValueError("CSV must be saved as UTF-8 text") from exc
        except csv.Error as exc:
            raise ValueError(f"CSV could not be read: {exc}") from exc

        if not parsed and not errors:
            errors.append("The CSV has headings but no transaction rows")
        return ImportPreview(source, tuple(parsed), tuple(errors))

    def import_transactions(self, preview: ImportPreview) -> int:
        if preview.errors:
            raise ValueError("Fix the CSV errors before importing")
        rows = [row for row in preview.rows if not row.duplicate]
        with unit_of_work(self.db):
            for row in rows:
                if row.transaction_type == "income":
                    self.transactions.add_income(
                        row.account_id,
                        row.amount,
                        row.date,
                        row.description,
                        category_id=row.category_id,
                        notes=row.notes,
                    )
                elif row.transaction_type == "expense":
                    self.transactions.add_expense(
                        row.account_id,
                        row.amount,
                        row.date,
                        row.description,
                        category_id=row.category_id,
                        notes=row.notes,
                    )
                else:
                    self.transactions.add_transfer(
                        row.account_id,
                        row.target_account_id,
                        row.amount,
                        row.date,
                        row.description,
                        notes=row.notes,
                    )
        return len(rows)

    def _parse_row(
        self,
        row_number: int,
        raw: dict[str, str],
        columns: dict[str, str],
        account_names: dict[str, list[object]],
        category_names: dict[tuple[str, str], object],
    ) -> TransactionImportRow:
        value = lambda name: _csv_text(raw.get(columns.get(name, ""), ""))
        transaction_type = value("type").casefold().replace(" ", "_")
        if transaction_type not in {"income", "expense", "transfer"}:
            if transaction_type in {"transfer_in", "transfer_out"}:
                raise ValueError(
                    "old transfer exports cannot be re-imported; export again with this app version"
                )
            raise ValueError("type must be income, expense, or transfer")

        date = require_iso_date(value("date"))
        amount = require_positive(value("amount").replace(",", ""))
        account_name = value("account")
        account = self._account_named(account_name, account_names)
        target_name = value("target_account") or None
        target = None
        if transaction_type == "transfer":
            if not target_name:
                raise ValueError("target_account is required for a transfer")
            target = self._account_named(target_name, account_names)
            if target.id == account.id:
                raise ValueError("transfer accounts must be different")

        category_id = None
        category_name = value("category")
        if category_name:
            if transaction_type == "transfer":
                raise ValueError("transfers cannot have a category")
            category = category_names.get(
                (transaction_type, category_name.casefold())
            )
            if category is None:
                raise ValueError(
                    f'category "{category_name}" was not found for {transaction_type}'
                )
            category_id = category.id

        description = value("description")
        notes = value("notes") or None
        duplicate = self._is_duplicate(
            transaction_type,
            date,
            account.id,
            target.id if target else None,
            amount,
            description,
            notes,
            category_id,
        )
        return TransactionImportRow(
            row_number=row_number,
            date=date,
            transaction_type=transaction_type,
            account_id=account.id,
            account_name=account.name,
            amount=amount,
            description=description,
            notes=notes,
            category_id=category_id,
            target_account_id=target.id if target else None,
            target_account_name=target.name if target else None,
            duplicate=duplicate,
        )

    @staticmethod
    def _account_named(name: str, accounts: dict[str, list[object]]):
        matches = accounts.get(name.casefold(), [])
        if not matches:
            raise ValueError(f'active account "{name}" was not found')
        if len(matches) > 1:
            raise ValueError(f'account name "{name}" is ambiguous')
        return matches[0]

    def _is_duplicate(
        self,
        transaction_type: str,
        date: str,
        account_id: str,
        target_account_id: str | None,
        amount: Decimal,
        description: str,
        notes: str | None,
        category_id: str | None,
    ) -> bool:
        cents = decimal_to_cents(amount)
        if transaction_type != "transfer":
            signed_cents = cents if transaction_type == "income" else -cents
            row = self.db.execute(
                """
                SELECT 1 FROM transactions
                WHERE deleted_at IS NULL AND date = ? AND type = ?
                  AND account_id = ? AND amount_cents = ? AND description = ?
                  AND COALESCE(notes, '') = COALESCE(?, '')
                  AND COALESCE(category_id, '') = COALESCE(?, '')
                LIMIT 1
                """,
                (
                    date,
                    transaction_type,
                    account_id,
                    signed_cents,
                    description,
                    notes,
                    category_id,
                ),
            ).fetchone()
            return row is not None

        row = self.db.execute(
            """
            SELECT 1
            FROM transactions outgoing
            JOIN transactions incoming
              ON incoming.transfer_group_id = outgoing.transfer_group_id
             AND incoming.type = 'transfer_in'
             AND incoming.deleted_at IS NULL
            WHERE outgoing.deleted_at IS NULL
              AND outgoing.type = 'transfer_out'
              AND outgoing.date = ?
              AND outgoing.account_id = ?
              AND incoming.account_id = ?
              AND outgoing.amount_cents = ?
              AND outgoing.description = ?
              AND COALESCE(outgoing.notes, '') = COALESCE(?, '')
            LIMIT 1
            """,
            (
                date,
                account_id,
                target_account_id,
                -cents,
                description,
                notes,
            ),
        ).fetchone()
        return row is not None


def _csv_text(value: object) -> str:
    text = str(value or "").strip()
    if len(text) > 1 and text[0] == "'" and text[1] in "=+-@\t\r":
        return text[1:]
    return text
