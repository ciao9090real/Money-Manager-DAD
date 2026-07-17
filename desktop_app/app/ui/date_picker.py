from __future__ import annotations

from PySide6.QtCore import QDate, QPointF, QRect, Qt
from PySide6.QtGui import QMouseEvent, QPainter
from PySide6.QtWidgets import QCalendarWidget, QDateEdit, QWidget

from app.ui.icons import icon
from app.ui.theme import Colors


class DatePicker(QDateEdit):
    """Click-first date field with a consistent calendar popup."""

    def __init__(
        self,
        value: QDate | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(value or QDate.currentDate(), parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd MMM yyyy")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Choose a date")
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setCursor(Qt.CursorShape.PointingHandCursor)
        self._calendar_icon = icon("upcoming", Colors.TEXT_SECONDARY, 16)

        calendar = self.calendarWidget()
        calendar.setObjectName("BookingCalendar")
        calendar.setMinimumSize(320, 240)
        calendar.setGridVisible(False)
        calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        calendar.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            super().mousePressEvent(self._drop_down_event(event))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            super().mouseReleaseEvent(self._drop_down_event(event))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        # Scrolling a form should never silently change a financial date.
        event.ignore()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        self._calendar_icon.paint(
            painter,
            QRect(self.width() - 27, (self.height() - 16) // 2, 16, 16),
        )

    def _drop_down_event(self, event: QMouseEvent) -> QMouseEvent:
        local_position = QPointF(max(1, self.width() - 8), self.height() / 2)
        global_position = QPointF(self.mapToGlobal(local_position.toPoint()))
        return QMouseEvent(
            event.type(),
            local_position,
            global_position,
            event.button(),
            event.buttons(),
            event.modifiers(),
        )
