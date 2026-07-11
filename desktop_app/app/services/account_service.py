from __future__ import annotations

import sqlite3
from decimal import Decimal

from app.models.account import Account
from app.repositories.account_repository import AccountRepository
from app.utils.money import to_decimal
from app.utils.validators import require_text


class AccountService:
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
        self._validate_parent(parent_id)
        return self.accounts.create(
            Account(
                id=None,
                name=require_text(name, "Account name"),
                type=require_text(account_type, "Account type"),
                parent_id=parent_id,
                opening_balance=to_decimal(opening_balance),
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
        existing = self._require_account(account_id)
        self._validate_parent(parent_id, account_id)
        existing.name = require_text(name, "Account name")
        existing.type = require_text(account_type, "Account type")
        existing.parent_id = parent_id
        existing.opening_balance = to_decimal(opening_balance)
        existing.is_active = is_active
        existing.display_order = display_order
        return self.accounts.update(existing)

    def deactivate_account(self, account_id: int) -> None:
        self._require_account(account_id)
        self.accounts.deactivate(account_id)

    def list_accounts(self, include_inactive: bool = False) -> list[Account]:
        return self.accounts.list(include_inactive=include_inactive)

    def account_balance(self, account_id: int) -> Decimal:
        account = self._require_account(account_id)
        row = self.db.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions WHERE account_id = ?",
            (account_id,),
        ).fetchone()
        return account.opening_balance + Decimal(str(row["total"] or 0))

    def account_tree(self, include_inactive: bool = False) -> list[dict]:
        accounts = self.accounts.list(include_inactive=include_inactive)
        balances = {account.id: self.account_balance(int(account.id)) for account in accounts if account.id}
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
