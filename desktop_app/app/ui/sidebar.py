from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


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
        self.setFixedHeight(46)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(12, 0, 12, 0)
        self.layout.setSpacing(10)

        self.icon_label = QLabel(icon)
        self.icon_label.setProperty("role", "navIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedWidth(28)

        self.text_label = QLabel(label)
        self.text_label.setProperty("role", "navLabel")

        self.layout.addWidget(self.icon_label)
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
        self.icon_label.setFixedWidth(44 if collapsed else 28)
        self._refresh_style()

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        self._refresh_style()

    def _refresh_style(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)
        for child in (self.icon_label, self.text_label):
            child.style().unpolish(child)
            child.style().polish(child)


class Sidebar(QFrame):
    page_selected = Signal(int)

    EXPANDED_WIDTH = 240
    COLLAPSED_WIDTH = 76

    def __init__(self, pages: list[tuple[str, str]], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.pages = pages
        self.collapsed = False
        self.nav_buttons: list[SidebarNavItem] = []
        self.setFixedWidth(self.EXPANDED_WIDTH)

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(16, 18, 16, 18)
        self.root_layout.setSpacing(8)

        self._build_header()
        self._build_collapse_button()
        self.root_layout.addSpacing(8)
        self._build_nav()
        self.set_selected(0)

    def _build_header(self) -> None:
        self.header = QWidget()
        layout = QHBoxLayout(self.header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.mark = QLabel("\u20ac")
        self.mark.setObjectName("SidebarMark")
        self.mark.setFixedSize(38, 38)
        self.mark.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_block = QWidget()
        title_layout = QVBoxLayout(self.title_block)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(1)
        self.title = QLabel("Money Manager")
        self.title.setObjectName("SidebarTitle")
        self.subtitle = QLabel("Local finance tracker")
        self.subtitle.setObjectName("SidebarSubtitle")
        title_layout.addWidget(self.title)
        title_layout.addWidget(self.subtitle)

        layout.addWidget(self.mark, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.title_block, 1)
        self.root_layout.addWidget(self.header)

    def _build_collapse_button(self) -> None:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch()
        self.collapse_button = QPushButton("\u2039")
        self.collapse_button.setProperty("variant", "sidebarIcon")
        self.collapse_button.setFixedSize(34, 34)
        self.collapse_button.setToolTip("Collapse sidebar")
        self.collapse_button.clicked.connect(self.toggle)
        layout.addWidget(self.collapse_button)
        self.root_layout.addWidget(row)

    def _build_nav(self) -> None:
        for index, (label, icon) in enumerate(self.pages):
            if label == "Settings":
                self.root_layout.addStretch()
            key = label.lower().replace(" ", "_")
            button = SidebarNavItem(key, label, icon)
            button.clicked.connect(lambda row=index: self.page_selected.emit(row))
            self.nav_buttons.append(button)
            self.root_layout.addWidget(button)

    def toggle(self) -> None:
        self.collapsed = not self.collapsed
        self.setFixedWidth(self.COLLAPSED_WIDTH if self.collapsed else self.EXPANDED_WIDTH)
        self.title_block.setVisible(not self.collapsed)
        self.collapse_button.setText("\u203a" if self.collapsed else "\u2039")
        self.collapse_button.setToolTip("Expand sidebar" if self.collapsed else "Collapse sidebar")
        for button in self.nav_buttons:
            button.set_collapsed(self.collapsed)

    def set_selected(self, index: int) -> None:
        for row, button in enumerate(self.nav_buttons):
            button.set_selected(row == index)
