from __future__ import annotations

import sqlite3
from decimal import Decimal

from app.core.database import unit_of_work
from app.models.account import Account
from app.repositories.account_repository import AccountRepository
from app.utils.money import to_decimal
from app.utils.validators import require_text


class AccountService:
    LIABILITY_TYPES = {"credit_card", "loan", "mortgage", "liability"}

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.accounts = AccountRepository(db)

    def create_account(
        self,
        name: str,
        account_type: str,
        parent_id: int | None = None,
        opening_balance: object = "0",
        is_active: bool = True,
        display_order: int = 0,
    ) -> Account:
        with unit_of_work(self.db):
            self._validate_parent(parent_id)
            return self.accounts.create(
                Account(
                    id=None,
                    name=require_text(name, "Account name"),
                    type=require_text(account_type, "Account type"),
                    parent_id=parent_id,
                    opening_balance=self._opening_balance(account_type, opening_balance),
                    is_active=is_active,
                    display_order=display_order,
                )
            )

    def update_account(
        self,
        account_id: int,
        name: str,
        account_type: str,
        parent_id: int | None,
        opening_balance: object,
        is_active: bool = True,
        display_order: int = 0,
    ) -> Account:
        with unit_of_work(self.db):
            existing = self._require_account(account_id)
            self._validate_parent(parent_id, account_id)
            if not is_active and self.accounts.has_active_children(account_id):
                raise ValueError("Deactivate active child accounts first")
            existing.name = require_text(name, "Account name")
            existing.type = require_text(account_type, "Account type")
            existing.parent_id = parent_id
            existing.opening_balance = self._opening_balance(account_type, opening_balance)
            existing.is_active = is_active
            existing.display_order = display_order
            return self.accounts.update(existing)

    def deactivate_account(self, account_id: int) -> None:
        with unit_of_work(self.db):
            self._require_account(account_id)
            if self.accounts.has_active_children(account_id):
                raise ValueError("Deactivate active child accounts first")
            self.accounts.deactivate(account_id)

    def list_accounts(self, include_inactive: bool = False) -> list[Account]:
        return self.accounts.list(include_inactive=include_inactive)

    def account_balance(self, account_id: int) -> Decimal:
        balance = self.accounts.balance(account_id)
        if balance is None:
            raise ValueError("Account not found")
        return balance

    def account_tree(self, include_inactive: bool = False) -> list[dict]:
        account_balances = self.accounts.list_with_balances(include_inactive=include_inactive)
        accounts = [account for account, _balance in account_balances]
        balances = {account.id: balance for account, balance in account_balances}
        nodes = {
            account.id: {
                "account": account,
                "balance": balances.get(account.id, Decimal("0")),
                "rollup_balance": balances.get(account.id, Decimal("0")),
                "children": [],
            }
            for account in accounts
        }
        roots: list[dict] = []
        for account in accounts:
            node = nodes[account.id]
            parent = nodes.get(account.parent_id)
            if parent:
                parent["children"].append(node)
            else:
                roots.append(node)

        def rollup(node: dict) -> Decimal:
            node["children"].sort(key=lambda child: (child["account"].display_order, child["account"].name.lower()))
            total = node["balance"]
            for child in node["children"]:
                total += rollup(child)
            node["rollup_balance"] = total
            return total

        roots.sort(key=lambda item: (item["account"].display_order, item["account"].name.lower()))
        for root in roots:
            rollup(root)
        return roots

    def _require_account(self, account_id: int) -> Account:
        account = self.accounts.get(account_id)
        if not account:
            raise ValueError("Account not found")
        return account

    def _validate_parent(self, parent_id: int | None, account_id: int | None = None) -> None:
        if parent_id is None:
            return
        if account_id and parent_id == account_id:
            raise ValueError("An account cannot be its own parent")
        parent = self._require_account(parent_id)
        if not parent.is_active:
            raise ValueError("Parent account must be active")
        if account_id and parent_id in self._descendant_ids(account_id):
            raise ValueError("Circular account hierarchy detected")
        if self._depth(parent_id) + 1 > 3:
            raise ValueError("Account hierarchy can be at most three levels deep")

    def _depth(self, account_id: int) -> int:
        depth = 1
        seen = {account_id}
        account = self._require_account(account_id)
        while account.parent_id is not None:
            if account.parent_id in seen:
                raise ValueError("Circular account hierarchy detected")
            seen.add(account.parent_id)
            account = self._require_account(account.parent_id)
            depth += 1
        return depth

    def _descendant_ids(self, account_id: int) -> set[int]:
        rows = self.db.execute("SELECT id, parent_id FROM accounts").fetchall()
        children: dict[int, list[int]] = {}
        for row in rows:
            if row["parent_id"] is not None:
                children.setdefault(row["parent_id"], []).append(row["id"])
        descendants: set[int] = set()
        stack = list(children.get(account_id, []))
        while stack:
            child_id = stack.pop()
            if child_id in descendants:
                continue
            descendants.add(child_id)
            stack.extend(children.get(child_id, []))
        return descendants

    def _opening_balance(self, account_type: str, value: object) -> Decimal:
        balance = to_decimal(value)
        if account_type in self.LIABILITY_TYPES and balance > 0:
            return -balance
        return balance
