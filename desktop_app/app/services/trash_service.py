from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.core.database import unit_of_work


UTC_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


@dataclass(frozen=True)
class TrashItem:
    entity_type: str
    entity_id: str
    label: str
    detail: str
    deleted_at: str


class TrashService:
    """Recover user-visible records that were soft deleted for synchronization."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def list_items(self) -> list[TrashItem]:
        items = self._deleted_transactions() + self._deleted_recurring_rules()
        return sorted(items, key=lambda item: item.deleted_at, reverse=True)

    def restore(self, entity_type: str, entity_id: str) -> None:
        with unit_of_work(self.db):
            if entity_type == "transactions":
                self._restore_transaction(entity_id)
            elif entity_type == "recurring_rules":
                self._restore_single("recurring_rules", entity_id)
            else:
                raise ValueError("This deleted item cannot be restored here")

    def _deleted_transactions(self) -> list[TrashItem]:
        rows = self.db.execute(
            """
            SELECT transactions.id, transactions.date, transactions.type,
                   transactions.description, transactions.transfer_group_id,
                   transactions.deleted_at
            FROM transactions
            JOIN tombstones
              ON tombstones.entity_type = 'transactions'
             AND tombstones.entity_id = transactions.id
            WHERE transactions.deleted_at IS NOT NULL
            ORDER BY transactions.deleted_at DESC
            """
        ).fetchall()
        items: list[TrashItem] = []
        seen_transfers: set[str] = set()
        for row in rows:
            transfer_group = row["transfer_group_id"]
            if transfer_group and transfer_group in seen_transfers:
                continue
            if transfer_group:
                seen_transfers.add(transfer_group)
            kind = "Transfer" if transfer_group else str(row["type"]).replace("_", " ").title()
            label = str(row["description"] or kind)
            items.append(
                TrashItem(
                    "transactions",
                    str(row["id"]),
                    label,
                    f"{kind} on {row['date']}",
                    str(row["deleted_at"]),
                )
            )
        return items

    def _deleted_recurring_rules(self) -> list[TrashItem]:
        return [
            TrashItem(
                "recurring_rules",
                str(row["id"]),
                str(row["name"]),
                f"{str(row['kind']).title()} recurring payment",
                str(row["deleted_at"]),
            )
            for row in self.db.execute(
                """
                SELECT recurring_rules.id, recurring_rules.name, recurring_rules.kind,
                       recurring_rules.deleted_at
                FROM recurring_rules
                JOIN tombstones
                  ON tombstones.entity_type = 'recurring_rules'
                 AND tombstones.entity_id = recurring_rules.id
                WHERE recurring_rules.deleted_at IS NOT NULL
                ORDER BY recurring_rules.deleted_at DESC
                """
            )
        ]

    def _restore_transaction(self, transaction_id: str) -> None:
        row = self.db.execute(
            """
            SELECT id, transfer_group_id FROM transactions
            WHERE id = ? AND deleted_at IS NOT NULL
            """,
            (transaction_id,),
        ).fetchone()
        if not row:
            raise ValueError("Deleted transaction not found")
        if row["transfer_group_id"]:
            ids = [
                str(item["id"])
                for item in self.db.execute(
                    """
                    SELECT id FROM transactions
                    WHERE transfer_group_id = ? AND deleted_at IS NOT NULL
                    """,
                    (row["transfer_group_id"],),
                )
            ]
        else:
            ids = [str(row["id"])]
        for item_id in ids:
            self._restore_single("transactions", item_id)

    def _restore_single(self, table: str, entity_id: str) -> None:
        if table not in {"transactions", "recurring_rules"}:
            raise ValueError("Unsupported trash entity")
        cursor = self.db.execute(
            f"""
            UPDATE {table}
            SET deleted_at = NULL, updated_at = {UTC_NOW}, revision = revision + 1
            WHERE id = ? AND deleted_at IS NOT NULL
            """,
            (entity_id,),
        )
        if cursor.rowcount != 1:
            raise ValueError("Deleted item not found")
        self.db.execute(
            "DELETE FROM tombstones WHERE entity_type = ? AND entity_id = ?",
            (table, entity_id),
        )
