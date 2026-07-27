from __future__ import annotations

import csv
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree

from app.core.database import unit_of_work
from app.repositories.account_repository import AccountRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.payment_method_repository import PaymentMethodRepository
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
    payment_method_id: str | None = None
    target_account_id: str | None = None
    target_account_name: str | None = None
    duplicate: bool = False


@dataclass(frozen=True)
class ImportIssue:
    row_number: int
    message: str
    raw_payload: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ImportPreview:
    source: Path
    rows: tuple[TransactionImportRow, ...]
    errors: tuple[str, ...]
    issues: tuple[ImportIssue, ...] = ()

    @property
    def duplicate_count(self) -> int:
        return sum(row.duplicate for row in self.rows)

    @property
    def import_count(self) -> int:
        return len(self.rows) - self.duplicate_count


@dataclass(frozen=True)
class SpreadsheetTable:
    source: Path
    sheet_name: str
    headers: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    header_row_number: int = 1


@dataclass(frozen=True)
class StatementMapping:
    payment_method_id: str
    period_start: str
    period_end: str
    date_column: int
    description_column: int | None
    amount_mode: str = "signed"
    amount_column: int | None = None
    debit_column: int | None = None
    credit_column: int | None = None
    amount_sign: str = "signed"


@dataclass(frozen=True)
class StatementImportPreview(ImportPreview):
    payment_method_name: str = ""
    period_start: str = ""
    period_end: str = ""
    outside_period_count: int = 0
    blank_row_count: int = 0
    payment_method_id: str = ""
    sheet_name: str = ""
    mapping: StatementMapping | None = None


class ImportService:
    REQUIRED_COLUMNS = frozenset({"date", "type", "account", "amount"})

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.accounts = AccountRepository(db)
        self.categories = CategoryRepository(db)
        self.payment_methods = PaymentMethodRepository(db)
        self.transactions = TransactionService(db)

    @staticmethod
    def spreadsheet_sheets(source: Path) -> tuple[str, ...]:
        source = _checked_spreadsheet_path(source)
        if source.suffix.casefold() == ".csv":
            return ("Transactions",)
        return tuple(name for name, _target in _xlsx_sheets(source))

    @staticmethod
    def read_spreadsheet(
        source: Path, sheet_name: str | None = None
    ) -> SpreadsheetTable:
        source = _checked_spreadsheet_path(source)
        if source.suffix.casefold() == ".csv":
            rows = _read_csv_rows(source)
            return _table_from_rows(source, "Transactions", rows)
        rows, selected_sheet = _read_xlsx_rows(source, sheet_name)
        return _table_from_rows(source, selected_sheet, rows)

    def preview_bank_statement(
        self,
        table: SpreadsheetTable,
        mapping: StatementMapping,
    ) -> StatementImportPreview:
        if not table.headers:
            raise ValueError("The selected sheet does not contain column headings")
        start = require_iso_date(mapping.period_start)
        end = require_iso_date(mapping.period_end)
        if start > end:
            raise ValueError("The statement start date must not be after the end date")
        if mapping.amount_mode not in {"signed", "split"}:
            raise ValueError("Choose a supported amount layout")
        if mapping.amount_sign not in {"signed", "expense", "income"}:
            raise ValueError("Choose how positive amounts should be interpreted")
        self._require_column(table, mapping.date_column, "date")
        if mapping.description_column is not None:
            self._require_column(table, mapping.description_column, "description")
        if mapping.amount_mode == "signed":
            if mapping.amount_column is None:
                raise ValueError("Choose the amount column")
            self._require_column(table, mapping.amount_column, "amount")
        else:
            if mapping.debit_column is None or mapping.credit_column is None:
                raise ValueError("Choose both the debit and credit columns")
            if mapping.debit_column == mapping.credit_column:
                raise ValueError("Debit and credit must use different columns")
            self._require_column(table, mapping.debit_column, "debit")
            self._require_column(table, mapping.credit_column, "credit")

        method = self.payment_methods.get(mapping.payment_method_id)
        if method is None or not method.is_active:
            raise ValueError("Choose an active payment card")
        if method.type != "debit_card":
            raise ValueError("Bank statements can only be linked to a debit card")
        account = self.accounts.get(method.account_id)
        if account is None or not account.is_active:
            raise ValueError("The account linked to this debit card is not active")

        parsed: list[TransactionImportRow] = []
        errors: list[str] = []
        issues: list[ImportIssue] = []
        outside_period = 0
        blank_rows = 0
        for offset, values in enumerate(
            table.rows, start=table.header_row_number + 1
        ):
            if not any(_spreadsheet_text(value) for value in values):
                blank_rows += 1
                continue
            try:
                row_date = _spreadsheet_date(_cell(values, mapping.date_column))
                if row_date < start or row_date > end:
                    outside_period += 1
                    continue
                transaction_type, amount = self._statement_amount(values, mapping)
                description = (
                    _spreadsheet_text(_cell(values, mapping.description_column))
                    if mapping.description_column is not None
                    else ""
                )
                if not description:
                    description = "Card transaction"
                duplicate = self._is_statement_duplicate(
                    transaction_type,
                    row_date,
                    account.id,
                    amount,
                    description,
                )
                parsed.append(
                    TransactionImportRow(
                        row_number=offset,
                        date=row_date,
                        transaction_type=transaction_type,
                        account_id=account.id,
                        account_name=account.name,
                        amount=amount,
                        description=description,
                        notes=None,
                        payment_method_id=method.id,
                        duplicate=duplicate,
                    )
                )
            except ValueError as exc:
                errors.append(f"Row {offset}: {exc}")
                relevant_columns = {
                    "date": mapping.date_column,
                    "description": mapping.description_column,
                    "amount": mapping.amount_column,
                    "debit": mapping.debit_column,
                    "credit": mapping.credit_column,
                }
                issues.append(
                    ImportIssue(
                        offset,
                        str(exc),
                        tuple(
                            (
                                label,
                                _spreadsheet_text(_cell(values, column)),
                            )
                            for label, column in relevant_columns.items()
                            if column is not None
                        ),
                    )
                )

        if not parsed and not errors:
            errors.append(
                "No transactions were found inside the selected statement period"
            )
        return StatementImportPreview(
            source=table.source,
            rows=tuple(parsed),
            errors=tuple(errors),
            issues=tuple(issues),
            payment_method_name=method.name,
            period_start=start,
            period_end=end,
            outside_period_count=outside_period,
            blank_row_count=blank_rows,
            payment_method_id=method.id,
            sheet_name=table.sheet_name,
            mapping=mapping,
        )

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
        issues: list[ImportIssue] = []
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
                        safe_columns = (
                            "date",
                            "type",
                            "account",
                            "target_account",
                            "amount",
                            "description",
                            "category",
                            "notes",
                        )
                        issues.append(
                            ImportIssue(
                                row_number,
                                str(exc),
                                tuple(
                                    (
                                        name,
                                        _csv_text(
                                            raw.get(columns.get(name, ""), "")
                                        ),
                                    )
                                    for name in safe_columns
                                    if name in columns
                                ),
                            )
                        )
        except UnicodeDecodeError as exc:
            raise ValueError("CSV must be saved as UTF-8 text") from exc
        except csv.Error as exc:
            raise ValueError(f"CSV could not be read: {exc}") from exc

        if not parsed and not errors:
            errors.append("The CSV has headings but no transaction rows")
        return ImportPreview(
            source,
            tuple(parsed),
            tuple(errors),
            tuple(issues),
        )

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
                        payment_method_id=row.payment_method_id,
                        notes=row.notes,
                    )
                elif row.transaction_type == "expense":
                    self.transactions.add_expense(
                        row.account_id,
                        row.amount,
                        row.date,
                        row.description,
                        category_id=row.category_id,
                        payment_method_id=row.payment_method_id,
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

    @staticmethod
    def _require_column(
        table: SpreadsheetTable, column: int, label: str
    ) -> None:
        if column < 0 or column >= len(table.headers):
            raise ValueError(f"Choose a valid {label} column")

    @staticmethod
    def _statement_amount(
        values: tuple[object, ...], mapping: StatementMapping
    ) -> tuple[str, Decimal]:
        if mapping.amount_mode == "split":
            debit = _spreadsheet_decimal(_cell(values, mapping.debit_column), blank_ok=True)
            credit = _spreadsheet_decimal(
                _cell(values, mapping.credit_column), blank_ok=True
            )
            if debit and credit:
                raise ValueError("both debit and credit contain an amount")
            if debit:
                return "expense", abs(debit)
            if credit:
                return "income", abs(credit)
            raise ValueError("debit and credit are both blank")

        amount = _spreadsheet_decimal(_cell(values, mapping.amount_column))
        if amount == 0:
            raise ValueError("amount must not be zero")
        if mapping.amount_sign == "expense":
            return "expense", abs(amount)
        if mapping.amount_sign == "income":
            return "income", abs(amount)
        return ("expense", abs(amount)) if amount < 0 else ("income", amount)

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

    def _is_statement_duplicate(
        self,
        transaction_type: str,
        transaction_date: str,
        account_id: str,
        amount: Decimal,
        description: str,
    ) -> bool:
        cents = decimal_to_cents(amount)
        signed_cents = cents if transaction_type == "income" else -cents
        row = self.db.execute(
            """
            SELECT 1 FROM transactions
            WHERE deleted_at IS NULL AND date = ? AND type = ?
              AND account_id = ? AND amount_cents = ? AND description = ?
            LIMIT 1
            """,
            (
                transaction_date,
                transaction_type,
                account_id,
                signed_cents,
                description,
            ),
        ).fetchone()
        return row is not None


def _csv_text(value: object) -> str:
    text = str(value or "").strip()
    if len(text) > 1 and text[0] == "'" and text[1] in "=+-@\t\r":
        return text[1:]
    return text


def _checked_spreadsheet_path(source: Path) -> Path:
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise ValueError("Choose an existing CSV or Excel file")
    if source.suffix.casefold() not in {".csv", ".xlsx"}:
        raise ValueError("Choose a CSV or Excel .xlsx file")
    if source.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("Spreadsheet is too large; choose a file under 50 MB")
    return source


def _read_csv_rows(source: Path) -> list[list[object]]:
    try:
        with source.open("r", newline="", encoding="utf-8-sig") as handle:
            sample = handle.read(8192)
            handle.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel
            return [list(row) for row in csv.reader(handle, dialect)]
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be saved as UTF-8 text") from exc
    except csv.Error as exc:
        raise ValueError(f"CSV could not be read: {exc}") from exc


def _xlsx_sheets(source: Path) -> list[tuple[str, str]]:
    try:
        with zipfile.ZipFile(source) as archive:
            if sum(item.file_size for item in archive.infolist()) > 200 * 1024 * 1024:
                raise ValueError(
                    "Excel workbook expands beyond the 200 MB safety limit"
                )
            workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
            relationships = ElementTree.fromstring(
                archive.read("xl/_rels/workbook.xml.rels")
            )
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise ValueError("Excel workbook could not be read") from exc

    relationship_targets = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships
    }
    result: list[tuple[str, str]] = []
    relationship_key = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    for sheet in workbook.findall(
        ".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet"
    ):
        target = relationship_targets.get(sheet.attrib.get(relationship_key, ""))
        if not target:
            continue
        normalized = target.lstrip("/")
        if not normalized.startswith("xl/"):
            normalized = f"xl/{normalized}"
        result.append((sheet.attrib.get("name", "Sheet"), normalized))
    if not result:
        raise ValueError("Excel workbook does not contain a readable worksheet")
    return result


def _read_xlsx_rows(
    source: Path, sheet_name: str | None
) -> tuple[list[list[object]], str]:
    sheets = _xlsx_sheets(source)
    selected = next(
        (sheet for sheet in sheets if sheet[0] == sheet_name),
        sheets[0] if sheet_name is None else None,
    )
    if selected is None:
        raise ValueError("The selected worksheet was not found")
    try:
        with zipfile.ZipFile(source) as archive:
            shared_strings = _xlsx_shared_strings(archive)
            date_styles = _xlsx_date_styles(archive)
            worksheet = ElementTree.fromstring(archive.read(selected[1]))
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise ValueError("The selected Excel worksheet could not be read") from exc

    rows: list[list[object]] = []
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    for row in worksheet.findall(f".//{namespace}sheetData/{namespace}row"):
        row_number = int(row.attrib.get("r", str(len(rows) + 1)))
        while len(rows) < row_number - 1:
            rows.append([])
        values: list[object] = []
        for cell in row.findall(f"{namespace}c"):
            reference = cell.attrib.get("r", "A1")
            column = _excel_column_index(reference)
            while len(values) <= column:
                values.append("")
            values[column] = _xlsx_cell_value(
                cell, namespace, shared_strings, date_styles
            )
        rows.append(values)
    return rows, selected[0]


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    return [
        "".join(node.text or "" for node in item.iter(f"{namespace}t"))
        for item in root.findall(f"{namespace}si")
    ]


def _xlsx_date_styles(archive: zipfile.ZipFile) -> set[int]:
    try:
        root = ElementTree.fromstring(archive.read("xl/styles.xml"))
    except KeyError:
        return set()
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    custom_date_formats = {
        int(item.attrib["numFmtId"])
        for item in root.findall(f".//{namespace}numFmts/{namespace}numFmt")
        if _is_date_number_format(item.attrib.get("formatCode", ""))
    }
    built_in = set(range(14, 23)) | {45, 46, 47}
    date_styles: set[int] = set()
    cell_formats = root.find(f"{namespace}cellXfs")
    if cell_formats is not None:
        for index, item in enumerate(cell_formats.findall(f"{namespace}xf")):
            number_format = int(item.attrib.get("numFmtId", "0"))
            if number_format in built_in or number_format in custom_date_formats:
                date_styles.add(index)
    return date_styles


def _is_date_number_format(format_code: str) -> bool:
    cleaned = format_code.casefold()
    for literal in ('"'.join(cleaned.split('"')[1::2]),):
        if literal:
            cleaned = cleaned.replace(literal, "")
    return any(token in cleaned for token in ("yy", "dd", "mm/", "/mm", "m-", "-m"))


def _xlsx_cell_value(
    cell: ElementTree.Element,
    namespace: str,
    shared_strings: list[str],
    date_styles: set[int],
) -> object:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(
            node.text or "" for node in cell.iter(f"{namespace}t")
        )
    value_node = cell.find(f"{namespace}v")
    if value_node is None or value_node.text is None:
        return ""
    value = value_node.text
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (IndexError, ValueError):
            return ""
    if cell_type in {"str", "e"}:
        return value
    if cell_type == "b":
        return value == "1"
    try:
        number = Decimal(value)
    except InvalidOperation:
        return value
    style = int(cell.attrib.get("s", "0"))
    if style in date_styles:
        return date(1899, 12, 30) + timedelta(days=int(number))
    return number


def _excel_column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    result = 0
    for letter in letters.upper():
        result = result * 26 + ord(letter) - ord("A") + 1
    return max(result - 1, 0)


def _excel_column_name(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _table_from_rows(
    source: Path, sheet_name: str, raw_rows: list[list[object]]
) -> SpreadsheetTable:
    if not raw_rows:
        return SpreadsheetTable(source, sheet_name, (), ())
    candidates = raw_rows[:25]
    header_index = max(
        range(len(candidates)),
        key=lambda index: sum(
            bool(_spreadsheet_text(value)) for value in candidates[index]
        ),
    )
    if not any(_spreadsheet_text(value) for value in raw_rows[header_index]):
        return SpreadsheetTable(source, sheet_name, (), ())
    data_rows = raw_rows[header_index + 1 :]
    width = max(
        [len(raw_rows[header_index]), *(len(row) for row in data_rows)],
        default=0,
    )
    raw_headers = list(raw_rows[header_index]) + [""] * (
        width - len(raw_rows[header_index])
    )
    used: set[str] = set()
    headers: list[str] = []
    for index, value in enumerate(raw_headers):
        base = _spreadsheet_text(value) or f"Column {_excel_column_name(index)}"
        label = base
        if label.casefold() in used:
            label = f"{base} (column {_excel_column_name(index)})"
        used.add(label.casefold())
        headers.append(label)
    rows = [
        tuple(list(row) + [""] * (width - len(row)))
        for row in data_rows
    ]
    return SpreadsheetTable(
        source,
        sheet_name,
        tuple(headers),
        tuple(rows),
        header_row_number=header_index + 1,
    )


def _cell(values: tuple[object, ...], column: int | None) -> object:
    if column is None or column < 0 or column >= len(values):
        return ""
    return values[column]


def _spreadsheet_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    return str(value).strip()


def _spreadsheet_date(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = _spreadsheet_text(value)
    if not text:
        raise ValueError("date is blank")
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        pass
    for pattern in (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d/%m/%y",
        "%d-%m-%y",
    ):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f'date "{text}" is not recognized')


def _spreadsheet_decimal(value: object, *, blank_ok: bool = False) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = _spreadsheet_text(value)
    if not text:
        if blank_ok:
            return Decimal("0")
        raise ValueError("amount is blank")
    negative_parentheses = text.startswith("(") and text.endswith(")")
    cleaned = "".join(
        character
        for character in text
        if character.isdigit() or character in ",.-+"
    )
    if not cleaned:
        if blank_ok:
            return Decimal("0")
        raise ValueError(f'amount "{text}" is not recognized')
    if "," in cleaned and "." in cleaned:
        decimal_separator = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        grouping_separator = "." if decimal_separator == "," else ","
        cleaned = cleaned.replace(grouping_separator, "").replace(
            decimal_separator, "."
        )
    elif "," in cleaned:
        pieces = cleaned.split(",")
        cleaned = (
            "".join(pieces)
            if len(pieces[-1]) == 3 and len(pieces) > 1
            else "".join(pieces[:-1]) + "." + pieces[-1]
        )
    elif cleaned.count(".") > 1:
        pieces = cleaned.split(".")
        cleaned = (
            "".join(pieces)
            if len(pieces[-1]) == 3
            else "".join(pieces[:-1]) + "." + pieces[-1]
        )
    try:
        result = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f'amount "{text}" is not recognized') from exc
    return -abs(result) if negative_parentheses else result
