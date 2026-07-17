from __future__ import annotations

import json
import sqlite3
from hmac import compare_digest
from uuid import uuid4


UTC_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


class SyncRepository:
    """Persistence primitives for a future validated change-exchange service."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def local_device_id(self) -> str:
        return self._metadata("local_device_id")

    def active_device_id(self) -> str:
        return self._metadata("active_device_id")

    def set_active_device(self, device_id: str) -> None:
        if not self.db.execute("SELECT 1 FROM devices WHERE id = ?", (device_id,)).fetchone():
            raise ValueError("Device is not registered")
        self.db.execute(
            "UPDATE sync_metadata SET value = ? WHERE key = 'active_device_id'",
            (device_id,),
        )

    def register_device(
        self,
        display_name: str,
        certificate_fingerprint: str,
        *,
        device_id: str | None = None,
        auth_token_hash: str | None = None,
    ) -> str:
        registered_id = device_id or str(uuid4())
        self.db.execute(
            f"""
            INSERT INTO devices (
                id, display_name, certificate_fingerprint, auth_token_hash, is_local
            ) VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(id) DO UPDATE SET
                display_name = excluded.display_name,
                certificate_fingerprint = excluded.certificate_fingerprint,
                auth_token_hash = excluded.auth_token_hash,
                revoked_at = NULL,
                paired_at = {UTC_NOW}
            """,
            (
                registered_id,
                display_name.strip(),
                certificate_fingerprint.strip(),
                auth_token_hash,
            ),
        )
        return registered_id

    def authenticate_device(self, device_id: str, token_hash: str) -> bool:
        row = self.db.execute(
            """
            SELECT auth_token_hash
            FROM devices
            WHERE id = ? AND is_local = 0 AND revoked_at IS NULL
            """,
            (device_id,),
        ).fetchone()
        return bool(
            row
            and row["auth_token_hash"]
            and compare_digest(str(row["auth_token_hash"]), token_hash)
        )

    def touch_device(self, device_id: str) -> None:
        self.db.execute(
            f"UPDATE devices SET last_seen_at = {UTC_NOW} WHERE id = ?",
            (device_id,),
        )

    def revoke_device(self, device_id: str) -> None:
        cursor = self.db.execute(
            f"""
            UPDATE devices
            SET revoked_at = {UTC_NOW}, auth_token_hash = NULL
            WHERE id = ? AND is_local = 0 AND revoked_at IS NULL
            """,
            (device_id,),
        )
        if cursor.rowcount != 1:
            raise ValueError("Paired device not found")

    def list_devices(self) -> list[sqlite3.Row]:
        return self.db.execute(
            """
            SELECT id, display_name, paired_at, last_seen_at, revoked_at
            FROM devices
            WHERE is_local = 0
            ORDER BY revoked_at IS NOT NULL, display_name COLLATE NOCASE
            """
        ).fetchall()

    def changes_since(self, sequence: int, limit: int = 500) -> list[sqlite3.Row]:
        if sequence < 0:
            raise ValueError("Change sequence cannot be negative")
        if limit <= 0:
            raise ValueError("Change batch size must be positive")
        return self.db.execute(
            """
            SELECT sequence, entity_type, entity_id, operation, revision, device_id, changed_at
            FROM change_log
            WHERE sequence > ?
            ORDER BY sequence
            LIMIT ?
            """,
            (sequence, limit),
        ).fetchall()

    def cursor_for(self, device_id: str) -> int:
        row = self.db.execute(
            "SELECT last_change_sequence FROM sync_cursors WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        return int(row["last_change_sequence"]) if row else 0

    def advance_cursor(self, device_id: str, sequence: int) -> None:
        if sequence < self.cursor_for(device_id):
            raise ValueError("Sync cursor cannot move backwards")
        self.db.execute(
            f"""
            INSERT INTO sync_cursors (device_id, last_change_sequence)
            VALUES (?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                last_change_sequence = excluded.last_change_sequence,
                updated_at = {UTC_NOW}
            """,
            (device_id, sequence),
        )

    def max_change_sequence(self) -> int:
        row = self.db.execute(
            "SELECT COALESCE(MAX(sequence), 0) AS sequence FROM change_log"
        ).fetchone()
        return int(row["sequence"])

    def command_receipt(self, command_id: str) -> sqlite3.Row | None:
        return self.db.execute(
            "SELECT * FROM sync_commands WHERE command_id = ?",
            (command_id,),
        ).fetchone()

    def save_command_receipt(
        self,
        command_id: str,
        device_id: str,
        command_type: str,
        payload_hash: str,
        status: str,
        result_payload: dict | None,
        error_message: str | None,
    ) -> None:
        self.db.execute(
            """
            INSERT INTO sync_commands (
                command_id, device_id, command_type, payload_hash, status,
                result_payload, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                command_id,
                device_id,
                command_type,
                payload_hash,
                status,
                (
                    json.dumps(result_payload, sort_keys=True, separators=(",", ":"))
                    if result_payload is not None
                    else None
                ),
                error_message,
            ),
        )

    def record_conflict(
        self,
        device_id: str,
        entity_type: str,
        entity_id: str,
        local_revision: int,
        remote_revision: int,
        local_payload: dict,
        remote_payload: dict,
    ) -> str:
        conflict_id = str(uuid4())
        self.db.execute(
            """
            INSERT INTO conflicts (
                id, device_id, entity_type, entity_id, local_revision,
                remote_revision, local_payload, remote_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conflict_id,
                device_id,
                entity_type,
                entity_id,
                local_revision,
                remote_revision,
                json.dumps(local_payload, sort_keys=True, separators=(",", ":")),
                json.dumps(remote_payload, sort_keys=True, separators=(",", ":")),
            ),
        )
        return conflict_id

    def list_conflicts(self, status: str = "pending") -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM conflicts WHERE status = ? ORDER BY created_at, id",
            (status,),
        ).fetchall()

    def resolve_conflict(self, conflict_id: str, *, ignored: bool = False) -> None:
        status = "ignored" if ignored else "resolved"
        cursor = self.db.execute(
            f"""
            UPDATE conflicts
            SET status = ?, resolved_at = {UTC_NOW}
            WHERE id = ? AND status = 'pending'
            """,
            (status, conflict_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("Pending conflict not found")

    def _metadata(self, key: str) -> str:
        row = self.db.execute(
            "SELECT value FROM sync_metadata WHERE key = ?", (key,)
        ).fetchone()
        if not row:
            raise RuntimeError(f"Missing synchronization metadata: {key}")
        return str(row["value"])
