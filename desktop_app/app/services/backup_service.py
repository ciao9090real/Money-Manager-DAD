from __future__ import annotations

import base64
import os
import sqlite3
from datetime import date
from pathlib import Path
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from app.core.paths import backup_dir, database_path, ensure_app_dirs
from app.core.migrations import SCHEMA_VERSION, assert_database_integrity, migrate
from app.utils.dates import timestamp_for_filename


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
        destination = sqlite3.connect(target)
        try:
            self.db.backup(destination)
            destination.execute("PRAGMA foreign_keys = ON")
            assert_database_integrity(destination)
        except Exception:
            destination.close()
            target.unlink(missing_ok=True)
            raise
        else:
            destination.close()

    def _verified_backup_bytes(self) -> bytes:
        temporary = backup_dir() / f".encrypt-source-{uuid4().hex}.db"
        try:
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
        candidate.backup(self.db)
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
    def _open_source(source: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _rotate(prefix: str, retention: int) -> None:
        keep = max(1, int(retention))
        candidates = sorted(backup_dir().glob(f"{prefix}*.db"), reverse=True)
        for expired in candidates[keep:]:
            expired.unlink(missing_ok=True)
