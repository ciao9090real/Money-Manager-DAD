from __future__ import annotations

import ctypes
import os
import secrets
import sqlite3
from ctypes import wintypes
from pathlib import Path
from uuid import uuid4

from app.core.paths import database_key_path, ensure_app_dirs

try:
    from sqlcipher3 import dbapi2 as sqlcipher
except ImportError:  # pragma: no cover - exercised only in an incomplete install
    sqlcipher = None


KEY_FILE_HEADER = b"MMDBKEY\x01"
KEY_SIZE = 32
DPAPI_ENTROPY = b"MoneyManagerDAD/database-key/v1"
SQLITE_HEADER = b"SQLite format 3\x00"

DB_ERROR_TYPES = (
    (sqlite3.Error, sqlcipher.Error) if sqlcipher is not None else (sqlite3.Error,)
)
DB_INTEGRITY_ERROR_TYPES = (
    (sqlite3.IntegrityError, sqlcipher.IntegrityError)
    if sqlcipher is not None
    else (sqlite3.IntegrityError,)
)


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def encryption_enabled(*, explicit_path: bool = False) -> bool:
    forced = os.environ.get("MONEY_MANAGER_DAD_ENCRYPT_DATABASE", "").strip().lower()
    if forced in {"1", "true", "yes"}:
        return True
    if forced in {"0", "false", "no"}:
        return False
    return (
        os.name == "nt"
        and not explicit_path
        and not os.environ.get("MONEY_MANAGER_DAD_DATA_DIR")
    )


def load_or_create_database_key(*, allow_create: bool = True) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Encrypted desktop storage currently requires Windows")
    ensure_app_dirs()
    target = database_key_path()
    if target.exists():
        raw = target.read_bytes()
        if not raw.startswith(KEY_FILE_HEADER):
            raise RuntimeError("The protected database key file is damaged")
        key = _dpapi_unprotect(raw[len(KEY_FILE_HEADER) :])
        if len(key) != KEY_SIZE:
            raise RuntimeError("The protected database key is invalid")
        return key

    if not allow_create:
        raise RuntimeError(
            "The Windows-protected database key is missing. Restore database.key from this Windows profile before opening the encrypted database."
        )

    key = secrets.token_bytes(KEY_SIZE)
    protected = KEY_FILE_HEADER + _dpapi_protect(key)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(protected)
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return key


def connect_encrypted(path: Path, *, timeout: int = 10):
    driver = _require_sqlcipher()
    encrypted_database_exists = (
        path.is_file()
        and path.stat().st_size > 0
        and not is_plain_sqlite_file(path)
    )
    key = load_or_create_database_key(allow_create=not encrypted_database_exists)
    _recover_interrupted_migration(path, key)
    if is_plain_sqlite_file(path):
        _migrate_plain_database(path, key)
    connection = driver.connect(path, timeout=timeout)
    apply_database_key(connection, key)
    connection.row_factory = driver.Row
    try:
        connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except driver.Error as exc:
        connection.close()
        raise RuntimeError(
            "The encrypted database could not be unlocked with this Windows account"
        ) from exc
    return connection


def apply_database_key(connection, key: bytes) -> None:
    connection.execute(f'PRAGMA key = "x\'{key.hex()}\'"')


def connection_is_encrypted(connection) -> bool:
    try:
        row = connection.execute("PRAGMA cipher_status").fetchone()
    except Exception:
        return False
    return bool(row and str(row[0]) == "1")


def open_local_database(source: Path, *, read_only: bool = False):
    """Open a plain legacy file or a database encrypted for this Windows user."""
    source = Path(source)
    if is_plain_sqlite_file(source):
        mode = "?mode=ro" if read_only else ""
        connection = sqlite3.connect(
            f"file:{source.as_posix()}{mode}",
            uri=bool(mode),
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    driver = _require_sqlcipher()
    mode = "?mode=ro" if read_only else ""
    connection = driver.connect(
        f"file:{source.as_posix()}{mode}",
        uri=bool(mode),
    )
    apply_database_key(connection, load_or_create_database_key(allow_create=False))
    connection.row_factory = driver.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
    return connection


def backup_connection(connection, target: Path, *, portable_plaintext: bool = False) -> None:
    target = Path(target)
    if not connection_is_encrypted(connection):
        destination = sqlite3.connect(target)
        try:
            connection.backup(destination)
        finally:
            destination.close()
        return

    driver = _require_sqlcipher()
    key = load_or_create_database_key(allow_create=False)
    if not portable_plaintext:
        destination = driver.connect(target)
        try:
            apply_database_key(destination, key)
            connection.backup(destination)
        finally:
            destination.close()
        return

    escaped = str(target.resolve()).replace("'", "''")
    connection.execute(f"ATTACH DATABASE '{escaped}' AS portable KEY ''")
    try:
        connection.execute("SELECT sqlcipher_export('portable')").fetchone()
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        connection.execute(f"PRAGMA portable.user_version = {version}")
    finally:
        connection.execute("DETACH DATABASE portable")


def restore_connection(candidate, destination) -> None:
    if connection_is_encrypted(destination) == connection_is_encrypted(candidate):
        candidate.backup(destination)
        return
    if not connection_is_encrypted(destination):
        raise RuntimeError("Cannot restore encrypted data into an unencrypted database")

    temporary = Path(destination.execute("PRAGMA database_list").fetchone()[2]).with_name(
        f".restore-source-{uuid4().hex}.db"
    )
    try:
        _encrypt_plain_connection(
            candidate,
            temporary,
            load_or_create_database_key(allow_create=False),
        )
        encrypted_candidate = open_local_database(temporary, read_only=True)
        try:
            encrypted_candidate.backup(destination)
        finally:
            encrypted_candidate.close()
    finally:
        remove_database_files(temporary)


def is_plain_sqlite_file(path: Path) -> bool:
    path = Path(path)
    if not path.is_file() or path.stat().st_size < len(SQLITE_HEADER):
        return False
    with path.open("rb") as stream:
        return stream.read(len(SQLITE_HEADER)) == SQLITE_HEADER


def remove_database_files(path: Path) -> None:
    for candidate in (
        Path(path),
        Path(f"{path}-wal"),
        Path(f"{path}-shm"),
        Path(f"{path}-journal"),
    ):
        candidate.unlink(missing_ok=True)


def remove_database_sidecars(path: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)


def _migrate_plain_database(path: Path, key: bytes) -> None:
    encrypted = path.with_name(f".{path.name}.encrypted-migration")
    rollback = path.with_name(f".{path.name}.plaintext-migration")
    remove_database_files(encrypted)
    remove_database_files(rollback)
    source = sqlite3.connect(path)
    try:
        source.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        _encrypt_plain_connection(source, encrypted, key)
    finally:
        source.close()

    verified = _require_sqlcipher().connect(encrypted)
    try:
        apply_database_key(verified, key)
        result = verified.execute("PRAGMA integrity_check").fetchone()
        if not result or str(result[0]).lower() != "ok":
            raise RuntimeError("Encrypted database migration failed its integrity check")
    finally:
        verified.close()

    remove_database_sidecars(path)
    path.replace(rollback)
    try:
        encrypted.replace(path)
        check = _require_sqlcipher().connect(path)
        try:
            apply_database_key(check, key)
            check.execute("SELECT count(*) FROM sqlite_master").fetchone()
        finally:
            check.close()
    except Exception:
        remove_database_files(path)
        rollback.replace(path)
        raise
    else:
        remove_database_files(rollback)


def _encrypt_plain_connection(source, target: Path, key: bytes) -> None:
    driver = _require_sqlcipher()
    # SQLCipher's export function must run from its own connection. A plain
    # temporary backup first provides a consistent snapshot for that export.
    plain_snapshot = target.with_name(f".{target.name}.plain-source")
    remove_database_files(plain_snapshot)
    snapshot = sqlite3.connect(plain_snapshot)
    try:
        source.backup(snapshot)
    finally:
        snapshot.close()
    sqlcipher_source = driver.connect(plain_snapshot)
    escaped = str(target.resolve()).replace("'", "''")
    try:
        sqlcipher_source.execute(
            f'ATTACH DATABASE \'{escaped}\' AS encrypted KEY "x\'{key.hex()}\'"'
        )
        sqlcipher_source.execute("SELECT sqlcipher_export('encrypted')").fetchone()
        version = int(sqlcipher_source.execute("PRAGMA user_version").fetchone()[0])
        sqlcipher_source.execute(f"PRAGMA encrypted.user_version = {version}")
        sqlcipher_source.execute("DETACH DATABASE encrypted")
    finally:
        sqlcipher_source.close()
        remove_database_files(plain_snapshot)


def _recover_interrupted_migration(path: Path, key: bytes) -> None:
    encrypted = path.with_name(f".{path.name}.encrypted-migration")
    rollback = path.with_name(f".{path.name}.plaintext-migration")
    if path.exists():
        if rollback.exists() and not is_plain_sqlite_file(path):
            candidate = _require_sqlcipher().connect(path)
            try:
                apply_database_key(candidate, key)
                result = candidate.execute("PRAGMA integrity_check").fetchone()
                valid = bool(result and str(result[0]).lower() == "ok")
            except Exception:
                valid = False
            finally:
                candidate.close()
            if valid:
                remove_database_files(rollback)
            else:
                remove_database_files(path)
                rollback.replace(path)
        return
    if encrypted.exists():
        candidate = _require_sqlcipher().connect(encrypted)
        try:
            apply_database_key(candidate, key)
            result = candidate.execute("PRAGMA integrity_check").fetchone()
            valid = bool(result and str(result[0]).lower() == "ok")
        except Exception:
            valid = False
        finally:
            candidate.close()
        if valid:
            encrypted.replace(path)
            remove_database_files(rollback)
            return
        remove_database_files(encrypted)
    if rollback.exists():
        rollback.replace(path)


def _require_sqlcipher():
    if sqlcipher is None:
        raise RuntimeError(
            "SQLCipher is not installed. Reinstall Money Manager or its locked dependencies."
        )
    return sqlcipher


def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    blob = _DataBlob(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buffer


def _dpapi_protect(data: bytes) -> bytes:
    source, source_buffer = _blob(data)
    entropy, entropy_buffer = _blob(DPAPI_ENTROPY)
    output = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    if not crypt32.CryptProtectData(
        ctypes.byref(source),
        "Money Manager database key",
        ctypes.byref(entropy),
        None,
        None,
        0x1,
        ctypes.byref(output),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)
        del source_buffer, entropy_buffer


def _dpapi_unprotect(data: bytes) -> bytes:
    source, source_buffer = _blob(data)
    entropy, entropy_buffer = _blob(DPAPI_ENTROPY)
    output = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source),
        None,
        ctypes.byref(entropy),
        None,
        None,
        0x1,
        ctypes.byref(output),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)
        del source_buffer, entropy_buffer
