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

    def _require_account(self, account_id: int) -> None:
        if not self.accounts.get(account_id):
            raise ValueError("Account not found")

