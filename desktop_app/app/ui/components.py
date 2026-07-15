from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
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
    QStyledItemDelegate,
    QStyleOptionViewItem,
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


class FittedLabel(QLabel):
    """A bold label that keeps long values visible inside compact cards."""

    def __init__(self, text: str, maximum_size: int, minimum_size: int, parent=None):
        super().__init__(text, parent)
        self.maximum_size = maximum_size
        self.minimum_size = minimum_size
        self.setMinimumWidth(0)
        self.setToolTip(text)
        QTimer.singleShot(0, self._fit_text)

    def setText(self, text: str) -> None:
        super().setText(text)
        self.setToolTip(text)
        QTimer.singleShot(0, self._fit_text)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_text()

    def _fit_text(self) -> None:
        available = max(1, self.contentsRect().width() - 2)
        point_size = self.maximum_size
        while point_size > self.minimum_size:
            font = QFont(self.font())
            font.setPixelSize(point_size)
            font.setWeight(QFont.Weight.Bold)
            if QFontMetrics(font).horizontalAdvance(self.text()) <= available:
                break
            point_size -= 1
        font = QFont(self.font())
        font.setPixelSize(point_size)
        font.setWeight(QFont.Weight.Bold)
        self.setFont(font)


class BadgeDelegate(QStyledItemDelegate):
    """Paint a subtle pill badge without replacing a model-backed table cell."""

    TONES = {
        "neutral": (Colors.NEUTRAL_BADGE_BG, Colors.NEUTRAL_BADGE_TEXT),
        "positive": (Colors.POSITIVE_BADGE_BG, Colors.POSITIVE_BADGE_TEXT),
        "negative": (Colors.NEGATIVE_BADGE_BG, Colors.NEGATIVE_BADGE_TEXT),
        "info": (Colors.INFO_BADGE_BG, Colors.INFO_BADGE_TEXT),
        "muted": (Colors.MUTED_BADGE_BG, Colors.MUTED_BADGE_TEXT),
    }

    def __init__(self, tone_for_text: Callable[[str], str] | None = None, parent=None):
        super().__init__(parent)
        self.tone_for_text = tone_for_text or (lambda _text: "neutral")

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        background_option = QStyleOptionViewItem(option)
        background_option.text = ""
        super().paint(painter, background_option, index)
        if not text:
            return

        painter.save()
        font = QFont(option.font)
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.DemiBold)
        metrics = QFontMetrics(font)
        width = min(option.rect.width() - 16, metrics.horizontalAdvance(text) + 20)
        badge_rect = QRectF(
            option.rect.x() + 8,
            option.rect.y() + (option.rect.height() - 24) / 2,
            max(20, width),
            24,
        )
        tone = self.tone_for_text(text)
        background, foreground = self.TONES.get(tone, self.TONES["neutral"])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(badge_rect, 10, 10)
        painter.setFont(font)
        painter.setPen(QColor(foreground))
        elided = metrics.elidedText(
            text, Qt.TextElideMode.ElideRight, int(badge_rect.width() - 12)
        )
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, elided)
        painter.restore()


def page_header(title: str, subtitle: str, action: QWidget | None = None) -> QWidget:
    container = QWidget()
    outer = QHBoxLayout(container)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(Spacing.GAP)
    text_block = QWidget()
    text_block.setMinimumWidth(0)
    text_block.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    layout = QVBoxLayout(text_block)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)
    title_label = QLabel(title)
    title_label.setProperty("role", "pageTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setProperty("role", "subtitle")
    subtitle_label.setWordWrap(True)
    subtitle_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    layout.addWidget(title_label)
    layout.addWidget(subtitle_label)
    outer.addWidget(text_block, 1)
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


def section_heading(title: str, subtitle: str | None = None, action: QWidget | None = None) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(1, 2, 1, 0)
    layout.setSpacing(12)
    labels = QVBoxLayout()
    labels.setContentsMargins(0, 0, 0, 0)
    labels.setSpacing(2)
    title_label = QLabel(title)
    title_label.setProperty("role", "sectionTitle")
    labels.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setProperty("role", "sectionSubtitle")
        subtitle_label.setWordWrap(True)
        labels.addWidget(subtitle_label)
    layout.addLayout(labels, 1)
    if action:
        layout.addWidget(action, 0, Qt.AlignmentFlag.AlignTop)
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


def metric_card(
    label: str,
    value: str,
    helper: str | None = None,
    tone: str | None = None,
    compact: bool = False,
) -> tuple[QFrame, QLabel]:
    card, layout = create_card(role="metricCard")
    card.setProperty("tone", tone or "neutral")
    card.setMinimumWidth(0)
    card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    if compact:
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        card.setMinimumHeight(92)
        card.setMaximumHeight(104)
    else:
        card.setMinimumHeight(112)
        card.setMaximumHeight(128)
    label_widget = QLabel(label)
    label_widget.setProperty("role", "metricLabel")
    label_widget.setWordWrap(True)
    label_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    value_widget = FittedLabel(
        value,
        maximum_size=23 if compact else 27,
        minimum_size=12,
    )
    value_widget.setProperty("role", "metricValue")
    value_widget.setMinimumHeight(28 if compact else 36)
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
    label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    label.setMaximumWidth(max(54, QFontMetrics(label.font()).horizontalAdvance(text) + 28))
    return label


def badge_tone(kind: str) -> str:
    normalized = (kind or "").lower().replace(" ", "_")
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


def compact_money(value: object) -> str:
    """Keep dashboard metrics readable while preserving the full value in tooltips."""
    amount = to_decimal(value)
    magnitude = abs(amount)
    for threshold, suffix in (
        (Decimal("1000000000"), "B"),
        (Decimal("1000000"), "M"),
    ):
        if magnitude >= threshold:
            scaled = magnitude / threshold
            number = f"{scaled:.2f}".rstrip("0").rstrip(".")
            sign = "-" if amount < 0 else ""
            return f"{sign}€{number}{suffix}"
    return format_money(amount)


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
    tree.setStyleSheet(
        f"""
        QTreeWidget::branch {{ color: {Colors.TEXT_SECONDARY}; }}
        QTreeWidget::item:selected {{
            background: #e3e5ff;
            color: {Colors.TEXT};
        }}
        """
    )
    tree.header().setStretchLastSection(True)
    tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    if visible_rows:
        tree.setMinimumHeight(44 + visible_rows * 44)
        tree.setMaximumHeight(44 + visible_rows * 44)


def fit_item_view_height(view, row_count: int, minimum_rows: int = 1, maximum_rows: int = 8) -> None:
    rows = max(minimum_rows, min(maximum_rows, row_count))
    if hasattr(view, "horizontalHeader"):
        header = view.horizontalHeader()
        row_height = max(42, view.verticalHeader().defaultSectionSize())
    else:
        header = view.header()
        row_height = 44
    height = max(40, header.height()) + rows * row_height + 2
    view.setMinimumHeight(height)
    view.setMaximumHeight(height)


def clear_layout(layout: QGridLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.setParent(None)
