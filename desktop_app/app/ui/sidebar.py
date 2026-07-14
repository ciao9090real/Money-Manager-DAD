from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from app.ui.icons import LineIcon


class SidebarNavItem(QFrame):
    clicked = Signal()

    def __init__(self, key: str, label: str, icon: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.key = key
        self.label = label
        self.icon = icon
        self.setProperty("role", "navItem")
        self.setProperty("selected", "false")
        self.setProperty("collapsed", "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(label)
        self.setFixedHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(12, 0, 12, 0)
        self.layout.setSpacing(10)

        self.icon_widget = LineIcon(icon, "#94a3b8", 20)
        self.icon_container = QWidget()
        icon_layout = QHBoxLayout(self.icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(self.icon_widget)
        self.icon_container.setFixedWidth(28)

        self.text_label = QLabel(label)
        self.text_label.setProperty("role", "navLabel")

        self.layout.addWidget(self.icon_container)
        self.layout.addWidget(self.text_label, 1)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_collapsed(self, collapsed: bool) -> None:
        self.text_label.setVisible(not collapsed)
        self.setProperty("collapsed", "true" if collapsed else "false")
        self.layout.setContentsMargins(0 if collapsed else 12, 0, 0 if collapsed else 12, 0)
        self.layout.setSpacing(0 if collapsed else 10)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter if collapsed else Qt.AlignmentFlag.AlignLeft)
        self.icon_container.setFixedWidth(44 if collapsed else 28)
        self._refresh_style()

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        self.icon_widget.set_color("#ffffff" if selected else "#94a3b8")
        self._refresh_style()

    def _refresh_style(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)
        for child in (self.icon_container, self.text_label):
            child.style().unpolish(child)
            child.style().polish(child)


class Sidebar(QFrame):
    page_selected = Signal(int)

    EXPANDED_WIDTH = 252
    COLLAPSED_WIDTH = 76

    def __init__(self, pages: list[tuple[str, str]], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.pages = pages
        self.collapsed = False
        self.nav_buttons: list[SidebarNavItem] = []
        self.setFixedWidth(self.EXPANDED_WIDTH)

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(14, 18, 14, 16)
        self.root_layout.setSpacing(8)

        self._build_header()
        self.root_layout.addSpacing(16)
        self._build_nav()
        self._build_footer()
        self.set_selected(0)

    def _build_header(self) -> None:
        self.header = QWidget()
        layout = QHBoxLayout(self.header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.mark = QFrame()
        self.mark.setObjectName("LogoTile")
        self.mark.setFixedSize(42, 42)
        mark_layout = QHBoxLayout(self.mark)
        mark_layout.setContentsMargins(10, 10, 10, 10)
        mark_layout.addWidget(LineIcon("accounts", "#ffffff", 22))

        self.title_block = QWidget()
        title_layout = QVBoxLayout(self.title_block)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(1)
        self.title = QLabel("Money Manager")
        self.title.setObjectName("SidebarTitle")
        self.subtitle = QLabel("Private finance hub")
        self.subtitle.setObjectName("SidebarSubtitle")
        title_layout.addWidget(self.title)
        title_layout.addWidget(self.subtitle)

        layout.addWidget(self.mark, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.title_block, 1)
        self.root_layout.addWidget(self.header)

    def _build_nav(self) -> None:
        for index, (label, icon) in enumerate(self.pages):
            if label == "Settings":
                self.root_layout.addStretch()
            key = label.lower().replace(" ", "_")
            button = SidebarNavItem(key, label, icon)
            button.clicked.connect(lambda row=index: self.page_selected.emit(row))
            self.nav_buttons.append(button)
            self.root_layout.addWidget(button)

    def _build_footer(self) -> None:
        self.root_layout.addSpacing(10)
        self.status = QFrame()
        self.status.setObjectName("SidebarStatus")
        status_layout = QHBoxLayout(self.status)
        status_layout.setContentsMargins(12, 10, 12, 10)
        status_layout.setSpacing(9)
        dot = QFrame()
        dot.setObjectName("StatusDot")
        dot.setFixedSize(8, 8)
        labels = QVBoxLayout()
        labels.setContentsMargins(0, 0, 0, 0)
        labels.setSpacing(1)
        local = QLabel("Local & private")
        local.setStyleSheet("color: white; font-weight: 600; font-size: 12px;")
        offline = QLabel("Your data stays here")
        offline.setProperty("role", "sidebarMeta")
        labels.addWidget(local)
        labels.addWidget(offline)
        status_layout.addWidget(dot)
        status_layout.addLayout(labels, 1)
        self.root_layout.addWidget(self.status)

        collapse_row = QWidget()
        collapse_layout = QHBoxLayout(collapse_row)
        collapse_layout.setContentsMargins(0, 2, 0, 0)
        collapse_layout.addStretch()
        self.collapse_button = QPushButton("\u2039")
        self.collapse_button.setProperty("variant", "sidebarIcon")
        self.collapse_button.setFixedSize(34, 34)
        self.collapse_button.setToolTip("Collapse sidebar")
        self.collapse_button.clicked.connect(self.toggle)
        collapse_layout.addWidget(self.collapse_button)
        self.root_layout.addWidget(collapse_row)

    def toggle(self) -> None:
        self.collapsed = not self.collapsed
        self.setFixedWidth(self.COLLAPSED_WIDTH if self.collapsed else self.EXPANDED_WIDTH)
        self.title_block.setVisible(not self.collapsed)
        self.status.setVisible(not self.collapsed)
        self.collapse_button.setText("\u203a" if self.collapsed else "\u2039")
        self.collapse_button.setToolTip("Expand sidebar" if self.collapsed else "Collapse sidebar")
        for button in self.nav_buttons:
            button.set_collapsed(self.collapsed)

    def set_selected(self, index: int) -> None:
        for row, button in enumerate(self.nav_buttons):
            button.set_selected(row == index)
