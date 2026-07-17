from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from decimal import Decimal
from uuid import UUID

from app.core.app_info import APP_VERSION
from app.core.database import unit_of_work
from app.repositories.sync_repository import SyncRepository
from app.services.recurring_service import RecurringService
from app.services.transaction_service import TransactionService
from app.sync.protocol import COMMAND_TYPES, PROTOCOL_VERSION, SYNC_ENTITIES


class SyncService:
    """Validated command exchange for an independently stored mobile database."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.sync = SyncRepository(db)

    def hello(self) -> dict:
        return {
            "app": "Money Manager",
            "app_version": APP_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "storage": "independent_sqlite",
        }

    def pair_device(
        self,
        device_id: str,
        display_name: str,
        server_fingerprint: str,
    ) -> dict:
        normalized_id = self._uuid(device_id, "Device id")
        cleaned_name = display_name.strip()
        if not cleaned_name:
            raise ValueError("Device name is required")
        token = secrets.token_urlsafe(32)
        token_hash = self.token_hash(token)
        with unit_of_work(self.db):
            self.sync.register_device(
                cleaned_name,
                server_fingerprint,
                device_id=normalized_id,
                auth_token_hash=token_hash,
            )
        return {
            "device_id": normalized_id,
            "auth_token": token,
            "protocol_version": PROTOCOL_VERSION,
        }

    def authenticate(self, device_id: str, token: str) -> bool:
        if not device_id or not token:
            return False
        return self.sync.authenticate_device(device_id, self.token_hash(token))

    def exchange(
        self,
        device_id: str,
        cursor: int,
        commands: list[dict] | None = None,
        *,
        limit: int = 1000,
    ) -> dict:
        normalized_id = self._uuid(device_id, "Device id")
        if cursor < 0:
            raise ValueError("Sync cursor cannot be negative")
        command_results = [
            self._apply_command(normalized_id, command)
            for command in (commands or [])
        ]
        changes, next_cursor, has_more, snapshot = self._changes(cursor, limit)
        with unit_of_work(self.db):
            self.sync.advance_cursor(normalized_id, next_cursor)
            self.sync.touch_device(normalized_id)
        return {
            "protocol_version": PROTOCOL_VERSION,
            "snapshot": snapshot,
            "cursor": next_cursor,
            "has_more": has_more,
            "commands": command_results,
            "changes": changes,
        }

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _apply_command(self, device_id: str, command: dict) -> dict:
        if not isinstance(command, dict):
            raise ValueError("Each sync command must be an object")
        command_id = self._uuid(str(command.get("id", "")), "Command id")
        command_type = str(command.get("type", ""))
        payload = command.get("payload") or {}
        if command_type not in COMMAND_TYPES:
            raise ValueError("Sync command type is not supported")
        if not isinstance(payload, dict):
            raise ValueError("Sync command payload must be an object")
        payload_hash = self._payload_hash(command_type, payload)

        existing = self.sync.command_receipt(command_id)
        if existing:
            if existing["device_id"] != device_id or existing["payload_hash"] != payload_hash:
                return {
                    "id": command_id,
                    "status": "rejected",
                    "error": "Command id was reused with different data",
                }
            return self._receipt_payload(existing)

        local_device_id = self.sync.local_device_id()
        with unit_of_work(self.db):
            self.sync.set_active_device(device_id)
            try:
                try:
                    result = self._dispatch(command_type, payload)
                    status = "accepted"
                    error = None
                except ValueError as exc:
                    result = None
                    status = "rejected"
                    error = str(exc)
                self.sync.save_command_receipt(
                    command_id,
                    device_id,
                    command_type,
                    payload_hash,
                    status,
                    result,
                    error,
                )
            finally:
                self.sync.set_active_device(local_device_id)
        return {
            "id": command_id,
            "status": status,
            **({"result": result} if result is not None else {}),
            **({"error": error} if error else {}),
        }

    def _dispatch(self, command_type: str, payload: dict) -> dict:
        transactions = TransactionService(self.db)
        if command_type in {"create_income", "create_expense", "create_transfer"}:
            common = {
                "amount": self._amount(payload.get("amount_cents")),
                "date": str(payload.get("date", "")),
                "description": str(payload.get("description", "")),
                "notes": self._optional_text(payload.get("notes")),
            }
        if command_type == "create_income":
            created = transactions.add_income(
                str(payload.get("account_id", "")),
                category_id=payload.get("category_id"),
                payment_method_id=self._optional_text(payload.get("payment_method_id")),
                **common,
            )
            return {"entity_ids": [created.id]}
        if command_type == "create_expense":
            created = transactions.add_expense(
                str(payload.get("account_id", "")),
                category_id=payload.get("category_id"),
                payment_method_id=self._optional_text(payload.get("payment_method_id")),
                **common,
            )
            return {"entity_ids": [created.id]}
        if command_type == "create_transfer":
            outgoing, incoming = transactions.add_transfer(
                str(payload.get("source_account_id", "")),
                str(payload.get("target_account_id", "")),
                **common,
            )
            return {"entity_ids": [outgoing.id, incoming.id]}
        if command_type == "record_recurring":
            amount_cents = payload.get("amount_cents")
            created = RecurringService(self.db).record_payment(
                str(payload.get("rule_id", "")),
                actual_amount=(
                    self._amount(amount_cents) if amount_cents is not None else None
                ),
                transaction_date=self._optional_text(payload.get("date")),
            )
            return {"entity_ids": [created.id]}
        raise ValueError("Sync command type is not supported")

    def _changes(self, cursor: int, limit: int) -> tuple[list[dict], int, bool, bool]:
        if limit <= 0:
            raise ValueError("Sync batch size must be positive")
        if cursor == 0:
            changes = []
            for entity_type in SYNC_ENTITIES:
                for row in self.db.execute(f"SELECT * FROM {entity_type}"):
                    payload = dict(row)
                    changes.append(
                        self._change_payload(
                            entity_type,
                            str(payload["id"]),
                            payload,
                        )
                    )
            return changes, self.sync.max_change_sequence(), False, True

        rows = self.sync.changes_since(cursor, limit)
        next_cursor = int(rows[-1]["sequence"]) if rows else cursor
        latest: dict[tuple[str, str], dict] = {}
        for row in rows:
            entity_type = str(row["entity_type"])
            if entity_type not in SYNC_ENTITIES:
                continue
            entity_id = str(row["entity_id"])
            stored = self.db.execute(
                f"SELECT * FROM {entity_type} WHERE id = ?",
                (entity_id,),
            ).fetchone()
            if stored:
                latest[(entity_type, entity_id)] = self._change_payload(
                    entity_type,
                    entity_id,
                    dict(stored),
                )
        has_more = bool(
            self.db.execute(
                "SELECT 1 FROM change_log WHERE sequence > ? LIMIT 1",
                (next_cursor,),
            ).fetchone()
        )
        return list(latest.values()), next_cursor, has_more, False

    @staticmethod
    def _change_payload(entity_type: str, entity_id: str, payload: dict) -> dict:
        deleted = payload.get("deleted_at") is not None
        return {
            "entity": entity_type,
            "id": entity_id,
            "operation": "delete" if deleted else "upsert",
            "revision": int(payload.get("revision", 1)),
            "payload": payload,
        }

    @staticmethod
    def _payload_hash(command_type: str, payload: dict) -> str:
        encoded = json.dumps(
            {"type": command_type, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _receipt_payload(row: sqlite3.Row) -> dict:
        result = json.loads(row["result_payload"]) if row["result_payload"] else None
        return {
            "id": row["command_id"],
            "status": row["status"],
            **({"result": result} if result is not None else {}),
            **({"error": row["error_message"]} if row["error_message"] else {}),
        }

    @staticmethod
    def _amount(value: object) -> Decimal:
        if isinstance(value, bool):
            raise ValueError("Amount must be integer cents")
        try:
            cents = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Amount must be integer cents") from exc
        if cents <= 0:
            raise ValueError("Amount must be greater than zero")
        return Decimal(cents) / Decimal(100)

    @staticmethod
    def _uuid(value: str, label: str) -> str:
        try:
            return str(UUID(value))
        except (ValueError, AttributeError) as exc:
            raise ValueError(f"{label} must be a UUID") from exc

    @staticmethod
    def _optional_text(value: object) -> str | None:
        cleaned = str(value or "").strip()
        return cleaned or None
