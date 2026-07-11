from __future__ import annotations

import sqlite3

from app.models.payment_method import PaymentMethod
from app.repositories.account_repository import AccountRepository
from app.repositories.payment_method_repository import PaymentMethodRepository
from app.utils.validators import require_text


class PaymentMethodService:
    def __init__(self, db: sqlite3.Connection):
        self.accounts = AccountRepository(db)
        self.payment_methods = PaymentMethodRepository(db)

    def create_payment_method(self, name: str, account_id: int, payment_type: str) -> PaymentMethod:
        account = self.accounts.get(account_id)
        if not account:
            raise ValueError("Account not found")
        if not account.is_active:
            raise ValueError("Payment method account must be active")
        return self.payment_methods.create(
            PaymentMethod(
                id=None,
                name=require_text(name, "Payment method name"),
                account_id=account_id,
                type=require_text(payment_type, "Payment method type"),
            )
        )

    def list_payment_methods(self, include_inactive: bool = False) -> list[PaymentMethod]:
        return self.payment_methods.list(include_inactive=include_inactive)

