from __future__ import annotations

import sqlite3

from app.core.database import unit_of_work
from app.models.payment_method import PaymentMethod
from app.repositories.account_repository import AccountRepository
from app.repositories.payment_method_repository import PaymentMethodRepository
from app.utils.validators import require_text


class PaymentMethodService:
    VALID_TYPES = {"debit_card", "credit_card", "paypal", "wallet", "other"}

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.accounts = AccountRepository(db)
        self.payment_methods = PaymentMethodRepository(db)

    def create_payment_method(self, name: str, account_id: str, payment_type: str) -> PaymentMethod:
        with unit_of_work(self.db):
            self._require_active_account(account_id)
            cleaned_name = require_text(name, "Payment method name")
            if self.payment_methods.find_by_account_and_name(account_id, cleaned_name):
                raise ValueError("A payment method with this name already exists for the account")
            return self.payment_methods.create(
                PaymentMethod(
                    id=None,
                    name=cleaned_name,
                    account_id=account_id,
                    type=self._require_type(payment_type),
                )
            )

    def list_payment_methods(self, include_inactive: bool = False) -> list[PaymentMethod]:
        return self.payment_methods.list(include_inactive=include_inactive)

    def update_payment_method(
        self,
        payment_method_id: str,
        name: str,
        account_id: str,
        payment_type: str,
    ) -> PaymentMethod:
        with unit_of_work(self.db):
            method = self._require_method(payment_method_id)
            self._require_active_account(account_id)
            cleaned_name = require_text(name, "Payment method name")
            duplicate = self.payment_methods.find_by_account_and_name(account_id, cleaned_name)
            if duplicate and duplicate.id != payment_method_id:
                raise ValueError("A payment method with this name already exists for the account")
            method.name = cleaned_name
            method.account_id = account_id
            method.type = self._require_type(payment_type)
            return self.payment_methods.update(method)

    def archive_payment_method(self, payment_method_id: str) -> None:
        with unit_of_work(self.db):
            self._require_method(payment_method_id)
            self.payment_methods.set_active(payment_method_id, False)

    def restore_payment_method(self, payment_method_id: str) -> None:
        with unit_of_work(self.db):
            method = self._require_method(payment_method_id)
            self._require_active_account(method.account_id)
            duplicate = self.payment_methods.find_by_account_and_name(
                method.account_id, method.name
            )
            if duplicate and duplicate.id != payment_method_id and duplicate.is_active:
                raise ValueError("An active payment method with this name already exists")
            self.payment_methods.set_active(payment_method_id, True)

    def _require_method(self, payment_method_id: str) -> PaymentMethod:
        method = self.payment_methods.get(payment_method_id)
        if not method:
            raise ValueError("Payment method not found")
        return method

    def _require_active_account(self, account_id: str) -> None:
        account = self.accounts.get(account_id)
        if not account:
            raise ValueError("Account not found")
        if not account.is_active:
            raise ValueError("Payment method account must be active")

    def _require_type(self, payment_type: str) -> str:
        cleaned = require_text(payment_type, "Payment method type")
        if cleaned not in self.VALID_TYPES:
            raise ValueError("Payment method type is not supported")
        return cleaned
