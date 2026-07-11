from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import Colors, Spacing
from app.utils.money import format_money, to_decimal


def page_header(title: str, subtitle: str, action: QWidget | None = None) -> QWidget:
    container = QWidget()
    outer = QHBoxLayout(container)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(Spacing.GAP)
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    title_label = QLabel(title)
    title_label.setProperty("role", "pageTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setProperty("role", "subtitle")
    layout.addWidget(title_label)
    layout.addWidget(subtitle_label)
    outer.addLayout(layout)
    outer.addStretch()
    if action:
        outer.addWidget(action, 0, Qt.AlignmentFlag.AlignTop)
    return container


def page_layout(root: QWidget, title: str, subtitle: str, action: QWidget | None = None) -> QVBoxLayout:
    layout = QVBoxLayout(root)
    layout.setContentsMargins(Spacing.PAGE, Spacing.PAGE, Spacing.PAGE, Spacing.PAGE)
    layout.setSpacing(Spacing.GAP + 4)
    header = page_header(title, subtitle, action)
    header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    layout.addWidget(header)
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


def create_card(title: str | None = None, max_height: int | None = None) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setProperty("role", "card")
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    if max_height:
        card.setMaximumHeight(max_height)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(Spacing.CARD, Spacing.CARD, Spacing.CARD, Spacing.CARD)
    layout.setSpacing(12)
    if title:
        label = QLabel(title)
        label.setProperty("role", "sectionTitle")
        layout.addWidget(label)
    return card, layout


def metric_card(label: str, value: str, helper: str | None = None, tone: str | None = None) -> tuple[QFrame, QLabel]:
    card, layout = create_card()
    card.setMinimumHeight(132)
    card.setMaximumHeight(156)
    label_widget = QLabel(label)
    label_widget.setProperty("role", "metricLabel")
    value_widget = QLabel(value)
    value_widget.setProperty("role", "metricValue")
    value_widget.setMinimumHeight(34)
    value_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    if tone:
        value_widget.setProperty("tone", tone)
    layout.addWidget(label_widget)
    layout.addWidget(value_widget)
    if helper:
        helper_widget = QLabel(helper)
        helper_widget.setProperty("role", "helper")
        layout.addWidget(helper_widget)
    layout.addStretch()
    return card, value_widget


def primary_button(text: str, icon: str | None = None) -> QPushButton:
    button = QPushButton(f"{icon}  {text}" if icon else text)
    button.setProperty("variant", "primary")
    return button


def secondary_button(text: str, icon: str | None = None) -> QPushButton:
    return QPushButton(f"{icon}  {text}" if icon else text)


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


def style_table(table: QTableWidget, visible_rows: int | None = None) -> None:
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setWordWrap(False)
    table.verticalHeader().setDefaultSectionSize(38)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    if visible_rows:
        table.setMinimumHeight(42 + visible_rows * 38)
        table.setMaximumHeight(42 + visible_rows * 38)


def style_tree(tree: QTreeWidget, visible_rows: int | None = None) -> None:
    tree.setAlternatingRowColors(True)
    tree.setRootIsDecorated(True)
    tree.setIndentation(24)
    tree.setUniformRowHeights(True)
    tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    tree.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    tree.header().setStretchLastSection(True)
    tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    tree.setStyleSheet(f"QTreeWidget::branch {{ color: {Colors.TEXT_SECONDARY}; }}")
    if visible_rows:
        tree.setMinimumHeight(42 + visible_rows * 38)
        tree.setMaximumHeight(42 + visible_rows * 38)


def clear_layout(layout: QGridLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.setParent(None)
