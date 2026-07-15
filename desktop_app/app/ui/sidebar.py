from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from app.ui.icons import LineIcon, icon


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

        self.icon_widget = LineIcon(icon, "#91a59f", 19)
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
        self.icon_widget.set_color("#a7ead5" if selected else "#91a59f")
        self._refresh_style()

    def _refresh_style(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)
        for child in (self.icon_container, self.text_label):
            child.style().unpolish(child)
            child.style().polish(child)


class Sidebar(QFrame):
    page_selected = Signal(int)
    state_changed = Signal(bool, bool)

    EXPANDED_WIDTH = 236
    COLLAPSED_WIDTH = 72

    def __init__(self, pages: list[tuple[str, str]], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.pages = pages
        self.collapsed = False
        self.nav_buttons: list[SidebarNavItem] = []
        self.setFixedWidth(self.EXPANDED_WIDTH)
        self.width_animation = QPropertyAnimation(self, b"sidebar_width", self)
        self.width_animation.setDuration(170)
        self.width_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.width_animation.finished.connect(self._finish_width_animation)

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(12, 16, 12, 14)
        self.root_layout.setSpacing(7)

        self._build_header()
        self.root_layout.addSpacing(18)
        self._build_nav()
        self._build_footer()
        self.set_selected(0)

    def _build_header(self) -> None:
        self.header = QWidget()
        header_layout = QVBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        self.brand_row = QWidget()
        layout = QHBoxLayout(self.brand_row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.mark = QPushButton()
        self.mark.setObjectName("LogoButton")
        self.mark.setFixedSize(40, 40)
        self.mark.setText("€")
        self.mark.setProperty("role", "brandMark")
        self.mark.setToolTip("Money Manager")

        self.title_block = QWidget()
        title_layout = QVBoxLayout(self.title_block)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(1)
        self.title = QLabel("Money Manager")
        self.title.setObjectName("SidebarTitle")
        self.subtitle = QLabel("LOCAL FINANCE")
        self.subtitle.setObjectName("SidebarSubtitle")
        title_layout.addWidget(self.title)
        title_layout.addWidget(self.subtitle)

        layout.addWidget(self.mark, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.title_block, 1)

        self.collapse_button = QPushButton()
        self.collapse_button.setProperty("variant", "sidebarIcon")
        self.collapse_button.setFixedSize(30, 30)
        self.collapse_button.setIcon(icon("chevron_left", "#cbd5e1", 16))
        self.collapse_button.setToolTip("Collapse sidebar (Ctrl+B)")
        self.collapse_button.clicked.connect(self.toggle)
        layout.addWidget(self.collapse_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.expand_button = QPushButton()
        self.expand_button.setProperty("variant", "sidebarIcon")
        self.expand_button.setFixedSize(30, 30)
        self.expand_button.setIcon(icon("chevron_right", "#cbd5e1", 16))
        self.expand_button.setToolTip("Expand sidebar (Ctrl+B)")
        self.expand_button.clicked.connect(self.toggle)
        self.expand_button.setVisible(False)
        header_layout.addWidget(self.brand_row)
        header_layout.addWidget(
            self.expand_button,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )
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
        local = QLabel("Stored locally")
        local.setStyleSheet("color: white; font-weight: 600; font-size: 12px;")
        offline = QLabel("Private on this device")
        offline.setProperty("role", "sidebarMeta")
        labels.addWidget(local)
        labels.addWidget(offline)
        status_layout.addWidget(dot)
        status_layout.addLayout(labels, 1)
        self.root_layout.addWidget(self.status)

    def toggle(self) -> None:
        self.set_collapsed(not self.collapsed, animate=True, user_initiated=True)

    def set_collapsed(
        self,
        collapsed: bool,
        *,
        animate: bool = True,
        user_initiated: bool = False,
    ) -> None:
        collapsed = bool(collapsed)
        target_width = self.COLLAPSED_WIDTH if collapsed else self.EXPANDED_WIDTH
        if collapsed == self.collapsed and self.width() == target_width:
            return

        self.collapsed = collapsed
        self.title_block.setVisible(not collapsed)
        self.status.setVisible(not collapsed)
        self.collapse_button.setVisible(not collapsed)
        self.expand_button.setVisible(collapsed)
        self.mark.setText("€")
        self.mark.setToolTip("Money Manager")
        for button in self.nav_buttons:
            button.set_collapsed(collapsed)

        self.width_animation.stop()
        if animate and self.isVisible():
            self.width_animation.setStartValue(self.width())
            self.width_animation.setEndValue(target_width)
            self.width_animation.start()
        else:
            self.sidebar_width = target_width
        self.state_changed.emit(collapsed, user_initiated)

    def _get_sidebar_width(self) -> int:
        return self.width()

    def _set_sidebar_width(self, width: int) -> None:
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)

    def _finish_width_animation(self) -> None:
        self.sidebar_width = self.COLLAPSED_WIDTH if self.collapsed else self.EXPANDED_WIDTH

    sidebar_width = Property(int, _get_sidebar_width, _set_sidebar_width)

    def set_selected(self, index: int) -> None:
        for row, button in enumerate(self.nav_buttons):
            button.set_selected(row == index)
