from __future__ import annotations

import secrets

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    Property,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QSignalBlocker,
)
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLineEdit,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from app.ui.icons import icon
from app.ui.theme import Colors


class ScrambledPasswordInput(QLineEdit):
    """Native password input painted as a harmless, randomized cipher."""

    MASK_GROUPS = (
        tuple("2345789"),
        tuple("AKQRmxz"),
        (".", "·", "•"),
    )
    MASK_ALPHABET = tuple(
        token for group in MASK_GROUPS for token in group
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._privacy_mask = ""
        self.textChanged.connect(self._regenerate_privacy_mask)
        self.cursorPositionChanged.connect(lambda *_: self.update())
        self.selectionChanged.connect(self.update)

    def privacy_mask(self) -> str:
        return self._privacy_mask

    def _regenerate_privacy_mask(self, *_args) -> None:
        tokens: list[str] = []
        while len(tokens) < len(self.text()):
            groups = list(self.MASK_GROUPS)
            secrets.SystemRandom().shuffle(groups)
            tokens.extend(secrets.choice(group) for group in groups)
        self._privacy_mask = "".join(tokens[: len(self.text())])
        self.update()

    def setEchoMode(self, mode: QLineEdit.EchoMode) -> None:
        super().setEchoMode(mode)
        if mode == QLineEdit.EchoMode.Password:
            self._regenerate_privacy_mask()
        else:
            self.update()

    def paintEvent(self, event) -> None:
        if (
            self.echoMode() != QLineEdit.EchoMode.Password
            or not self.text()
        ):
            super().paintEvent(event)
            return

        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.fillRect(self.rect(), self.palette().color(QPalette.ColorRole.Base))

        content = self.contentsRect().adjusted(1, 0, -1, 0)
        painter.setClipRect(content)
        painter.setFont(self.font())
        metrics = painter.fontMetrics()
        slot_width = max(11, metrics.horizontalAdvance("0") + 2)
        mask_width = len(self._privacy_mask) * slot_width
        cursor_position = self.cursorPosition()
        cursor_offset = cursor_position * slot_width
        scroll = max(
            0,
            min(
                max(0, mask_width - content.width()),
                cursor_offset - content.width() + slot_width,
            ),
        )
        start_x = content.left() - scroll

        selection_start = self.selectionStart()
        selection_end = (
            selection_start + len(self.selectedText())
            if selection_start >= 0
            else -1
        )
        normal_color = self.palette().color(QPalette.ColorRole.Text)
        selected_color = self.palette().color(
            QPalette.ColorRole.HighlightedText
        )
        selection_color = self.palette().color(
            QPalette.ColorRole.Highlight
        )

        for index, token in enumerate(self._privacy_mask):
            token_rect = QRectF(
                start_x + index * slot_width,
                content.top(),
                slot_width,
                content.height(),
            )
            selected = selection_start <= index < selection_end
            if selected:
                painter.fillRect(token_rect, selection_color)
            painter.setPen(selected_color if selected else normal_color)
            painter.drawText(
                token_rect,
                Qt.AlignmentFlag.AlignCenter,
                token,
            )

        if self.hasFocus():
            caret_x = start_x + cursor_position * slot_width
            painter.setPen(QPen(normal_color, 1.4))
            painter.drawLine(
                int(caret_x),
                content.top() + 8,
                int(caret_x),
                content.bottom() - 8,
            )


class PeekMascot(QWidget):
    """Tiny password guardian whose eyelids follow the reveal state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._openness = 0.0
        self.setFixedSize(46, 30)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.animation = QPropertyAnimation(self, b"openness", self)
        self.animation.setDuration(280)
        self.animation.setEasingCurve(QEasingCurve.Type.OutBack)

    def get_openness(self) -> float:
        return self._openness

    def set_openness(self, value: float) -> None:
        self._openness = max(0.0, min(1.0, float(value)))
        self.update()

    openness = Property(float, get_openness, set_openness)

    def set_peeking(self, peeking: bool, *, animate: bool = True) -> None:
        target = 1.0 if peeking else 0.0
        self.animation.stop()
        if not animate:
            self.set_openness(target)
            return
        self.animation.setStartValue(self._openness)
        self.animation.setEndValue(target)
        self.animation.start()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(Colors.TEXT))
        painter.drawRoundedRect(QRectF(0, 0, 46, 30), 14, 14)
        for left in (11.0, 27.0):
            eye = QRectF(left, 10, 8, 9)
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(eye)
            painter.setBrush(QColor(Colors.TEXT))
            pupil = QRectF(left + 3.0, 13.0, 2.4, 3.0)
            painter.drawEllipse(pupil)
            lid_height = 9.0 * (1.0 - self._openness)
            if lid_height > 0.15:
                painter.drawRoundedRect(
                    QRectF(left - 0.4, 9.4, 8.8, lid_height),
                    4,
                    4,
                )
        if self._openness > 0.65:
            painter.setPen(
                QPen(
                    QColor("#ffffff"),
                    1.2,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
            )
            painter.drawArc(QRectF(18, 18, 10, 6), 200 * 16, 140 * 16)


class PasswordField(QWidget):
    """Password input with a keyboard-accessible trailing eye control."""

    def __init__(
        self,
        placeholder: str = "",
        *,
        mascot: bool = False,
        max_length: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.has_mascot = mascot
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.setMinimumHeight(68 if mascot else 56)

        self.surface = QFrame(self)
        self.surface.setProperty("role", "passwordField")
        shadow = QGraphicsDropShadowEffect(self.surface)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 16))
        self.surface.setGraphicsEffect(shadow)
        field_layout = QHBoxLayout(self.surface)
        field_layout.setContentsMargins(14, 0, 8, 0)
        field_layout.setSpacing(5)

        self.input = ScrambledPasswordInput()
        self.input.setProperty("role", "passwordInput")
        self.input.setEchoMode(QLineEdit.EchoMode.Password)
        self.input.setPlaceholderText(placeholder)
        if max_length is not None:
            self.input.setMaxLength(max_length)
        field_layout.addWidget(self.input, 1)

        self.toggle_button = QToolButton()
        self.toggle_button.setProperty("role", "passwordToggle")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setAutoRaise(True)
        self.toggle_button.setFixedSize(34, 34)
        self.toggle_button.setIconSize(QSize(22, 22))
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.toggled.connect(self._set_revealed)
        field_layout.addWidget(self.toggle_button)

        self.mascot = PeekMascot(self) if mascot else None
        self.input.installEventFilter(self)
        self.toggle_button.installEventFilter(self)
        self._update_toggle()

        # Preserve the familiar QLineEdit signal surface for dialog call sites.
        self.returnPressed = self.input.returnPressed
        self.textChanged = self.input.textChanged

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        top = 12 if self.has_mascot else 0
        self.surface.setGeometry(0, top, self.width(), 56)
        if self.mascot is not None:
            self.mascot.move(max(0, self.width() - 80), 0)
            self.mascot.raise_()

    def eventFilter(self, watched, event) -> bool:
        if watched in {self.input, self.toggle_button} and event.type() in {
            QEvent.Type.FocusIn,
            QEvent.Type.FocusOut,
        }:
            focused = self.input.hasFocus() or self.toggle_button.hasFocus()
            self.surface.setProperty("focused", focused)
            self.surface.style().unpolish(self.surface)
            self.surface.style().polish(self.surface)
        return super().eventFilter(watched, event)

    def _set_revealed(self, revealed: bool) -> None:
        self.input.setEchoMode(
            QLineEdit.EchoMode.Normal
            if revealed
            else QLineEdit.EchoMode.Password
        )
        if self.mascot is not None:
            self.mascot.set_peeking(revealed)
        self._update_toggle()

    def _update_toggle(self) -> None:
        revealed = self.input.echoMode() == QLineEdit.EchoMode.Normal
        label = "Hide password" if revealed else "Show password"
        self.toggle_button.setIcon(
            icon(
                "eye_off" if revealed else "eye",
                Colors.TEXT,
                20,
            )
        )
        self.toggle_button.setToolTip(label)
        self.toggle_button.setAccessibleName(label)

    def text(self) -> str:
        return self.input.text()

    def setText(self, value: str) -> None:
        self.input.setText(value)

    def clear(self) -> None:
        self.input.clear()

    def selectAll(self) -> None:
        self.input.selectAll()

    def setPlaceholderText(self, value: str) -> None:
        self.input.setPlaceholderText(value)

    def setMaxLength(self, value: int) -> None:
        self.input.setMaxLength(value)

    def echoMode(self) -> QLineEdit.EchoMode:
        return self.input.echoMode()

    def setEchoMode(self, mode: QLineEdit.EchoMode) -> None:
        self.input.setEchoMode(mode)
        revealed = mode == QLineEdit.EchoMode.Normal
        with QSignalBlocker(self.toggle_button):
            self.toggle_button.setChecked(revealed)
        if self.mascot is not None:
            self.mascot.set_peeking(revealed, animate=False)
        self._update_toggle()

    def setFocus(
        self,
        reason: Qt.FocusReason = Qt.FocusReason.OtherFocusReason,
    ) -> None:
        self.input.setFocus(reason)
