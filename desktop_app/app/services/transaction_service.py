from __future__ import annotations

import sqlite3
from decimal import Decimal
from uuid import uuid4

from app.models.transaction import Transaction
from app.repositories.account_repository import AccountRepository
from app.repositories.transaction_repository import TransactionRepository
from app.utils.dates import require_iso_date
from app.utils.money import require_positive, to_decimal


class TransactionService:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.accounts = AccountRepository(db)
        self.transactions = TransactionRepository(db)

    def add_income(
        self,
        account_id: int,
        amount: object,
        date: str,
        description: str = "",
        category_id: int | None = None,
        payment_method_id: int | None = None,
        notes: str | None = None,
    ) -> Transaction:
        self._require_account(account_id)
        transaction = self.transactions.create(
            Transaction(
                id=None,
                date=require_iso_date(date),
                type="income",
                account_id=account_id,
                payment_method_id=payment_method_id,
                amount=require_positive(amount),
                description=description.strip(),
                category_id=category_id,
                notes=notes,
            )
        )
        self.db.commit()
        return transaction

    def add_expense(
        self,
        account_id: int,
        amount: object,
        date: str,
        description: str = "",
        category_id: int | None = None,
        payment_method_id: int | None = None,
        notes: str | None = None,
    ) -> Transaction:
        self._require_account(account_id)
        transaction = self.transactions.create(
            Transaction(
                id=None,
                date=require_iso_date(date),
                type="expense",
                account_id=account_id,
                payment_method_id=payment_method_id,
                amount=-require_positive(amount),
                description=description.strip(),
                category_id=category_id,
                notes=notes,
            )
        )
        self.db.commit()
        return transaction

    def add_adjustment(
        self,
        account_id: int,
        amount: object,
        date: str,
        description: str = "",
        notes: str | None = None,
    ) -> Transaction:
        self._require_account(account_id)
        transaction = self.transactions.create(
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
        self.db.commit()
        return transaction

    def add_transfer(
        self,
        source_account_id: int,
        target_account_id: int,
        amount: object,
        date: str,
        description: str = "",
        notes: str | None = None,
    ) -> tuple[Transaction, Transaction]:
        self._require_account(source_account_id)
        self._require_account(target_account_id)
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
        self.db.commit()
        return outgoing, incoming

    def list_transactions(self, limit: int | None = None) -> list[Transaction]:
        return self.transactions.list(limit=limit)

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
        category_id: int | None = None,
        payment_method_id: int | None = None,
        notes: str | None = None,
    ) -> Transaction | tuple[Transaction, Transaction]:
        existing = self._require_transaction(transaction_id)
        cleaned_type = self._normalize_type(transaction_type)
        if cleaned_type == "transfer":
            result = self._update_as_transfer(
                existing,
                account_id,
                target_account_id,
                amount,
                date,
                description,
                notes,
            )
        else:
            result = self._update_as_single(
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
        self.db.commit()
        return result

    def delete_transaction(self, transaction_id: int) -> None:
        transaction = self._require_transaction(transaction_id)
        if transaction.transfer_group_id:
            for linked in self.transactions.list_by_transfer_group(transaction.transfer_group_id):
                if linked.id is not None:
                    self.transactions.delete(linked.id)
        else:
            self.transactions.delete(transaction_id)
        self.db.commit()

    def _require_account(self, account_id: int) -> None:
        if not self.accounts.get(account_id):
            raise ValueError("Account not found")

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
        category_id: int | None,
        payment_method_id: int | None,
        notes: str | None,
    ) -> Transaction:
        self._require_account(account_id)
        if existing.transfer_group_id:
            for linked in self.transactions.list_by_transfer_group(existing.transfer_group_id):
                if linked.id != existing.id and linked.id is not None:
                    self.transactions.delete(linked.id)
        signed_amount = self._signed_amount(transaction_type, amount)
        category_value = category_id if transaction_type in {"income", "expense"} else None
        payment_value = payment_method_id if transaction_type in {"income", "expense"} else None
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
        self._require_account(source_account_id)
        self._require_account(target_account_id)
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
