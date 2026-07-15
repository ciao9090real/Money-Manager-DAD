from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget


def _draw_icon(painter: QPainter, name: str, rect: QRectF, color: str) -> None:
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), max(1.6, rect.width() / 12))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

    if name == "dashboard":
        painter.drawRoundedRect(QRectF(x, y, w * 0.42, h * 0.42), 2, 2)
        painter.drawRoundedRect(QRectF(x + w * 0.58, y, w * 0.42, h * 0.64), 2, 2)
        painter.drawRoundedRect(QRectF(x, y + h * 0.58, w * 0.42, h * 0.42), 2, 2)
        painter.drawRoundedRect(QRectF(x + w * 0.58, y + h * 0.80, w * 0.42, h * 0.20), 2, 2)
    elif name == "upcoming":
        painter.drawRoundedRect(QRectF(x + w * 0.06, y + h * 0.16, w * 0.88, h * 0.76), 3, 3)
        painter.drawLine(QPointF(x + w * 0.06, y + h * 0.38), QPointF(x + w * 0.94, y + h * 0.38))
        painter.drawLine(QPointF(x + w * 0.28, y), QPointF(x + w * 0.28, y + h * 0.26))
        painter.drawLine(QPointF(x + w * 0.72, y), QPointF(x + w * 0.72, y + h * 0.26))
        painter.drawEllipse(QPointF(x + w * 0.36, y + h * 0.61), w * 0.035, w * 0.035)
        painter.drawEllipse(QPointF(x + w * 0.62, y + h * 0.61), w * 0.035, w * 0.035)
    elif name == "accounts":
        painter.drawRoundedRect(QRectF(x, y + h * 0.20, w, h * 0.72), 3, 3)
        painter.drawLine(QPointF(x, y + h * 0.40), QPointF(x + w, y + h * 0.40))
        painter.drawEllipse(QPointF(x + w * 0.76, y + h * 0.66), w * 0.06, w * 0.06)
        painter.drawLine(QPointF(x + w * 0.14, y + h * 0.08), QPointF(x + w * 0.78, y + h * 0.08))
    elif name == "accounts_expand":
        _draw_icon(painter, "accounts", QRectF(x, y + h * 0.10, w * 0.68, h * 0.80), color)
        painter.drawLine(
            QPointF(x + w * 0.78, y + h * 0.31),
            QPointF(x + w * 0.96, y + h * 0.50),
        )
        painter.drawLine(
            QPointF(x + w * 0.96, y + h * 0.50),
            QPointF(x + w * 0.78, y + h * 0.69),
        )
    elif name == "transactions":
        painter.drawLine(QPointF(x, y + h * 0.30), QPointF(x + w * 0.78, y + h * 0.30))
        painter.drawLine(QPointF(x + w * 0.78, y + h * 0.30), QPointF(x + w * 0.62, y + h * 0.12))
        painter.drawLine(QPointF(x + w * 0.78, y + h * 0.30), QPointF(x + w * 0.62, y + h * 0.48))
        painter.drawLine(QPointF(x + w, y + h * 0.70), QPointF(x + w * 0.22, y + h * 0.70))
        painter.drawLine(QPointF(x + w * 0.22, y + h * 0.70), QPointF(x + w * 0.38, y + h * 0.52))
        painter.drawLine(QPointF(x + w * 0.22, y + h * 0.70), QPointF(x + w * 0.38, y + h * 0.88))
    elif name == "investments":
        painter.drawLine(QPointF(x + w * 0.08, y + h * 0.88), QPointF(x + w * 0.08, y + h * 0.18))
        painter.drawLine(QPointF(x + w * 0.08, y + h * 0.88), QPointF(x + w * 0.92, y + h * 0.88))
        path = QPainterPath()
        path.moveTo(x + w * 0.18, y + h * 0.70)
        path.lineTo(x + w * 0.40, y + h * 0.50)
        path.lineTo(x + w * 0.58, y + h * 0.60)
        path.lineTo(x + w * 0.86, y + h * 0.24)
        painter.drawPath(path)
        painter.drawLine(QPointF(x + w * 0.70, y + h * 0.25), QPointF(x + w * 0.86, y + h * 0.24))
        painter.drawLine(QPointF(x + w * 0.86, y + h * 0.24), QPointF(x + w * 0.85, y + h * 0.40))
    elif name == "loans":
        roof = QPainterPath()
        roof.moveTo(x + w * 0.08, y + h * 0.34)
        roof.lineTo(x + w * 0.50, y + h * 0.08)
        roof.lineTo(x + w * 0.92, y + h * 0.34)
        roof.closeSubpath()
        painter.drawPath(roof)
        for column in (0.24, 0.50, 0.76):
            painter.drawLine(
                QPointF(x + w * column, y + h * 0.40),
                QPointF(x + w * column, y + h * 0.78),
            )
        painter.drawLine(QPointF(x + w * 0.10, y + h * 0.82), QPointF(x + w * 0.90, y + h * 0.82))
        painter.drawLine(QPointF(x + w * 0.04, y + h * 0.94), QPointF(x + w * 0.96, y + h * 0.94))
    elif name in {"chevron_left", "chevron_right"}:
        left = name == "chevron_left"
        outer = 0.64 if left else 0.36
        inner = 0.32 if left else 0.68
        painter.drawLine(
            QPointF(x + w * outer, y + h * 0.16),
            QPointF(x + w * inner, y + h * 0.50),
        )
        painter.drawLine(
            QPointF(x + w * inner, y + h * 0.50),
            QPointF(x + w * outer, y + h * 0.84),
        )
    elif name == "settings":
        painter.drawEllipse(QRectF(x + w * 0.33, y + h * 0.33, w * 0.34, h * 0.34))
        painter.drawEllipse(QRectF(x + w * 0.10, y + h * 0.10, w * 0.80, h * 0.80))
        for px, py, qx, qy in (
            (0.50, 0.00, 0.50, 0.15), (0.50, 0.85, 0.50, 1.00),
            (0.00, 0.50, 0.15, 0.50), (0.85, 0.50, 1.00, 0.50),
        ):
            painter.drawLine(QPointF(x + w * px, y + h * py), QPointF(x + w * qx, y + h * qy))
    elif name == "plus":
        painter.drawLine(QPointF(x + w * 0.18, y + h * 0.50), QPointF(x + w * 0.82, y + h * 0.50))
        painter.drawLine(QPointF(x + w * 0.50, y + h * 0.18), QPointF(x + w * 0.50, y + h * 0.82))
    elif name == "edit":
        path = QPainterPath()
        path.moveTo(x + w * 0.18, y + h * 0.78)
        path.lineTo(x + w * 0.24, y + h * 0.55)
        path.lineTo(x + w * 0.68, y + h * 0.11)
        path.lineTo(x + w * 0.89, y + h * 0.32)
        path.lineTo(x + w * 0.45, y + h * 0.76)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(x + w * 0.18, y + h * 0.85), QPointF(x + w * 0.82, y + h * 0.85))
    elif name in {"archive", "backup"}:
        painter.drawRoundedRect(QRectF(x + w * 0.10, y + h * 0.28, w * 0.80, h * 0.62), 2, 2)
        painter.drawRoundedRect(QRectF(x, y + h * 0.08, w, h * 0.24), 2, 2)
        painter.drawLine(QPointF(x + w * 0.36, y + h * 0.55), QPointF(x + w * 0.64, y + h * 0.55))
    elif name == "restore":
        path = QPainterPath()
        path.moveTo(x + w * 0.20, y + h * 0.36)
        path.cubicTo(
            x + w * 0.38,
            y + h * 0.06,
            x + w * 0.84,
            y + h * 0.16,
            x + w * 0.86,
            y + h * 0.54,
        )
        path.cubicTo(
            x + w * 0.88,
            y + h * 0.86,
            x + w * 0.48,
            y + h * 1.02,
            x + w * 0.24,
            y + h * 0.74,
        )
        painter.drawPath(path)
        painter.drawLine(QPointF(x + w * 0.20, y + h * 0.36), QPointF(x + w * 0.20, y + h * 0.08))
        painter.drawLine(QPointF(x + w * 0.20, y + h * 0.36), QPointF(x + w * 0.48, y + h * 0.36))
    elif name == "delete":
        painter.drawRoundedRect(QRectF(x + w * 0.20, y + h * 0.24, w * 0.60, h * 0.68), 2, 2)
        painter.drawLine(QPointF(x + w * 0.10, y + h * 0.20), QPointF(x + w * 0.90, y + h * 0.20))
        painter.drawLine(QPointF(x + w * 0.36, y + h * 0.08), QPointF(x + w * 0.64, y + h * 0.08))
        painter.drawLine(QPointF(x + w * 0.40, y + h * 0.40), QPointF(x + w * 0.40, y + h * 0.74))
        painter.drawLine(QPointF(x + w * 0.60, y + h * 0.40), QPointF(x + w * 0.60, y + h * 0.74))
    elif name == "play":
        path = QPainterPath()
        path.moveTo(x + w * 0.24, y + h * 0.12)
        path.lineTo(x + w * 0.84, y + h * 0.50)
        path.lineTo(x + w * 0.24, y + h * 0.88)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "pause":
        painter.drawRoundedRect(QRectF(x + w * 0.20, y + h * 0.12, w * 0.20, h * 0.76), 1, 1)
        painter.drawRoundedRect(QRectF(x + w * 0.60, y + h * 0.12, w * 0.20, h * 0.76), 1, 1)
    elif name == "skip":
        painter.drawLine(QPointF(x + w * 0.12, y + h * 0.18), QPointF(x + w * 0.58, y + h * 0.50))
        painter.drawLine(QPointF(x + w * 0.58, y + h * 0.50), QPointF(x + w * 0.12, y + h * 0.82))
        painter.drawLine(QPointF(x + w * 0.72, y + h * 0.18), QPointF(x + w * 0.72, y + h * 0.82))
    elif name == "search":
        painter.drawEllipse(QRectF(x + w * 0.08, y + h * 0.08, w * 0.62, h * 0.62))
        painter.drawLine(QPointF(x + w * 0.62, y + h * 0.62), QPointF(x + w * 0.94, y + h * 0.94))
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(x, y + h * 0.24)
        path.lineTo(x + w * 0.36, y + h * 0.24)
        path.lineTo(x + w * 0.48, y + h * 0.38)
        path.lineTo(x + w, y + h * 0.38)
        path.lineTo(x + w * 0.90, y + h * 0.88)
        path.lineTo(x + w * 0.08, y + h * 0.88)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "download":
        painter.drawLine(QPointF(x + w * 0.50, y), QPointF(x + w * 0.50, y + h * 0.65))
        painter.drawLine(QPointF(x + w * 0.26, y + h * 0.43), QPointF(x + w * 0.50, y + h * 0.68))
        painter.drawLine(QPointF(x + w * 0.74, y + h * 0.43), QPointF(x + w * 0.50, y + h * 0.68))
        painter.drawLine(QPointF(x + w * 0.12, y + h * 0.92), QPointF(x + w * 0.88, y + h * 0.92))
    elif name == "tag":
        path = QPainterPath()
        path.moveTo(x + w * 0.06, y + h * 0.14)
        path.lineTo(x + w * 0.56, y + h * 0.14)
        path.lineTo(x + w * 0.94, y + h * 0.52)
        path.lineTo(x + w * 0.52, y + h * 0.94)
        path.lineTo(x + w * 0.06, y + h * 0.48)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawEllipse(QPointF(x + w * 0.30, y + h * 0.36), w * 0.05, w * 0.05)
    elif name == "shield":
        path = QPainterPath()
        path.moveTo(x + w * 0.50, y)
        path.lineTo(x + w * 0.88, y + h * 0.16)
        path.lineTo(x + w * 0.82, y + h * 0.65)
        path.quadTo(x + w * 0.72, y + h * 0.86, x + w * 0.50, y + h)
        path.quadTo(x + w * 0.28, y + h * 0.86, x + w * 0.18, y + h * 0.65)
        path.lineTo(x + w * 0.12, y + h * 0.16)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "copy":
        painter.drawRoundedRect(QRectF(x + w * 0.25, y + h * 0.05, w * 0.68, h * 0.68), 2, 2)
        painter.drawRoundedRect(QRectF(x + w * 0.07, y + h * 0.25, w * 0.68, h * 0.68), 2, 2)
    else:
        painter.drawEllipse(rect)


class LineIcon(QWidget):
    def __init__(self, name: str, color: str, size: int = 20, parent: QWidget | None = None):
        super().__init__(parent)
        self.name = name
        self.color = color
        self.setFixedSize(size, size)

    def set_color(self, color: str) -> None:
        self.color = color
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        margin = max(2.0, self.width() * 0.12)
        _draw_icon(
            painter,
            self.name,
            QRectF(margin, margin, self.width() - margin * 2, self.height() - margin * 2),
            self.color,
        )


def icon(name: str, color: str = "#60716b", size: int = 18) -> QIcon:
    ratio = 2
    pixmap = QPixmap(QSize(size * ratio, size * ratio))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    _draw_icon(painter, name, QRectF(3, 3, size * ratio - 6, size * ratio - 6), color)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return QIcon(pixmap)
