from __future__ import annotations

import calendar
import sqlite3
from datetime import date, timedelta
from decimal import Decimal

from app.core.database import unit_of_work
from app.models.recurring_rule import RecurringRule
from app.repositories.account_repository import AccountRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.payment_method_repository import PaymentMethodRepository
from app.repositories.recurring_rule_repository import RecurringRuleRepository
from app.services.transaction_service import TransactionService
from app.utils.dates import require_iso_date, today_iso
from app.utils.money import require_positive
from app.utils.validators import require_text


class RecurringService:
    KINDS = {"subscription", "bill", "other"}
    AMOUNT_MODES = {"fixed", "variable"}
    FREQUENCIES = {"weekly", "monthly", "quarterly", "yearly"}
    TRANSACTION_TYPES = {"income", "expense"}

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.rules = RecurringRuleRepository(db)
        self.accounts = AccountRepository(db)
        self.categories = CategoryRepository(db)
        self.payment_methods = PaymentMethodRepository(db)
        self.transactions = TransactionService(db)

    def create_rule(
        self,
        name: str,
        kind: str,
        amount_mode: str,
        account_id: str,
        frequency: str,
        next_due_date: str,
        amount: object = None,
        category_id: str | None = None,
        payment_method_id: str | None = None,
        end_date: str | None = None,
        reminder_days: int = 3,
        notes: str | None = None,
        transaction_type: str = "expense",
    ) -> RecurringRule:
        with unit_of_work(self.db):
            due_date = require_iso_date(next_due_date)
            cleaned_transaction_type = self._transaction_type(transaction_type)
            return self.rules.create(
                RecurringRule(
                    id=None,
                    name=require_text(name, "Recurring payment name"),
                    kind=self._kind(kind),
                    amount_mode=self._amount_mode(amount_mode),
                    amount=self._amount(amount_mode, amount),
                    account_id=self._account(account_id),
                    category_id=self._category(category_id, cleaned_transaction_type),
                    payment_method_id=(
                        self._payment_method(payment_method_id, account_id)
                        if cleaned_transaction_type == "expense"
                        else None
                    ),
                    frequency=self._frequency(frequency),
                    start_date=due_date,
                    next_due_date=due_date,
                    transaction_type=cleaned_transaction_type,
                    end_date=self._end_date(end_date, due_date),
                    reminder_days=self._reminder_days(reminder_days),
                    notes=self._notes(notes),
                )
            )

    def update_rule(
        self,
        rule_id: str,
        name: str,
        kind: str,
        amount_mode: str,
        account_id: str,
        frequency: str,
        next_due_date: str,
        amount: object = None,
        category_id: str | None = None,
        payment_method_id: str | None = None,
        end_date: str | None = None,
        reminder_days: int = 3,
        notes: str | None = None,
        transaction_type: str = "expense",
    ) -> RecurringRule:
        with unit_of_work(self.db):
            rule = self._rule(rule_id)
            due_date = require_iso_date(next_due_date)
            if due_date < rule.start_date:
                raise ValueError("Next due date cannot be before the schedule start")
            rule.name = require_text(name, "Recurring payment name")
            rule.kind = self._kind(kind)
            rule.amount_mode = self._amount_mode(amount_mode)
            rule.amount = self._amount(amount_mode, amount)
            rule.account_id = self._account(account_id)
            rule.transaction_type = self._transaction_type(transaction_type)
            rule.category_id = self._category(category_id, rule.transaction_type)
            rule.payment_method_id = (
                self._payment_method(payment_method_id, account_id)
                if rule.transaction_type == "expense"
                else None
            )
            rule.frequency = self._frequency(frequency)
            rule.next_due_date = due_date
            rule.end_date = self._end_date(end_date, due_date)
            rule.reminder_days = self._reminder_days(reminder_days)
            rule.notes = self._notes(notes)
            return self.rules.update(rule)

    def list_rules(
        self,
        *,
        status: str | None = None,
        kind: str | None = None,
        transaction_type: str | None = None,
    ) -> list[RecurringRule]:
        return self.rules.list(
            status=status,
            kind=kind,
            transaction_type=transaction_type,
        )

    def get_rule(self, rule_id: str) -> RecurringRule | None:
        return self.rules.get(rule_id)

    def summary(self, reference_date: date | None = None) -> dict:
        today = reference_date or date.today()
        horizon = today + timedelta(days=30)
        active = self.rules.list(status="active")
        overdue = [rule for rule in active if date.fromisoformat(rule.next_due_date) < today]
        due_soon = [
            rule
            for rule in active
            if today <= date.fromisoformat(rule.next_due_date) <= horizon
        ]
        expected_outgoings = sum(
            (
                rule.amount
                for rule in due_soon
                if rule.amount is not None and rule.transaction_type == "expense"
            ),
            start=Decimal("0"),
        )
        expected_income = sum(
            (
                rule.amount
                for rule in due_soon
                if rule.amount is not None and rule.transaction_type == "income"
            ),
            start=Decimal("0"),
        )
        return {
            "overdue_count": len(overdue),
            "due_soon_count": len(due_soon),
            "expected_30_days": expected_outgoings,
            "expected_income_30_days": expected_income,
            "expected_outgoings_30_days": expected_outgoings,
            "variable_count": sum(
                1 for rule in overdue + due_soon if rule.amount_mode == "variable"
            ),
        }

    def record_payment(
        self,
        rule_id: str,
        actual_amount: object = None,
        transaction_date: str | None = None,
    ):
        with unit_of_work(self.db):
            rule = self._active_rule(rule_id)
            if rule.amount_mode == "variable":
                if actual_amount is None or not str(actual_amount).strip():
                    raise ValueError("Actual amount is required for a variable bill")
                amount = require_positive(actual_amount)
            else:
                amount = (
                    require_positive(actual_amount)
                    if actual_amount is not None and str(actual_amount).strip()
                    else rule.amount
                )
                assert amount is not None
            recorded_date = require_iso_date(transaction_date or today_iso())
            add_transaction = (
                self.transactions.add_income
                if rule.transaction_type == "income"
                else self.transactions.add_expense
            )
            transaction = add_transaction(
                rule.account_id,
                amount,
                recorded_date,
                rule.name,
                category_id=rule.category_id,
                payment_method_id=rule.payment_method_id,
                notes=rule.notes,
                recurring_rule_id=rule.id,
            )
            self._advance(rule, recorded_date)
            self.rules.update(rule)
            return transaction

    def skip_occurrence(self, rule_id: str) -> RecurringRule:
        with unit_of_work(self.db):
            rule = self._active_rule(rule_id)
            self._advance(rule)
            return self.rules.update(rule)

    def set_paused(self, rule_id: str, paused: bool) -> RecurringRule:
        with unit_of_work(self.db):
            rule = self._rule(rule_id)
            if rule.status == "completed":
                raise ValueError("Completed schedules cannot be resumed")
            rule.status = "paused" if paused else "active"
            return self.rules.update(rule)

    def delete_rule(self, rule_id: str) -> None:
        with unit_of_work(self.db):
            self._rule(rule_id)
            self.rules.delete(rule_id)

    def _advance(self, rule: RecurringRule, recorded_date: str | None = None) -> None:
        current = date.fromisoformat(rule.next_due_date)
        anchor_day = date.fromisoformat(rule.start_date).day
        if rule.frequency == "weekly":
            next_due = current + timedelta(days=7)
        elif rule.frequency == "monthly":
            next_due = self._add_months(current, 1, anchor_day)
        elif rule.frequency == "quarterly":
            next_due = self._add_months(current, 3, anchor_day)
        else:
            next_due = self._add_months(current, 12, anchor_day)
        rule.next_due_date = next_due.isoformat()
        if recorded_date:
            rule.last_recorded_date = recorded_date
        if rule.end_date and rule.next_due_date > rule.end_date:
            rule.status = "completed"

    @staticmethod
    def _add_months(value: date, months: int, anchor_day: int) -> date:
        month_index = value.year * 12 + value.month - 1 + months
        year, zero_based_month = divmod(month_index, 12)
        month = zero_based_month + 1
        day = min(anchor_day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    def _rule(self, rule_id: str) -> RecurringRule:
        rule = self.rules.get(rule_id)
        if not rule:
            raise ValueError("Recurring payment not found")
        return rule

    def _active_rule(self, rule_id: str) -> RecurringRule:
        rule = self._rule(rule_id)
        if rule.status != "active":
            raise ValueError("Recurring payment is not active")
        return rule

    def _account(self, account_id: str) -> str:
        account = self.accounts.get(account_id)
        if not account:
            raise ValueError("Account not found")
        if not account.is_active:
            raise ValueError("Account is inactive")
        return account_id

    def _category(self, category_id: str | None, transaction_type: str) -> str | None:
        if not category_id:
            return None
        category = self.categories.get(category_id)
        if not category or not category.is_active:
            raise ValueError("Category is unavailable")
        if category.type != self._transaction_type(transaction_type):
            raise ValueError("Category type must match the recurring schedule")
        return category.id

    def _payment_method(self, method_id: str | None, account_id: str) -> str | None:
        if not method_id:
            return None
        method = self.payment_methods.get(method_id)
        if not method or not method.is_active:
            raise ValueError("Payment method is unavailable")
        if method.account_id != account_id:
            raise ValueError("Payment method does not belong to the selected account")
        return method.id

    def _kind(self, value: str) -> str:
        if value not in self.KINDS:
            raise ValueError("Recurring payment type is not supported")
        return value

    def _amount_mode(self, value: str) -> str:
        if value not in self.AMOUNT_MODES:
            raise ValueError("Amount mode is not supported")
        return value

    def _amount(self, mode: str, value: object):
        normalized_mode = self._amount_mode(mode)
        if normalized_mode == "fixed":
            return require_positive(value)
        if value is None or not str(value).strip():
            return None
        return require_positive(value)

    def _frequency(self, value: str) -> str:
        if value not in self.FREQUENCIES:
            raise ValueError("Frequency is not supported")
        return value

    def _transaction_type(self, value: str) -> str:
        if value not in self.TRANSACTION_TYPES:
            raise ValueError("Recurring schedule must be income or expense")
        return value

    @staticmethod
    def _end_date(value: str | None, next_due_date: str) -> str | None:
        if not value:
            return None
        end_date = require_iso_date(value)
        if end_date < next_due_date:
            raise ValueError("End date cannot be before the next due date")
        return end_date

    @staticmethod
    def _reminder_days(value: int) -> int:
        days = int(value)
        if not 0 <= days <= 90:
            raise ValueError("Reminder must be between 0 and 90 days")
        return days

    @staticmethod
    def _notes(value: str | None) -> str | None:
        cleaned = (value or "").strip()
        return cleaned or None
