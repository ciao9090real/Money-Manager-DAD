from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
)

from app.services.backup_service import BackupService
from app.ui.components import dialog_shell


class BackupPasswordDialog(QDialog):
    def __init__(self, *, confirm_password: bool, parent=None):
        super().__init__(parent)
        self.confirm_password = confirm_password
        self.setWindowTitle(
            "Encrypted backup" if confirm_password else "Unlock backup"
        )

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Backup password")
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.setPlaceholderText("Repeat password")
        self.show_password = QCheckBox("Show password")
        self.show_password.toggled.connect(self._set_password_visible)

        form = QFormLayout()
        form.addRow("Password", self.password_input)
        if confirm_password:
            form.addRow("Confirm", self.confirm_input)
        form.addRow("", self.show_password)

        if confirm_password:
            title = "Protect this backup"
            subtitle = (
                f"Use at least {BackupService.MINIMUM_PASSWORD_LENGTH} characters. "
                "The password cannot be recovered if it is lost."
            )
            primary_text = "Create encrypted backup"
        else:
            title = "Unlock encrypted backup"
            subtitle = "Enter the password used when this backup was created."
            primary_text = "Unlock and restore"
        dialog_shell(
            self,
            title,
            subtitle,
            form,
            primary_text,
            "shield",
            minimum_width=500,
        )

    def accept(self) -> None:
        password = self.password_input.text()
        if not password:
            QMessageBox.warning(self, "Password required", "Enter the backup password.")
            return
        if self.confirm_password:
            if len(password) < BackupService.MINIMUM_PASSWORD_LENGTH:
                QMessageBox.warning(
                    self,
                    "Password too short",
                    f"Use at least {BackupService.MINIMUM_PASSWORD_LENGTH} characters.",
                )
                return
            if password != self.confirm_input.text():
                QMessageBox.warning(
                    self,
                    "Passwords do not match",
                    "Enter the same password in both fields.",
                )
                return
        super().accept()

    def password(self) -> str:
        return self.password_input.text()

    def _set_password_visible(self, visible: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.password_input.setEchoMode(mode)
        self.confirm_input.setEchoMode(mode)
