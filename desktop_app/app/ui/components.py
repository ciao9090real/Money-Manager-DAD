from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableView,
    QTableWidgetItem,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import Colors, Spacing
from app.ui.icons import icon
from app.utils.money import format_money, to_decimal


def page_header(title: str, subtitle: str, action: QWidget | None = None) -> QWidget:
    container = QWidget()
    outer = QHBoxLayout(container)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(Spacing.GAP)
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)
    title_label = QLabel(title)
    title_label.setProperty("role", "pageTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setProperty("role", "subtitle")
    subtitle_label.setWordWrap(True)
    subtitle_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    layout.addWidget(title_label)
    layout.addWidget(subtitle_label)
    outer.addLayout(layout)
    outer.addStretch()
    if action:
        outer.addWidget(action, 0, Qt.AlignmentFlag.AlignTop)
    return container


def page_layout(root: QWidget, title: str, subtitle: str, action: QWidget | None = None) -> QVBoxLayout:
    outer = QVBoxLayout(root)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)
    scroll = QScrollArea()
    scroll.setObjectName("PageScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    content = QWidget()
    content.setObjectName("PageContent")
    layout = QVBoxLayout(content)
    layout.setContentsMargins(Spacing.PAGE, Spacing.PAGE, Spacing.PAGE, Spacing.PAGE)
    layout.setSpacing(Spacing.GAP)
    header = page_header(title, subtitle, action)
    header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    layout.addWidget(header)
    scroll.setWidget(content)
    outer.addWidget(scroll)
    root.page_scroll = scroll
    root.page_content = content
    return layout


def icon_label(icon: str, text: str) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    icon_widget = QLabel(icon)
    icon_widget.setProperty("role", "icon")
    text_widget = QLabel(text)
    layout.addWidget(icon_widget)
    layout.addWidget(text_widget)
    layout.addStretch()
    return container


def create_card(
    title: str | None = None,
    max_height: int | None = None,
    subtitle: str | None = None,
    action: QWidget | None = None,
    role: str = "card",
) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setProperty("role", role)
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    if max_height:
        card.setMaximumHeight(max_height)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(Spacing.CARD, Spacing.CARD, Spacing.CARD, Spacing.CARD)
    layout.setSpacing(14)
    if title:
        heading = QHBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(12)
        labels = QVBoxLayout()
        labels.setContentsMargins(0, 0, 0, 0)
        labels.setSpacing(3)
        label = QLabel(title)
        label.setProperty("role", "sectionTitle")
        labels.addWidget(label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setProperty("role", "sectionSubtitle")
            subtitle_label.setWordWrap(True)
            subtitle_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            labels.addWidget(subtitle_label)
        heading.addLayout(labels, 1)
        if action:
            heading.addWidget(action, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(heading)
    return card, layout


def metric_card(label: str, value: str, helper: str | None = None, tone: str | None = None) -> tuple[QFrame, QLabel]:
    card, layout = create_card(role="metricCard")
    card.setProperty("tone", tone or "neutral")
    card.setMinimumHeight(122)
    card.setMaximumHeight(145)
    label_widget = QLabel(label)
    label_widget.setProperty("role", "metricLabel")
    value_widget = QLabel(value)
    value_widget.setProperty("role", "metricValue")
    value_widget.setMinimumHeight(36)
    value_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    if tone:
        value_widget.setProperty("tone", tone)
    layout.addWidget(label_widget)
    layout.addWidget(value_widget)
    if helper:
        helper_widget = QLabel(helper)
        helper_widget.setProperty("role", "helper")
        helper_widget.setWordWrap(True)
        helper_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(helper_widget)
    layout.addStretch()
    return card, value_widget


def primary_button(text: str, icon: str | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("variant", "primary")
    _apply_button_icon(button, icon, "#ffffff")
    return button


def secondary_button(text: str, icon: str | None = None) -> QPushButton:
    button = QPushButton(text)
    _apply_button_icon(button, icon, Colors.TEXT_SECONDARY)
    return button


def soft_button(text: str, icon_name: str | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("variant", "soft")
    _apply_button_icon(button, icon_name, "#4f50c7")
    return button


def ghost_button(text: str, icon_name: str | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("variant", "ghost")
    _apply_button_icon(button, icon_name, Colors.TEXT_SECONDARY)
    return button


def danger_button(text: str, icon_name: str | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("variant", "danger")
    _apply_button_icon(button, icon_name, Colors.NEGATIVE)
    return button


def _apply_button_icon(button: QPushButton, icon_name: str | None, color: str) -> None:
    if not icon_name:
        return
    aliases = {"+": "plus", "\u21bb": "backup", "\u25a3": "folder"}
    button.setIcon(icon(aliases.get(icon_name, icon_name), color, 17))
    button.setIconSize(QSize(17, 17))


def chip_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("variant", "chip")
    button.setCheckable(True)
    return button


def nav_button(text: str, icon: str = "") -> QPushButton:
    button = QPushButton(f"{icon}  {text}" if icon else text)
    button.setProperty("variant", "nav")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setCheckable(True)
    button.setToolTip(text)
    button.setProperty("label", text)
    button.setProperty("icon", icon)
    return button


def actions_row(*buttons: QPushButton) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    for button in buttons:
        layout.addWidget(button)
    layout.addStretch()
    return container


def toolbar(left: list[QWidget] | None = None, right: list[QWidget] | None = None) -> QFrame:
    container = QFrame()
    container.setProperty("role", "toolbar")
    layout = QHBoxLayout(container)
    layout.setContentsMargins(8, 7, 8, 7)
    layout.setSpacing(7)
    for widget in left or []:
        layout.addWidget(widget)
    layout.addStretch()
    for widget in right or []:
        layout.addWidget(widget)
    return container


def empty_state(title: str, subtitle: str | None = None, action: QWidget | None = None) -> QWidget:
    container = QWidget()
    container.setProperty("role", "empty")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(18, 22, 18, 22)
    layout.setSpacing(8)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title_label = QLabel(title)
    title_label.setProperty("role", "emptyTitle")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setProperty("role", "emptySubtitle")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)
    if action:
        layout.addWidget(action, 0, Qt.AlignmentFlag.AlignCenter)
    container.setMinimumHeight(120)
    return container


def badge(text: str, tone: str = "neutral") -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "badge")
    label.setProperty("tone", tone)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setMinimumHeight(24)
    return label


def badge_tone(kind: str) -> str:
    normalized = (kind or "").lower()
    if normalized in {"income", "active"}:
        return "positive"
    if normalized in {"expense", "inactive"}:
        return "negative" if normalized == "expense" else "muted"
    if normalized in {"transfer", "transfer_out", "transfer_in", "adjustment"}:
        return "info"
    return "neutral"


def pretty_type(kind: str) -> str:
    normalized = (kind or "").replace("_", " ").strip()
    return normalized.title() if normalized else "Other"


def amount_item(value: object, neutral: bool = False) -> QTableWidgetItem:
    amount = to_decimal(value)
    item = QTableWidgetItem(format_money(amount))
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if not neutral:
        if amount > 0:
            item.setForeground(QColor(Colors.POSITIVE))
        elif amount < 0:
            item.setForeground(QColor(Colors.NEGATIVE))
    return item


def style_table(table: QTableWidget | QTableView, visible_rows: int | None = None) -> None:
    table.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setWordWrap(False)
    table.verticalHeader().setDefaultSectionSize(44)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    if visible_rows:
        table.setMinimumHeight(44 + visible_rows * 44)
        table.setMaximumHeight(44 + visible_rows * 44)


def style_tree(tree: QTreeWidget, visible_rows: int | None = None) -> None:
    tree.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
    tree.setAlternatingRowColors(True)
    tree.setRootIsDecorated(True)
    tree.setIndentation(22)
    tree.setUniformRowHeights(True)
    tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    tree.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    tree.setAnimated(True)
    tree.setItemsExpandable(True)
    tree.setExpandsOnDoubleClick(True)
    tree.setStyleSheet(f"QTreeWidget::branch {{ color: {Colors.TEXT_SECONDARY}; }}")
    tree.header().setStretchLastSection(True)
    tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    tree.setStyleSheet(f"QTreeWidget::branch {{ color: {Colors.TEXT_SECONDARY}; }}")
    if visible_rows:
        tree.setMinimumHeight(44 + visible_rows * 44)
        tree.setMaximumHeight(44 + visible_rows * 44)


def clear_layout(layout: QGridLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.setParent(None)
