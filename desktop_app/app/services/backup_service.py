from __future__ import annotations

import base64
import os
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from app.core.database_security import (
    backup_connection,
    connection_is_encrypted,
    is_plain_sqlite_file,
    open_local_database,
    restore_connection,
)
from app.core.paths import backup_dir, database_path, ensure_app_dirs
from app.core.migrations import SCHEMA_VERSION, assert_database_integrity, migrate
from app.utils.dates import timestamp_for_filename


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    created_at: float
    size_bytes: int
    kind: str
    protection: str
    status: str


@dataclass(frozen=True)
class BackupInspection:
    path: Path
    schema_version: int
    encrypted: bool
    integrity: str = "ok"


class BackupService:
    DAILY_RETENTION = 14
    ENCRYPTED_HEADER = b"MMDBACKUP\x01"
    ENCRYPTED_SUFFIX = ".mmbak"
    SALT_SIZE = 16
    MINIMUM_PASSWORD_LENGTH = 10
    SCRYPT_N = 2**15
    SCRYPT_R = 8
    SCRYPT_P = 1

    def __init__(self, db: sqlite3.Connection, db_path: Path | None = None):
        self.db = db
        self.db_path = db_path or database_path()

    def create_backup(self) -> Path:
        ensure_app_dirs()
        target = backup_dir() / f"money_manager_backup_{timestamp_for_filename()}.db"
        self._write_backup(target)
        return target

    def create_encrypted_backup(self, password: str) -> Path:
        """Create an authenticated backup protected by a user-supplied password."""
        ensure_app_dirs()
        password_bytes = self._new_password(password)
        salt = os.urandom(self.SALT_SIZE)
        encrypted = Fernet(self._derive_key(password_bytes, salt)).encrypt(
            self._verified_backup_bytes()
        )
        target = backup_dir() / (
            f"money_manager_encrypted_{timestamp_for_filename()}"
            f"{self.ENCRYPTED_SUFFIX}"
        )
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_bytes(self.ENCRYPTED_HEADER + salt + encrypted)
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return target

    def list_backups(self) -> list[BackupInfo]:
        """Return plain-language metadata for every locally managed backup."""
        ensure_app_dirs()
        candidates = {
            candidate.resolve()
            for pattern in ("*.db", f"*{self.ENCRYPTED_SUFFIX}")
            for candidate in backup_dir().glob(pattern)
            if candidate.is_file()
        }
        backups: list[BackupInfo] = []
        for candidate in candidates:
            encrypted = self.is_encrypted_backup(candidate)
            device_encrypted = (
                candidate.suffix.lower() == ".db"
                and not is_plain_sqlite_file(candidate)
            )
            if candidate.name.startswith("money_manager_daily_"):
                kind = "Automatic daily"
            elif candidate.name.startswith("money_manager_before_restore_"):
                kind = "Before restore"
            elif candidate.name.startswith("money_manager_pre_migration_"):
                kind = "Before upgrade"
            elif encrypted:
                kind = "Secure manual"
            else:
                kind = "Manual"

            if encrypted:
                protection = "Password"
                status = "Locked"
            elif device_encrypted:
                protection = "Windows account"
                try:
                    self.inspect_backup(candidate)
                except (OSError, ValueError, RuntimeError, *self._database_errors()):
                    status = "Needs attention"
                else:
                    status = "Ready"
            else:
                protection = "None"
                try:
                    self.inspect_backup(candidate)
                except (OSError, ValueError, RuntimeError, *self._database_errors()):
                    status = "Needs attention"
                else:
                    status = "Ready"
            metadata = candidate.stat()
            backups.append(
                BackupInfo(
                    path=candidate,
                    created_at=metadata.st_mtime,
                    size_bytes=metadata.st_size,
                    kind=kind,
                    protection=protection,
                    status=status,
                )
            )
        return sorted(backups, key=lambda item: item.created_at, reverse=True)

    def inspect_backup(
        self,
        source: Path,
        password: str | None = None,
    ) -> BackupInspection:
        """Verify that a backup is authentic, intact, and supported."""
        source = Path(source).expanduser().resolve()
        if not source.is_file():
            raise ValueError("Choose an existing Money Manager backup")
        password_encrypted = self.is_encrypted_backup(source)
        device_encrypted = (
            source.suffix.lower() == ".db" and not is_plain_sqlite_file(source)
        )
        if source.suffix.lower() == self.ENCRYPTED_SUFFIX and not password_encrypted:
            raise ValueError("This encrypted backup is damaged or unsupported")
        temporary_source = (
            self._decrypt_backup_to_temporary_file(source, password)
            if password_encrypted
            else None
        )
        try:
            candidate = self._open_source(temporary_source or source)
            try:
                assert_database_integrity(candidate)
                source_version = int(
                    candidate.execute("PRAGMA user_version").fetchone()[0]
                )
                if source_version > SCHEMA_VERSION:
                    raise ValueError(
                        f"This backup needs a newer app (schema {source_version})"
                    )
                return BackupInspection(
                    path=source,
                    schema_version=source_version,
                    encrypted=password_encrypted or device_encrypted,
                )
            finally:
                candidate.close()
        finally:
            if temporary_source:
                self._remove_temporary_database(temporary_source)

    def ensure_daily_backup(self, retention: int = DAILY_RETENTION) -> Path | None:
        """Create at most one verified automatic backup per local calendar day."""
        ensure_app_dirs()
        target = backup_dir() / f"money_manager_daily_{date.today():%Y%m%d}.db"
        if target.exists():
            existing = self._open_source(target)
            try:
                assert_database_integrity(existing)
            except Exception:
                existing.close()
                target.unlink(missing_ok=True)
            else:
                existing.close()
                return None
        self._write_backup(target)
        self._rotate("money_manager_daily_", retention)
        return target

    def restore_backup(self, source: Path, password: str | None = None) -> Path:
        """Restore a verified SQLite backup and retain a rollback copy."""
        ensure_app_dirs()
        source = Path(source).expanduser().resolve()
        if not source.is_file():
            raise ValueError("Choose an existing Money Manager backup")
        if source == self.db_path.expanduser().resolve():
            raise ValueError("The active database cannot be restored over itself")
        if self.db.in_transaction:
            raise RuntimeError("Cannot restore while a database operation is in progress")

        encrypted = self.is_encrypted_backup(source)
        if source.suffix.lower() == self.ENCRYPTED_SUFFIX and not encrypted:
            raise ValueError("This encrypted backup is damaged or unsupported")
        temporary_source = (
            self._decrypt_backup_to_temporary_file(source, password)
            if encrypted
            else None
        )
        try:
            candidate = self._open_source(temporary_source or source)
        except Exception:
            if temporary_source:
                self._remove_temporary_database(temporary_source)
            raise
        try:
            assert_database_integrity(candidate)
            source_version = int(candidate.execute("PRAGMA user_version").fetchone()[0])
            if source_version > SCHEMA_VERSION:
                raise ValueError(
                    f"This backup needs a newer app (schema {source_version})"
                )

            rollback = backup_dir() / (
                f"money_manager_before_restore_{timestamp_for_filename()}.db"
            )
            self._write_backup(rollback)
            try:
                self._restore_connection(candidate)
            except Exception:
                self._restore_from(rollback)
                raise
            return rollback
        finally:
            candidate.close()
            if temporary_source:
                self._remove_temporary_database(temporary_source)

    def _write_backup(self, target: Path) -> None:
        if self.db.in_transaction:
            raise RuntimeError("Cannot back up while a database operation is in progress")
        assert_database_integrity(self.db)
        try:
            backup_connection(self.db, target)
            destination = open_local_database(target, read_only=True)
            try:
                destination.execute("PRAGMA foreign_keys = ON")
                assert_database_integrity(destination)
            finally:
                destination.close()
        except Exception:
            target.unlink(missing_ok=True)
            raise

    def _verified_backup_bytes(self) -> bytes:
        temporary = backup_dir() / f".encrypt-source-{uuid4().hex}.db"
        try:
            if connection_is_encrypted(self.db):
                backup_connection(self.db, temporary, portable_plaintext=True)
                candidate = sqlite3.connect(temporary)
                try:
                    candidate.row_factory = sqlite3.Row
                    candidate.execute("PRAGMA foreign_keys = ON")
                    assert_database_integrity(candidate)
                finally:
                    candidate.close()
            else:
                self._write_backup(temporary)
            return temporary.read_bytes()
        finally:
            self._remove_temporary_database(temporary)

    def _restore_from(self, source: Path) -> None:
        candidate = self._open_source(source)
        try:
            self._restore_connection(candidate)
        finally:
            candidate.close()

    def _restore_connection(self, candidate: sqlite3.Connection) -> None:
        restore_connection(candidate, self.db)
        self.db.execute("PRAGMA foreign_keys = ON")
        migrate(self.db)
        assert_database_integrity(self.db)

    def _decrypt_backup_to_temporary_file(
        self,
        source: Path,
        password: str | None,
    ) -> Path:
        if not password:
            raise ValueError("Enter the password for this encrypted backup")
        raw = source.read_bytes()
        header_size = len(self.ENCRYPTED_HEADER)
        if len(raw) <= header_size + self.SALT_SIZE:
            raise ValueError("This encrypted backup is damaged or incomplete")
        salt = raw[header_size : header_size + self.SALT_SIZE]
        token = raw[header_size + self.SALT_SIZE :]
        try:
            plaintext = Fernet(
                self._derive_key(password.encode("utf-8"), salt)
            ).decrypt(token)
        except InvalidToken as exc:
            raise ValueError(
                "Incorrect password or damaged encrypted backup"
            ) from exc

        temporary = backup_dir() / f".decrypt-source-{uuid4().hex}.db"
        try:
            temporary.write_bytes(plaintext)
        except Exception:
            self._remove_temporary_database(temporary)
            raise
        return temporary

    @classmethod
    def is_encrypted_backup(cls, source: Path) -> bool:
        source = Path(source)
        if not source.is_file():
            return False
        with source.open("rb") as stream:
            return stream.read(len(cls.ENCRYPTED_HEADER)) == cls.ENCRYPTED_HEADER

    @classmethod
    def _derive_key(cls, password: bytes, salt: bytes) -> bytes:
        key = Scrypt(
            salt=salt,
            length=32,
            n=cls.SCRYPT_N,
            r=cls.SCRYPT_R,
            p=cls.SCRYPT_P,
        ).derive(password)
        return base64.urlsafe_b64encode(key)

    @classmethod
    def _new_password(cls, password: str) -> bytes:
        if not isinstance(password, str) or not password:
            raise ValueError("Enter a password for the encrypted backup")
        if len(password) < cls.MINIMUM_PASSWORD_LENGTH:
            raise ValueError(
                f"Use at least {cls.MINIMUM_PASSWORD_LENGTH} characters for the backup password"
            )
        return password.encode("utf-8")

    @staticmethod
    def _remove_temporary_database(source: Path) -> None:
        for candidate in (
            source,
            Path(f"{source}-wal"),
            Path(f"{source}-shm"),
        ):
            candidate.unlink(missing_ok=True)

    @staticmethod
    def _open_source(source: Path):
        return open_local_database(source, read_only=True)

    @staticmethod
    def _database_errors() -> tuple[type[BaseException], ...]:
        from app.core.database_security import DB_ERROR_TYPES

        return DB_ERROR_TYPES

    @staticmethod
    def _rotate(prefix: str, retention: int) -> None:
        keep = max(1, int(retention))
        candidates = sorted(backup_dir().glob(f"{prefix}*.db"), reverse=True)
        for expired in candidates[keep:]:
            expired.unlink(missing_ok=True)
