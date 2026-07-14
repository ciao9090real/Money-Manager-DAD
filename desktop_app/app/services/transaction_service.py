from __future__ import annotations

import sqlite3
from decimal import Decimal
from uuid import uuid4

from app.core.database import unit_of_work
from app.models.category import Category
from app.models.transaction import Transaction
from app.repositories.account_repository import AccountRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.payment_method_repository import PaymentMethodRepository
from app.repositories.transaction_repository import TransactionRepository
from app.utils.dates import require_iso_date
from app.utils.money import require_positive, to_decimal
from app.utils.validators import require_text


class TransactionService:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.accounts = AccountRepository(db)
        self.categories = CategoryRepository(db)
        self.payment_methods = PaymentMethodRepository(db)
        self.transactions = TransactionRepository(db)

    def add_income(
        self,
        account_id: int,
        amount: object,
        date: str,
        description: str = "",
        category_id: object = None,
        payment_method_id: int | None = None,
        notes: str | None = None,
    ) -> Transaction:
        with unit_of_work(self.db):
            self._require_account(account_id, active=True)
            resolved_category = self._resolve_category(category_id, "income")
            self._validate_payment_method(payment_method_id, account_id)
            return self.transactions.create(
                Transaction(
                    id=None,
                    date=require_iso_date(date),
                    type="income",
                    account_id=account_id,
                    payment_method_id=payment_method_id,
                    amount=require_positive(amount),
                    description=description.strip(),
                    category_id=resolved_category,
                    notes=notes,
                )
            )

    def add_expense(
        self,
        account_id: int,
        amount: object,
        date: str,
        description: str = "",
        category_id: object = None,
        payment_method_id: int | None = None,
        notes: str | None = None,
    ) -> Transaction:
        with unit_of_work(self.db):
            self._require_account(account_id, active=True)
            resolved_category = self._resolve_category(category_id, "expense")
            self._validate_payment_method(payment_method_id, account_id)
            return self.transactions.create(
                Transaction(
                    id=None,
                    date=require_iso_date(date),
                    type="expense",
                    account_id=account_id,
                    payment_method_id=payment_method_id,
                    amount=-require_positive(amount),
                    description=description.strip(),
                    category_id=resolved_category,
                    notes=notes,
                )
            )

    def add_adjustment(
        self,
        account_id: int,
        amount: object,
        date: str,
        description: str = "",
        notes: str | None = None,
    ) -> Transaction:
        with unit_of_work(self.db):
            self._require_account(account_id, active=True)
            return self.transactions.create(
                Transaction(
                    id=None,
                    date=require_iso_date(date),
                    type="adjustment",
                    account_id=account_id,
                    amount=to_decimal(amount),
                    description=description.strip(),
                    notes=notes,
                )
            )

    def add_transfer(
        self,
        source_account_id: int,
        target_account_id: int,
        amount: object,
        date: str,
        description: str = "",
        notes: str | None = None,
    ) -> tuple[Transaction, Transaction]:
        with unit_of_work(self.db):
            self._require_account(source_account_id, active=True)
            self._require_account(target_account_id, active=True)
            if source_account_id == target_account_id:
                raise ValueError("Transfer accounts must be different")
            transfer_amount = require_positive(amount)
            transfer_date = require_iso_date(date)
            group_id = uuid4().hex
            outgoing = self.transactions.create(
                Transaction(
                    id=None,
                    date=transfer_date,
                    type="transfer_out",
                    account_id=source_account_id,
                    amount=-transfer_amount,
                    description=description.strip(),
                    transfer_group_id=group_id,
                    notes=notes,
                )
            )
            incoming = self.transactions.create(
                Transaction(
                    id=None,
                    date=transfer_date,
                    type="transfer_in",
                    account_id=target_account_id,
                    amount=transfer_amount,
                    description=description.strip(),
                    transfer_group_id=group_id,
                    notes=notes,
                )
            )
            return outgoing, incoming

    def list_transactions(self, limit: int | None = None, **filters) -> list[Transaction]:
        return self.transactions.list(limit=limit, **filters)

    def get_transaction(self, transaction_id: int) -> Transaction | None:
        return self.transactions.get(transaction_id)

    def transfer_pair(self, transaction_id: int) -> tuple[Transaction, Transaction]:
        transaction = self._require_transaction(transaction_id)
        if not transaction.transfer_group_id:
            raise ValueError("Transaction is not a transfer")
        pair = self.transactions.list_by_transfer_group(transaction.transfer_group_id)
        if len(pair) != 2:
            raise ValueError("Transfer pair is incomplete")
        outgoing = next((item for item in pair if item.type == "transfer_out"), None)
        incoming = next((item for item in pair if item.type == "transfer_in"), None)
        if not outgoing or not incoming:
            raise ValueError("Transfer pair is invalid")
        return outgoing, incoming

    def update_transaction(
        self,
        transaction_id: int,
        transaction_type: str,
        account_id: int,
        amount: object,
        date: str,
        description: str = "",
        target_account_id: int | None = None,
        category_id: object = None,
        payment_method_id: int | None = None,
        notes: str | None = None,
    ) -> Transaction | tuple[Transaction, Transaction]:
        with unit_of_work(self.db):
            existing = self._require_transaction(transaction_id)
            cleaned_type = self._normalize_type(transaction_type)
            if cleaned_type == "transfer":
                return self._update_as_transfer(
                    existing,
                    account_id,
                    target_account_id,
                    amount,
                    date,
                    description,
                    notes,
                )
            return self._update_as_single(
                existing,
                cleaned_type,
                account_id,
                amount,
                date,
                description,
                category_id,
                payment_method_id,
                notes,
            )

    def delete_transaction(self, transaction_id: int) -> None:
        with unit_of_work(self.db):
            transaction = self._require_transaction(transaction_id)
            if transaction.transfer_group_id:
                for linked in self.transactions.list_by_transfer_group(transaction.transfer_group_id):
                    if linked.id is not None:
                        self.transactions.delete(linked.id)
            else:
                self.transactions.delete(transaction_id)

    def _require_account(self, account_id: int, active: bool = False) -> None:
        account = self.accounts.get(account_id)
        if not account:
            raise ValueError("Account not found")
        if active and not account.is_active:
            raise ValueError("Account is inactive")

    def _require_transaction(self, transaction_id: int) -> Transaction:
        transaction = self.transactions.get(transaction_id)
        if not transaction:
            raise ValueError("Transaction not found")
        return transaction

    def _normalize_type(self, transaction_type: str) -> str:
        cleaned = (transaction_type or "").strip()
        if cleaned in {"transfer_out", "transfer_in"}:
            return "transfer"
        if cleaned not in {"income", "expense", "transfer", "adjustment"}:
            raise ValueError("Transaction type is not supported")
        return cleaned

    def _update_as_single(
        self,
        existing: Transaction,
        transaction_type: str,
        account_id: int,
        amount: object,
        date: str,
        description: str,
        category_id: object,
        payment_method_id: int | None,
        notes: str | None,
    ) -> Transaction:
        self._require_account(account_id, active=True)
        if existing.transfer_group_id:
            for linked in self.transactions.list_by_transfer_group(existing.transfer_group_id):
                if linked.id != existing.id and linked.id is not None:
                    self.transactions.delete(linked.id)
        signed_amount = self._signed_amount(transaction_type, amount)
        category_value = (
            self._resolve_category(category_id, transaction_type)
            if transaction_type in {"income", "expense"}
            else None
        )
        payment_value = payment_method_id if transaction_type in {"income", "expense"} else None
        self._validate_payment_method(payment_value, account_id)
        return self.transactions.update(
            Transaction(
                id=existing.id,
                date=require_iso_date(date),
                type=transaction_type,
                account_id=account_id,
                payment_method_id=payment_value,
                amount=signed_amount,
                description=description.strip(),
                category_id=category_value,
                transfer_group_id=None,
                notes=notes,
            )
        )

    def _update_as_transfer(
        self,
        existing: Transaction,
        source_account_id: int,
        target_account_id: int | None,
        amount: object,
        date: str,
        description: str,
        notes: str | None,
    ) -> tuple[Transaction, Transaction]:
        if target_account_id is None:
            raise ValueError("Transfer target account is required")
        self._require_account(source_account_id, active=True)
        self._require_account(target_account_id, active=True)
        if source_account_id == target_account_id:
            raise ValueError("Transfer accounts must be different")
        transfer_amount = require_positive(amount)
        transfer_date = require_iso_date(date)
        description_value = description.strip()
        group_id = existing.transfer_group_id or uuid4().hex

        if existing.transfer_group_id:
            outgoing, incoming = self.transfer_pair(int(existing.id))
            outgoing_id = outgoing.id
            incoming_id = incoming.id
        else:
            outgoing_id = existing.id
            incoming = self.transactions.create(
                Transaction(
                    id=None,
                    date=transfer_date,
                    type="transfer_in",
                    account_id=target_account_id,
                    amount=transfer_amount,
                    description=description_value,
                    transfer_group_id=group_id,
                    notes=notes,
                )
            )
            incoming_id = incoming.id

        outgoing_updated = self.transactions.update(
            Transaction(
                id=outgoing_id,
                date=transfer_date,
                type="transfer_out",
                account_id=source_account_id,
                amount=-transfer_amount,
                description=description_value,
                transfer_group_id=group_id,
                notes=notes,
            )
        )
        incoming_updated = self.transactions.update(
            Transaction(
                id=incoming_id,
                date=transfer_date,
                type="transfer_in",
                account_id=target_account_id,
                amount=transfer_amount,
                description=description_value,
                transfer_group_id=group_id,
                notes=notes,
            )
        )
        return outgoing_updated, incoming_updated

    def _signed_amount(self, transaction_type: str, amount: object) -> Decimal:
        if transaction_type == "income":
            return require_positive(amount)
        if transaction_type == "expense":
            return -require_positive(amount)
        return to_decimal(amount)

    def _resolve_category(self, value: object, transaction_type: str) -> int | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if isinstance(value, int):
            category = self.categories.get(value)
            if not category:
                raise ValueError("Category not found")
            if not category.is_active:
                raise ValueError("Category is inactive")
            if category.type != transaction_type:
                raise ValueError("Category type does not match transaction type")
            return category.id

        name = require_text(str(value), "Category name")
        existing = self.categories.find_by_name_and_type(name, transaction_type)
        if existing:
            if not existing.is_active:
                raise ValueError("Category is inactive")
            return existing.id
        created = self.categories.create(
            Category(id=None, name=name, type=transaction_type, is_active=True)
        )
        return created.id

    def _validate_payment_method(self, payment_method_id: int | None, account_id: int) -> None:
        if payment_method_id is None:
            return
        method = self.payment_methods.get(payment_method_id)
        if not method:
            raise ValueError("Payment method not found")
        if not method.is_active:
            raise ValueError("Payment method is inactive")
        if method.account_id != account_id:
            raise ValueError("Payment method does not belong to the selected account")
