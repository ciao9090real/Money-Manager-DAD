from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from app.services.auth_service import (
    AuthenticationError,
    AuthService,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    WindowsHelloError,
)
from app.ui.components import dialog_shell, primary_button, secondary_button
from app.ui.icons import icon
from app.ui.theme import Colors


def _password_field(placeholder: str) -> QLineEdit:
    field = QLineEdit()
    field.setEchoMode(QLineEdit.EchoMode.Password)
    field.setMaxLength(PASSWORD_MAX_LENGTH)
    field.setPlaceholderText(placeholder)
    return field


def _error_label() -> QLabel:
    label = QLabel()
    label.setProperty("role", "formError")
    label.setWordWrap(True)
    label.hide()
    return label


class PasswordSetupDialog(QDialog):
    def __init__(self, auth: AuthService, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.setWindowTitle("Protect Money Manager")
        self.setModal(True)

        form = QFormLayout()
        self.password = _password_field(
            f"At least {PASSWORD_MIN_LENGTH} characters"
        )
        self.confirmation = _password_field("Type the password again")
        form.addRow("App password", self.password)
        form.addRow("Confirm password", self.confirmation)

        status = auth.status()
        self.use_hello = QCheckBox("Also set up Windows Hello")
        self.use_hello.setChecked(status.windows_hello_available)
        self.use_hello.setEnabled(status.windows_hello_available)
        self.use_hello.setToolTip(
            "Use face, fingerprint, or the Windows device verification prompt."
            if status.windows_hello_available
            else "Set up Windows Hello in Windows Settings first."
        )
        form.addRow("Faster unlock", self.use_hello)
        self.error = _error_label()
        form.addRow("", self.error)

        dialog_shell(
            self,
            "Protect your financial data",
            "Create a recovery password. You can then use Windows Hello for everyday unlocks.",
            form,
            "Create password",
            "shield",
            minimum_width=560,
        )
        self.password.setFocus()

    def accept(self) -> None:
        self.error.hide()
        password = self.password.text()
        if password != self.confirmation.text():
            self._show_error("The two passwords do not match.")
            return
        try:
            self.auth.set_initial_password(password)
        except AuthenticationError as exc:
            self._show_error(str(exc))
            return

        if self.use_hello.isChecked():
            try:
                self.auth.enable_windows_hello(int(self.winId()))
            except WindowsHelloError as exc:
                QMessageBox.warning(
                    self,
                    "Password saved; Windows Hello not enabled",
                    f"{exc}\n\nYou can set it up later in Settings > App security.",
                )
        super().accept()

    def _show_error(self, message: str) -> None:
        self.error.setText(message)
        self.error.show()
        self.password.selectAll()
        self.password.setFocus()


class UnlockDialog(QDialog):
    MAX_FAILED_ATTEMPTS = 5
    COOLDOWN_SECONDS = 30

    def __init__(self, auth: AuthService, parent=None, *, auto_hello: bool = True):
        super().__init__(parent)
        self.auth = auth
        self.failed_attempts = 0
        self.cooldown_remaining = 0
        self.setWindowTitle("Unlock Money Manager")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 28, 30, 26)
        root.setSpacing(16)

        icon_tile = QFrame()
        icon_tile.setProperty("role", "dialogIcon")
        icon_tile.setFixedSize(54, 54)
        icon_layout = QHBoxLayout(icon_tile)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel()
        icon_label.setPixmap(icon("shield", Colors.PRIMARY, 27).pixmap(27, 27))
        icon_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)
        root.addWidget(icon_tile, 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("Money Manager is locked")
        title.setProperty("role", "dialogTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel(
            "Use Windows Hello or your app password. Your financial pages stay closed until you unlock."
        )
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)
        root.addWidget(subtitle)

        surface = QFrame()
        surface.setProperty("role", "formSurface")
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(18, 17, 18, 17)
        surface_layout.setSpacing(10)
        password_label = QLabel("App password")
        self.password = _password_field("Enter your app password")
        self.password.returnPressed.connect(self.try_password)
        self.error = _error_label()
        surface_layout.addWidget(password_label)
        surface_layout.addWidget(self.password)
        surface_layout.addWidget(self.error)
        root.addWidget(surface)

        self.unlock_button = primary_button("Unlock with password", "shield")
        self.unlock_button.clicked.connect(self.try_password)
        self.hello_button = secondary_button("Use Windows Hello", "devices")
        self.hello_button.clicked.connect(self.try_windows_hello)
        status = auth.status()
        hello_ready = status.windows_hello_enabled and status.windows_hello_available
        self.hello_button.setVisible(status.windows_hello_enabled)
        self.hello_button.setEnabled(hello_ready)
        if status.windows_hello_enabled and not status.windows_hello_available:
            self.hello_button.setToolTip(
                "Windows Hello is unavailable. Use the app password."
            )

        buttons = QHBoxLayout()
        buttons.setSpacing(9)
        buttons.addWidget(self.hello_button)
        buttons.addStretch()
        quit_button = secondary_button("Quit")
        quit_button.clicked.connect(self.reject)
        buttons.addWidget(quit_button)
        buttons.addWidget(self.unlock_button)
        root.addLayout(buttons)

        self.cooldown_timer = QTimer(self)
        self.cooldown_timer.setInterval(1000)
        self.cooldown_timer.timeout.connect(self._cooldown_tick)
        self.password.setFocus()
        if auto_hello and hello_ready:
            QTimer.singleShot(150, self.try_windows_hello)

    def try_password(self) -> None:
        if self.cooldown_remaining:
            return
        if self.auth.verify_password(self.password.text()):
            self.password.clear()
            self.accept()
            return
        self.password.clear()
        self.failed_attempts += 1
        remaining = self.MAX_FAILED_ATTEMPTS - self.failed_attempts
        if remaining <= 0:
            self.cooldown_remaining = self.COOLDOWN_SECONDS
            self.failed_attempts = 0
            self.password.setEnabled(False)
            self.unlock_button.setEnabled(False)
            self.cooldown_timer.start()
            self._show_error(
                f"Too many attempts. Try again in {self.cooldown_remaining} seconds."
            )
        else:
            suffix = "attempt" if remaining == 1 else "attempts"
            self._show_error(
                f"That password is incorrect. {remaining} {suffix} before a short pause."
            )
            self.password.setFocus()

    def try_windows_hello(self) -> None:
        if not self.hello_button.isEnabled():
            return
        self.hello_button.setEnabled(False)
        self.error.hide()
        try:
            if self.auth.verify_windows_hello(int(self.winId())):
                self.accept()
                return
        except WindowsHelloError as exc:
            self._show_error(str(exc))
        finally:
            if self.result() != QDialog.DialogCode.Accepted:
                self.hello_button.setEnabled(True)

    def _cooldown_tick(self) -> None:
        self.cooldown_remaining -= 1
        if self.cooldown_remaining <= 0:
            self.cooldown_timer.stop()
            self.password.setEnabled(True)
            self.unlock_button.setEnabled(True)
            self.error.hide()
            self.password.setFocus()
            return
        self._show_error(
            f"Too many attempts. Try again in {self.cooldown_remaining} seconds."
        )

    def _show_error(self, message: str) -> None:
        self.error.setText(message)
        self.error.show()


class ChangePasswordDialog(QDialog):
    def __init__(self, auth: AuthService, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.setWindowTitle("Change app password")
        form = QFormLayout()
        self.current_password = _password_field("Current app password")
        self.new_password = _password_field(
            f"At least {PASSWORD_MIN_LENGTH} characters"
        )
        self.confirmation = _password_field("Type the new password again")
        form.addRow("Current password", self.current_password)
        form.addRow("New password", self.new_password)
        form.addRow("Confirm password", self.confirmation)
        self.error = _error_label()
        form.addRow("", self.error)
        dialog_shell(
            self,
            "Change app password",
            "Windows Hello remains available after the password changes.",
            form,
            "Change password",
            "shield",
        )

    def accept(self) -> None:
        self.error.hide()
        if self.new_password.text() != self.confirmation.text():
            self._show_error("The two new passwords do not match.")
            return
        try:
            self.auth.change_password(
                self.current_password.text(),
                self.new_password.text(),
            )
        except AuthenticationError as exc:
            self._show_error(str(exc))
            return
        self.current_password.clear()
        self.new_password.clear()
        self.confirmation.clear()
        super().accept()

    def _show_error(self, message: str) -> None:
        self.error.setText(message)
        self.error.show()


class ConfirmPasswordDialog(QDialog):
    def __init__(self, auth: AuthService, action: str, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.setWindowTitle("Confirm app password")
        form = QFormLayout()
        self.password = _password_field("Enter your app password")
        form.addRow("App password", self.password)
        self.error = _error_label()
        form.addRow("", self.error)
        dialog_shell(
            self,
            "Confirm this security change",
            f"Enter your app password to {action}.",
            form,
            "Continue",
            "shield",
        )

    def accept(self) -> None:
        if not self.auth.verify_password(self.password.text()):
            self.password.clear()
            self.error.setText("The app password is incorrect.")
            self.error.show()
            return
        self.password.clear()
        super().accept()
