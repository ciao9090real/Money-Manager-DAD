from __future__ import annotations

import hmac
import os
import secrets
import sqlite3
from dataclasses import dataclass
from typing import Protocol

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from app.core.database import unit_of_work


PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 256
PASSWORD_SALT_SIZE = 16
PASSWORD_VERIFIER_SIZE = 32
DEFAULT_SCRYPT_N = 2**15
RP_ID = "money-manager.local"
ORIGIN = f"https://{RP_ID}"


class AuthenticationError(RuntimeError):
    pass


class WindowsHelloError(AuthenticationError):
    pass


class HelloProvider(Protocol):
    def is_available(self) -> bool: ...

    def enroll(self, user_id: bytes, window_handle: int) -> bytes: ...

    def verify(self, credential: bytes, window_handle: int) -> bool: ...


class WindowsHelloProvider:
    """Register and verify a local Windows WebAuthn platform credential."""

    def is_available(self) -> bool:
        if os.name != "nt":
            return False
        try:
            from fido2.client.windows import WindowsClient

            return bool(WindowsClient.is_available())
        except Exception:
            return False

    def enroll(self, user_id: bytes, window_handle: int) -> bytes:
        if not self.is_available():
            raise WindowsHelloError(
                "Windows Hello is unavailable. Set up Windows Hello in Windows Settings first."
            )
        try:
            from fido2.client import DefaultClientDataCollector
            from fido2.client.windows import WindowsClient
            from fido2.server import Fido2Server
            from fido2.webauthn import (
                AuthenticatorAttachment,
                PublicKeyCredentialRpEntity,
                PublicKeyCredentialUserEntity,
                ResidentKeyRequirement,
                UserVerificationRequirement,
            )

            server = Fido2Server(
                PublicKeyCredentialRpEntity(id=RP_ID, name="Money Manager"),
                verify_origin=lambda origin: origin == ORIGIN,
            )
            client = WindowsClient(
                DefaultClientDataCollector(ORIGIN),
                handle=window_handle,
            )
            options, state = server.register_begin(
                PublicKeyCredentialUserEntity(
                    id=user_id,
                    name="Money Manager user",
                    display_name="Money Manager user",
                ),
                resident_key_requirement=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.REQUIRED,
                authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            )
            response = client.make_credential(options.public_key)
            auth_data = server.register_complete(state, response)
            credential = auth_data.credential_data
            if credential is None:
                raise WindowsHelloError(
                    "Windows Hello did not create a usable credential."
                )
            return bytes(credential)
        except WindowsHelloError:
            raise
        except Exception as exc:
            raise WindowsHelloError(
                "Windows Hello setup was canceled or could not be completed."
            ) from exc

    def verify(self, credential: bytes, window_handle: int) -> bool:
        if not self.is_available():
            raise WindowsHelloError(
                "Windows Hello is unavailable. Use your app password instead."
            )
        try:
            from fido2.client import DefaultClientDataCollector
            from fido2.client.windows import WindowsClient
            from fido2.server import Fido2Server
            from fido2.webauthn import (
                AttestedCredentialData,
                PublicKeyCredentialRpEntity,
                UserVerificationRequirement,
            )

            stored_credential = AttestedCredentialData(credential)
            server = Fido2Server(
                PublicKeyCredentialRpEntity(id=RP_ID, name="Money Manager"),
                verify_origin=lambda origin: origin == ORIGIN,
            )
            client = WindowsClient(
                DefaultClientDataCollector(ORIGIN),
                handle=window_handle,
            )
            options, state = server.authenticate_begin(
                [stored_credential],
                user_verification=UserVerificationRequirement.REQUIRED,
            )
            selection = client.get_assertion(options.public_key)
            response = selection.get_response(0)
            server.authenticate_complete(state, [stored_credential], response)
            return True
        except Exception as exc:
            raise WindowsHelloError(
                "Windows Hello did not verify you. Try again or use your app password."
            ) from exc


@dataclass(frozen=True)
class AuthenticationStatus:
    configured: bool
    windows_hello_enabled: bool
    windows_hello_available: bool


class AuthService:
    def __init__(
        self,
        db: sqlite3.Connection,
        *,
        hello_provider: HelloProvider | None = None,
        scrypt_n: int = DEFAULT_SCRYPT_N,
    ):
        self.db = db
        self.hello_provider = hello_provider or WindowsHelloProvider()
        self.scrypt_n = scrypt_n

    def status(self) -> AuthenticationStatus:
        row = self._row()
        return AuthenticationStatus(
            configured=row is not None,
            windows_hello_enabled=bool(row and row["hello_credential"]),
            windows_hello_available=self.hello_provider.is_available(),
        )

    def is_configured(self) -> bool:
        return self._row() is not None

    def set_initial_password(self, password: str) -> None:
        if self.is_configured():
            raise AuthenticationError("An app password is already configured.")
        self._validate_new_password(password)
        salt = secrets.token_bytes(PASSWORD_SALT_SIZE)
        verifier = self._derive(password, salt)
        with unit_of_work(self.db):
            self.db.execute(
                """
                INSERT INTO app_auth (id, password_salt, password_verifier)
                VALUES (1, ?, ?)
                """,
                (salt, verifier),
            )

    def verify_password(self, password: str) -> bool:
        row = self._row()
        if row is None or len(password) > PASSWORD_MAX_LENGTH:
            return False
        candidate = self._derive(password, bytes(row["password_salt"]))
        return hmac.compare_digest(candidate, bytes(row["password_verifier"]))

    def change_password(self, current_password: str, new_password: str) -> None:
        if not self.verify_password(current_password):
            raise AuthenticationError("The current app password is incorrect.")
        self._validate_new_password(new_password)
        salt = secrets.token_bytes(PASSWORD_SALT_SIZE)
        verifier = self._derive(new_password, salt)
        with unit_of_work(self.db):
            self.db.execute(
                """
                UPDATE app_auth
                SET password_salt = ?, password_verifier = ?,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = 1
                """,
                (salt, verifier),
            )

    def enable_windows_hello(self, window_handle: int) -> None:
        if not self.is_configured():
            raise AuthenticationError("Create an app password before Windows Hello.")
        user_id = secrets.token_bytes(32)
        credential = self.hello_provider.enroll(user_id, window_handle)
        if not credential:
            raise WindowsHelloError(
                "Windows Hello did not return a usable credential."
            )
        with unit_of_work(self.db):
            self.db.execute(
                """
                UPDATE app_auth
                SET hello_user_id = ?, hello_credential = ?,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = 1
                """,
                (user_id, credential),
            )

    def disable_windows_hello(self) -> None:
        with unit_of_work(self.db):
            self.db.execute(
                """
                UPDATE app_auth
                SET hello_user_id = NULL, hello_credential = NULL,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = 1
                """
            )

    def verify_windows_hello(self, window_handle: int) -> bool:
        row = self._row()
        if row is None or not row["hello_credential"]:
            raise WindowsHelloError(
                "Windows Hello is not set up for Money Manager. Use your app password."
            )
        return self.hello_provider.verify(
            bytes(row["hello_credential"]),
            window_handle,
        )

    def _row(self):
        return self.db.execute(
            """
            SELECT password_salt, password_verifier,
                   hello_user_id, hello_credential
            FROM app_auth WHERE id = 1
            """
        ).fetchone()

    def _derive(self, password: str, salt: bytes) -> bytes:
        return Scrypt(
            salt=salt,
            length=PASSWORD_VERIFIER_SIZE,
            n=self.scrypt_n,
            r=8,
            p=1,
        ).derive(password.encode("utf-8"))

    @staticmethod
    def _validate_new_password(password: str) -> None:
        if len(password) < PASSWORD_MIN_LENGTH:
            raise AuthenticationError(
                f"Use at least {PASSWORD_MIN_LENGTH} characters for the app password."
            )
        if len(password) > PASSWORD_MAX_LENGTH:
            raise AuthenticationError(
                f"Use no more than {PASSWORD_MAX_LENGTH} characters for the app password."
            )
