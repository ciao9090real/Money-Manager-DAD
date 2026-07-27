from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QLineEdit,
)

from app.core.database import connect
from app.services.auth_service import (
    AuthenticationError,
    AuthService,
    WindowsHelloProvider,
)
from app.ui.backup_password_dialog import BackupPasswordDialog
from app.ui.auth_dialogs import (
    ChangePasswordDialog,
    ConfirmPasswordDialog,
    PasswordSetupDialog,
    UnlockDialog,
)


class FakeHelloProvider:
    def __init__(self, *, available: bool = True):
        self.available = available
        self.enrolled_user_id = None
        self.enrolled_user_ids = []
        self.enrolled_handle = None
        self.verified_handle = None
        self.credential = b"fake-windows-hello-credential"

    def is_available(self) -> bool:
        return self.available

    def enroll(self, user_id: bytes, window_handle: int) -> bytes:
        self.enrolled_user_id = user_id
        self.enrolled_user_ids.append(user_id)
        self.enrolled_handle = window_handle
        return self.credential

    def verify(self, credential: bytes, window_handle: int) -> bool:
        self.verified_handle = window_handle
        return credential == self.credential


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def auth(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    db = connect(tmp_path / "auth.db")
    provider = FakeHelloProvider()
    service = AuthService(db, hello_provider=provider, scrypt_n=2**10)
    try:
        yield service, provider, db
    finally:
        db.close()


def test_password_is_salted_verified_and_changeable(auth):
    service, _provider, db = auth
    assert not service.is_configured()

    service.set_initial_password("correct horse battery staple")

    stored = db.execute(
        "SELECT password_salt, password_verifier FROM app_auth WHERE id = 1"
    ).fetchone()
    assert bytes(stored["password_salt"])
    assert bytes(stored["password_verifier"]) != b"correct horse battery staple"
    assert service.verify_password("correct horse battery staple")
    assert not service.verify_password("wrong password")

    service.change_password(
        "correct horse battery staple",
        "new password for money manager",
    )

    assert not service.verify_password("correct horse battery staple")
    assert service.verify_password("new password for money manager")


def test_password_rules_and_current_password_are_enforced(auth):
    service, _provider, _db = auth
    with pytest.raises(AuthenticationError, match="at least"):
        service.set_initial_password("short")

    service.set_initial_password("long enough password")
    with pytest.raises(AuthenticationError, match="incorrect"):
        service.change_password("not the password", "replacement password")


def test_windows_hello_credential_can_be_enabled_verified_and_removed(auth):
    service, provider, db = auth
    service.set_initial_password("long enough password")

    service.enable_windows_hello(1234)

    assert service.status().windows_hello_enabled
    assert provider.enrolled_handle == 1234
    assert len(provider.enrolled_user_id) == 32
    assert service.verify_windows_hello(5678)
    assert provider.verified_handle == 5678
    stored = db.execute(
        "SELECT hello_credential FROM app_auth WHERE id = 1"
    ).fetchone()
    assert bytes(stored["hello_credential"]) == provider.credential

    service.enable_windows_hello(9876)

    assert provider.enrolled_user_ids[0] == provider.enrolled_user_ids[1]
    assert provider.enrolled_handle == 9876

    service.disable_windows_hello()

    assert not service.status().windows_hello_enabled


def test_first_run_dialog_creates_password(qt_app, auth):
    service, provider, _db = auth
    provider.available = False
    dialog = PasswordSetupDialog(service)
    dialog.password.setText("dialog password")
    dialog.confirmation.setText("dialog password")

    dialog.accept()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert service.verify_password("dialog password")
    dialog.deleteLater()
    qt_app.processEvents()


def test_unlock_dialog_accepts_password_and_throttles_repeated_failures(
    qt_app, auth
):
    service, _provider, _db = auth
    service.set_initial_password("dialog password")
    dialog = UnlockDialog(service, auto_hello=False)

    for _attempt in range(dialog.MAX_FAILED_ATTEMPTS):
        dialog.password.setText("wrong password")
        dialog.try_password()

    assert dialog.cooldown_remaining == dialog.COOLDOWN_SECONDS
    assert not dialog.password.isEnabled()
    dialog.cooldown_timer.stop()
    dialog.cooldown_remaining = 0
    dialog.password.setEnabled(True)
    dialog.unlock_button.setEnabled(True)
    dialog.password.setText("dialog password")
    dialog.try_password()

    assert dialog.result() == QDialog.DialogCode.Accepted
    dialog.deleteLater()
    qt_app.processEvents()


def test_show_password_controls_reveal_and_hide_every_auth_field(qt_app, auth):
    service, _provider, _db = auth
    dialogs_and_fields = [
        (
            PasswordSetupDialog(service),
            lambda dialog: (dialog.password, dialog.confirmation),
        ),
        (
            UnlockDialog(service, auto_hello=False),
            lambda dialog: (dialog.password,),
        ),
        (
            ChangePasswordDialog(service),
            lambda dialog: (
                dialog.current_password,
                dialog.new_password,
                dialog.confirmation,
            ),
        ),
        (
            ConfirmPasswordDialog(service, "continue"),
            lambda dialog: (dialog.password,),
        ),
    ]
    for dialog, fields_for in dialogs_and_fields:
        fields = fields_for(dialog)
        assert all(
            field.echoMode() == QLineEdit.EchoMode.Password
            for field in fields
        )
        for field in fields:
            field.setText("secret")
            mask = field.input.privacy_mask()
            assert len(mask) == len("secret")
            assert set(mask) <= set(field.input.MASK_ALPHABET)
            assert any(token.isdigit() for token in mask)
            assert any(token.isalpha() for token in mask)
            assert any(token in ".·•" for token in mask)
            assert field.text() == "secret"
            assert field.toggle_button.accessibleName() == "Show password"
            field.toggle_button.setChecked(True)
            assert field.echoMode() == QLineEdit.EchoMode.Normal
            assert field.toggle_button.accessibleName() == "Hide password"
            field.toggle_button.setChecked(False)
            assert field.echoMode() == QLineEdit.EchoMode.Password
        dialog.deleteLater()
    qt_app.processEvents()


def test_backup_password_uses_individual_eye_buttons(qt_app):
    dialog = BackupPasswordDialog(confirm_password=True)

    assert not any(
        checkbox.text() == "Show password"
        for checkbox in dialog.findChildren(QCheckBox)
    )
    assert dialog.password_input.mascot is not None
    for field in (dialog.password_input, dialog.confirm_input):
        field.toggle_button.setChecked(True)
        assert field.echoMode() == QLineEdit.EchoMode.Normal
        field.toggle_button.setChecked(False)
        assert field.echoMode() == QLineEdit.EchoMode.Password

    dialog.deleteLater()
    qt_app.processEvents()


def test_windows_hello_cancellation_has_a_clear_non_destructive_message():
    cause = OSError("The user canceled")
    cause.winerror = 1223

    message = str(
        WindowsHelloProvider._friendly_error("setup", cause)
    )

    assert "canceled" in message
    assert "Nothing changed" in message
