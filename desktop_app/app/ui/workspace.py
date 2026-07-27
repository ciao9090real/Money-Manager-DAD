from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from app.models.navigation import WorkspaceRoute


@dataclass(frozen=True)
class WorkspaceSection:
    key: str
    label: str


class WorkspaceBar(QFrame):
    """Secondary navigation shown only while a workspace is open."""

    route_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("WorkspaceBar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(58)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(34, 9, 34, 8)
        layout.setSpacing(18)

        self.workspace_label = QLabel()
        self.workspace_label.setProperty("role", "workspaceLabel")
        self.workspace_label.setMinimumWidth(82)
        layout.addWidget(self.workspace_label)

        self.section_host = QWidget()
        self.section_layout = QHBoxLayout(self.section_host)
        self.section_layout.setContentsMargins(0, 0, 0, 0)
        self.section_layout.setSpacing(3)
        layout.addWidget(self.section_host, 1)

        self._workspace = ""
        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

    def configure(
        self,
        workspace: str,
        sections: tuple[WorkspaceSection, ...],
        active_section: str,
    ) -> None:
        if workspace != self._workspace or set(self._buttons) != {
            section.key for section in sections
        }:
            self._workspace = workspace
            self.workspace_label.setText(workspace.upper())
            self._rebuild_buttons(workspace, sections)
        self.set_active(active_section)

    def set_active(self, section: str) -> None:
        for key, button in self._buttons.items():
            selected = key == section
            button.setChecked(selected)
            button.setProperty("selected", "true" if selected else "false")
            button.style().unpolish(button)
            button.style().polish(button)

    def _rebuild_buttons(
        self,
        workspace: str,
        sections: tuple[WorkspaceSection, ...],
    ) -> None:
        while self.section_layout.count():
            item = self.section_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                self._group.removeButton(widget)
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._buttons = {}

        for section in sections:
            button = QPushButton(section.label)
            button.setProperty("variant", "workspaceTab")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, key=section.key: self.route_requested.emit(
                    WorkspaceRoute(workspace, key)
                )
            )
            self._group.addButton(button)
            self._buttons[section.key] = button
            self.section_layout.addWidget(button)
        self.section_layout.addStretch()
