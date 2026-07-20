from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from app.ui.theme import Colors
from app.utils.money import format_money, to_decimal


def _short_money(value: float) -> str:
    absolute = abs(value)
    sign = "-" if value < 0 else ""
    if absolute >= 1_000_000:
        return f"{sign}€{absolute / 1_000_000:.1f}m"
    if absolute >= 1_000:
        return f"{sign}€{absolute / 1_000:.1f}k"
    return f"{sign}€{absolute:.0f}"


def _display_date(value: str) -> str:
    try:
        return date.fromisoformat(value).strftime("%d %b")
    except ValueError:
        return value


class LineChart(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._points: list[tuple[str, Decimal]] = []
        self._empty_text = "Record a market value to start the chart"
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def sizeHint(self) -> QSize:
        return QSize(620, 240)

    def set_data(
        self,
        points: list[tuple[str, Decimal]],
        empty_text: str | None = None,
    ) -> None:
        self._points = sorted(points, key=lambda point: point[0])
        if empty_text:
            self._empty_text = empty_text
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font())
        if not self._points:
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self._empty_text,
            )
            return

        plot = QRectF(58, 18, max(40, self.width() - 76), max(60, self.height() - 56))
        values = [float(value) for _date, value in self._points]
        low = min(values)
        high = max(values)
        span = high - low
        padding = max(span * 0.14, max(abs(high), 1) * 0.025, 1)
        low = max(0, low - padding)
        high += padding
        if high <= low:
            high = low + 1

        grid_pen = QPen(QColor(Colors.BORDER_SOFT), 1)
        label_color = QColor(Colors.TEXT_MUTED)
        small_font = QFont(self.font())
        small_font.setPointSize(8)
        painter.setFont(small_font)
        for index in range(4):
            ratio = index / 3
            y = plot.top() + ratio * plot.height()
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            axis_value = high - ratio * (high - low)
            painter.setPen(label_color)
            painter.drawText(
                QRectF(0, y - 9, 50, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                _short_money(axis_value),
            )

        def point_position(index: int, value: float) -> QPointF:
            if len(values) == 1:
                x = plot.center().x()
            else:
                x = plot.left() + index / (len(values) - 1) * plot.width()
            y = plot.bottom() - (value - low) / (high - low) * plot.height()
            return QPointF(x, y)

        positions = [point_position(index, value) for index, value in enumerate(values)]
        line_path = QPainterPath(positions[0])
        for position in positions[1:]:
            line_path.lineTo(position)

        area_path = QPainterPath(line_path)
        area_path.lineTo(positions[-1].x(), plot.bottom())
        area_path.lineTo(positions[0].x(), plot.bottom())
        area_path.closeSubpath()
        fill = QColor(Colors.PRIMARY)
        fill.setAlpha(24)
        painter.fillPath(area_path, fill)

        painter.setPen(QPen(QColor(Colors.PRIMARY), 2.4))
        painter.drawPath(line_path)
        painter.setBrush(QColor(Colors.CARD))
        painter.setPen(QPen(QColor(Colors.PRIMARY), 2))
        for position in positions:
            painter.drawEllipse(position, 3.5, 3.5)

        painter.setPen(label_color)
        label_count = min(6, len(self._points))
        if len(self._points) <= label_count:
            label_indices = list(range(len(self._points)))
        else:
            label_indices = sorted(
                {
                    round(index * (len(self._points) - 1) / (label_count - 1))
                    for index in range(label_count)
                }
            )
        date_totals: dict[str, int] = {}
        for point_date, _value in self._points:
            date_totals[point_date] = date_totals.get(point_date, 0) + 1
        date_occurrences: dict[str, int] = {}
        label_width = min(92.0, max(54.0, plot.width() / max(1, len(label_indices))))
        for point_index in label_indices:
            point_date = self._points[point_index][0]
            date_occurrences[point_date] = date_occurrences.get(point_date, 0) + 1
            label = _display_date(point_date)
            if date_totals[point_date] > 1:
                label += f" ({date_occurrences[point_date]})"
            x = positions[point_index].x()
            left = max(plot.left(), min(x - label_width / 2, plot.right() - label_width))
            painter.drawText(
                QRectF(left, plot.bottom() + 8, label_width, 18),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )

        value_font = QFont(self.font())
        value_font.setPointSize(9)
        value_font.setBold(True)
        painter.setFont(value_font)
        painter.setPen(QColor(Colors.TEXT))
        painter.drawText(
            QRectF(plot.left(), 0, plot.width(), 20),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            format_money(self._points[-1][1]),
        )


class PerformanceChart(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._points: list[tuple[str, Decimal, Decimal]] = []
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def sizeHint(self) -> QSize:
        return QSize(680, 270)

    def set_data(self, points: list[tuple[str, Decimal, Decimal]]) -> None:
        self._points = points
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font())
        if not self._points:
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Add funds or record a market value to start the graph",
            )
            return

        plot = QRectF(58, 34, max(40, self.width() - 76), max(70, self.height() - 72))
        contributed = [float(point[1]) for point in self._points]
        current_values = [float(point[2]) for point in self._points]
        all_values = contributed + current_values
        minimum_value = min(all_values)
        maximum_value = max(all_values)
        span = maximum_value - minimum_value
        padding = max(span * 0.1, maximum_value * 0.02, 1.0)
        minimum = max(0.0, min(all_values) - padding)
        maximum = max(all_values) + padding
        if maximum <= minimum:
            maximum = minimum + 1.0

        small_font = QFont(self.font())
        small_font.setPointSize(8)
        painter.setFont(small_font)
        for index in range(4):
            ratio = index / 3
            y = plot.top() + ratio * plot.height()
            painter.setPen(QPen(QColor(Colors.BORDER_SOFT), 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(
                QRectF(0, y - 9, 50, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                _short_money(maximum - ratio * (maximum - minimum)),
            )

        legend_font = QFont(self.font())
        legend_font.setPointSize(9)
        legend_font.setBold(True)
        painter.setFont(legend_font)
        legend_x = plot.left()
        for label, color, width in (
            ("Current value", Colors.PRIMARY, 108),
            ("Invested", Colors.ACCENT, 82),
        ):
            painter.setPen(QPen(QColor(color), 3))
            painter.drawLine(
                QPointF(legend_x, 13),
                QPointF(legend_x + 24, 13),
            )
            painter.setPen(QColor(Colors.TEXT_SECONDARY))
            painter.drawText(QRectF(legend_x + 32, 3, width, 20), label)
            legend_x += width + 48

        def positions(values: list[float]) -> list[QPointF]:
            result: list[QPointF] = []
            for index, value in enumerate(values):
                x = (
                    plot.center().x()
                    if len(values) == 1
                    else plot.left() + index / (len(values) - 1) * plot.width()
                )
                y = plot.bottom() - (value - minimum) / (maximum - minimum) * plot.height()
                result.append(QPointF(x, y))
            return result

        def draw_series(values: list[float], color: str) -> None:
            series_positions = positions(values)
            painter.setPen(QPen(QColor(color), 2.6))
            if len(series_positions) == 1:
                point = series_positions[0]
                painter.drawLine(
                    QPointF(plot.left(), point.y()),
                    QPointF(plot.right(), point.y()),
                )
            else:
                path = QPainterPath(series_positions[0])
                for previous, point in zip(series_positions, series_positions[1:]):
                    midpoint = (previous.x() + point.x()) / 2
                    path.cubicTo(
                        QPointF(midpoint, previous.y()),
                        QPointF(midpoint, point.y()),
                        point,
                    )
                painter.drawPath(path)
            painter.setBrush(QColor(Colors.CARD))
            painter.setPen(QPen(QColor(color), 2))
            for point in series_positions:
                radius = 3.5 if len(series_positions) <= 36 else 2.5
                painter.drawEllipse(point, radius, radius)

        draw_series(contributed, Colors.ACCENT)
        draw_series(current_values, Colors.PRIMARY)

        painter.setFont(small_font)
        painter.setPen(QColor(Colors.TEXT_MUTED))
        label_count = min(6, len(self._points))
        if len(self._points) <= label_count:
            label_indices = list(range(len(self._points)))
        else:
            label_indices = sorted(
                {
                    round(index * (len(self._points) - 1) / (label_count - 1))
                    for index in range(label_count)
                }
            )
        label_width = min(96.0, max(56.0, plot.width() / max(1, len(label_indices))))
        value_positions = positions(current_values)
        for point_index in label_indices:
            x = value_positions[point_index].x()
            left = max(plot.left(), min(x - label_width / 2, plot.right() - label_width))
            painter.drawText(
                QRectF(left, plot.bottom() + 8, label_width, 18),
                Qt.AlignmentFlag.AlignCenter,
                self._points[point_index][0],
            )

        value_font = QFont(self.font())
        value_font.setPointSize(9)
        value_font.setBold(True)
        painter.setFont(value_font)
        painter.setPen(QColor(Colors.PRIMARY))
        painter.drawText(
            QRectF(plot.left(), 3, plot.width(), 20),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            format_money(self._points[-1][2]),
        )


class AllocationChart(QWidget):
    BAR_COLORS = (
        Colors.PRIMARY,
        Colors.ACCENT,
        "#4778b8",
        Colors.POSITIVE,
        Colors.WARNING,
        Colors.TEXT_SECONDARY,
    )

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._items: list[tuple[str, Decimal]] = []
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def sizeHint(self) -> QSize:
        return QSize(360, 240)

    def set_data(self, items: list[tuple[str, Decimal]]) -> None:
        ordered = sorted(items, key=lambda item: item[1], reverse=True)
        if len(ordered) > 6:
            other = sum((value for _label, value in ordered[5:]), Decimal("0"))
            ordered = ordered[:5] + [("Other", other)]
        self._items = ordered
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font())
        if not self._items or not any(value > 0 for _label, value in self._items):
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Allocation appears when investments have value",
            )
            return

        maximum = float(max(value for _label, value in self._items))
        top = 12
        row_height = max(30, min(42, (self.height() - 20) // len(self._items)))
        label_width = min(110, max(76, int(self.width() * 0.28)))
        value_width = 82
        track_left = label_width + 10
        track_width = max(40, self.width() - track_left - value_width - 12)
        metrics = painter.fontMetrics()

        for index, (label, value) in enumerate(self._items):
            y = top + index * row_height
            painter.setPen(QColor(Colors.TEXT_SECONDARY))
            painter.drawText(
                QRectF(0, y, label_width, row_height),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                metrics.elidedText(label, Qt.TextElideMode.ElideRight, label_width - 4),
            )
            track = QRectF(track_left, y + row_height / 2 - 4, track_width, 8)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(Colors.BORDER_SOFT))
            painter.drawRoundedRect(track, 4, 4)
            ratio = float(value) / maximum if maximum else 0
            bar = QRectF(track.left(), track.top(), max(4, track.width() * ratio), track.height())
            painter.setBrush(QColor(self.BAR_COLORS[index % len(self.BAR_COLORS)]))
            painter.drawRoundedRect(bar, 4, 4)
            painter.setPen(QColor(Colors.TEXT))
            painter.drawText(
                QRectF(self.width() - value_width, y, value_width - 4, row_height),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                _short_money(float(value)),
            )


class CashFlowChart(QWidget):
    period_selected = Signal(str, str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._months: list[tuple[str, str, Decimal, Decimal]] = []
        self._bar_regions: list[
            tuple[QRectF, str, str, str, Decimal]
        ] = []
        self._hovered_bar: tuple[str, str] | None = None
        self.setMouseTracking(True)
        self.setMinimumHeight(210)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def sizeHint(self) -> QSize:
        return QSize(900, 225)

    def set_data(
        self,
        months: list[tuple[str, str, Decimal, Decimal]],
    ) -> None:
        self._months = months
        self._bar_regions.clear()
        self._hovered_bar = None
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font())
        self._bar_regions.clear()
        if not self._months:
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Cash flow appears after income or expenses are recorded",
            )
            return

        plot = QRectF(50, 28, max(80, self.width() - 64), max(70, self.height() - 62))
        maximum = max(
            [float(income) for _key, _label, income, _expense in self._months]
            + [float(expense) for _key, _label, _income, expense in self._months]
            + [1.0]
        )
        painter.setPen(QColor(Colors.TEXT_SECONDARY))
        painter.setBrush(QColor(Colors.POSITIVE))
        painter.drawRect(QRectF(plot.left(), 2, 8, 8))
        painter.drawText(QRectF(plot.left() + 14, 0, 60, 14), "Income")
        painter.setBrush(QColor(Colors.NEGATIVE))
        painter.drawRect(QRectF(plot.left() + 82, 2, 8, 8))
        painter.drawText(QRectF(plot.left() + 96, 0, 70, 14), "Expenses")

        painter.setFont(QFont(self.font().family(), 8))
        for index in range(4):
            ratio = index / 3
            y = plot.top() + ratio * plot.height()
            painter.setPen(QPen(QColor(Colors.BORDER_SOFT), 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(
                QRectF(0, y - 9, 43, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                _short_money(maximum * (1 - ratio)),
            )

        group_width = plot.width() / len(self._months)
        bar_width = min(22, max(8, group_width * 0.24))
        for index, (month_key, month_label, income, expense) in enumerate(self._months):
            center = plot.left() + group_width * (index + 0.5)
            for kind, value, color, offset in (
                ("income", income, Colors.POSITIVE, -bar_width - 2),
                ("expense", expense, Colors.NEGATIVE, 2),
            ):
                numeric_value = float(value)
                height = numeric_value / maximum * plot.height()
                if numeric_value > 0:
                    height = max(3, height)
                rect = QRectF(center + offset, plot.bottom() - height, bar_width, height)
                painter.setPen(Qt.PenStyle.NoPen)
                fill = QColor(color)
                if self._hovered_bar == (month_key, kind):
                    fill = fill.lighter(112)
                painter.setBrush(fill)
                painter.drawRoundedRect(rect, 3, 3)
                if numeric_value > 0:
                    self._bar_regions.append(
                        (rect.adjusted(-2, -3, 2, 3), month_key, kind, month_label, value)
                    )
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(
                QRectF(center - group_width / 2, plot.bottom() + 7, group_width, 18),
                Qt.AlignmentFlag.AlignCenter,
                month_label,
            )

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        hit = self._bar_at(event.position())
        hovered = (hit[1], hit[2]) if hit else None
        if hovered != self._hovered_bar:
            self._hovered_bar = hovered
            self.update()
        if hit:
            _rect, month_key, kind, _label, value = hit
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            try:
                month = date.fromisoformat(f"{month_key}-01").strftime("%B %Y")
            except ValueError:
                month = month_key
            title = "Income" if kind == "income" else "Expenses"
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{month}\n{title}: {format_money(value)}\nClick to view transactions",
                self,
            )
        else:
            self.unsetCursor()
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._bar_at(event.position())
            if hit:
                self.period_selected.emit(hit[1], hit[2])
                event.accept()
                return
        super().mousePressEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered_bar = None
        self.unsetCursor()
        QToolTip.hideText()
        self.update()
        super().leaveEvent(event)

    def _bar_at(
        self,
        position: QPointF,
    ) -> tuple[QRectF, str, str, str, Decimal] | None:
        for region in reversed(self._bar_regions):
            if region[0].contains(position):
                return region
        return None


class NetWorthChart(QWidget):
    """Three-series chart for assets, liabilities, and net worth history."""

    SERIES = (
        ("Assets", 1, "#4778b8", 2.2),
        ("Liabilities", 2, Colors.NEGATIVE, 2.2),
        ("Net worth", 3, Colors.PRIMARY, 3.0),
    )

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._points: list[tuple[str, Decimal, Decimal, Decimal]] = []
        self._empty_text = "Net worth history appears after a snapshot is recorded"
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def sizeHint(self) -> QSize:
        return QSize(900, 270)

    def set_data(self, points: list[object], empty_text: str | None = None) -> None:
        normalized: list[tuple[str, Decimal, Decimal, Decimal]] = []
        for point in points:
            if all(
                hasattr(point, attribute)
                for attribute in ("date", "assets", "liabilities", "net_worth")
            ):
                point_date = getattr(point, "date")
                assets = getattr(point, "assets")
                liabilities = getattr(point, "liabilities")
                net_worth = getattr(point, "net_worth")
            else:
                try:
                    point_date, assets, liabilities, net_worth = point  # type: ignore[misc]
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        "Net worth points require date, assets, liabilities, and net worth"
                    ) from exc
            normalized.append(
                (
                    str(point_date),
                    to_decimal(assets),
                    to_decimal(liabilities),
                    to_decimal(net_worth),
                )
            )
        self._points = sorted(normalized, key=lambda point: point[0])
        if empty_text:
            self._empty_text = empty_text
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font())
        if not self._points:
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self._empty_text,
            )
            return

        plot = QRectF(64, 38, max(40, self.width() - 82), max(70, self.height() - 76))
        all_values = [
            value
            for point in self._points
            for value in (point[1], point[2], point[3])
        ]
        zero = Decimal("0")
        minimum = min(all_values + [zero])
        maximum = max(all_values + [zero])
        span = maximum - minimum
        magnitude = max(abs(minimum), abs(maximum), Decimal("1"))
        padding = max(span * Decimal("0.10"), magnitude * Decimal("0.025"), Decimal("1"))
        lower = min(zero, minimum - padding)
        upper = max(zero, maximum + padding)
        if upper <= lower:
            upper = lower + Decimal("1")

        small_font = QFont(self.font())
        small_font.setPointSize(8)
        painter.setFont(small_font)
        label_color = QColor(Colors.TEXT_MUTED)
        grid_pen = QPen(QColor(Colors.BORDER_SOFT), 1)
        for index in range(5):
            ratio = Decimal(index) / Decimal("4")
            y = plot.top() + float(ratio) * plot.height()
            axis_value = upper - ratio * (upper - lower)
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(label_color)
            painter.drawText(
                QRectF(0, y - 9, 56, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                self._short_money(axis_value),
            )

        if lower < zero < upper:
            zero_ratio = (zero - lower) / (upper - lower)
            zero_y = plot.bottom() - float(zero_ratio) * plot.height()
            painter.setPen(QPen(QColor(Colors.BORDER), 1.4))
            painter.drawLine(QPointF(plot.left(), zero_y), QPointF(plot.right(), zero_y))

        self._draw_legend(painter, plot)

        def positions(values: list[Decimal]) -> list[QPointF]:
            result: list[QPointF] = []
            for index, value in enumerate(values):
                x = (
                    plot.center().x()
                    if len(values) == 1
                    else plot.left() + index / (len(values) - 1) * plot.width()
                )
                value_ratio = (value - lower) / (upper - lower)
                y = plot.bottom() - float(value_ratio) * plot.height()
                result.append(QPointF(x, y))
            return result

        def draw_series(column: int, color: str, width: float) -> None:
            values = [point[column] for point in self._points]
            series_positions = positions(values)
            painter.setPen(QPen(QColor(color), width))
            if len(series_positions) == 1:
                point = series_positions[0]
                painter.drawLine(
                    QPointF(max(plot.left(), point.x() - 20), point.y()),
                    QPointF(min(plot.right(), point.x() + 20), point.y()),
                )
            else:
                path = QPainterPath(series_positions[0])
                for point in series_positions[1:]:
                    path.lineTo(point)
                painter.drawPath(path)
            painter.setBrush(QColor(Colors.CARD))
            painter.setPen(QPen(QColor(color), 2))
            radius = 3.5 if len(series_positions) <= 24 else 2.5
            for point in series_positions:
                painter.drawEllipse(point, radius, radius)

        # Paint the primary line last so it stays visually dominant at crossings.
        for _label, column, color, width in self.SERIES:
            draw_series(column, color, width)

        painter.setFont(small_font)
        painter.setPen(label_color)
        label_count = min(6, len(self._points))
        if len(self._points) <= label_count:
            label_indices = list(range(len(self._points)))
        else:
            label_indices = sorted(
                {
                    round(index * (len(self._points) - 1) / (label_count - 1))
                    for index in range(label_count)
                }
            )
        month_keys = [point[0][:7] for point in self._points]
        include_day = len(set(month_keys)) < len(month_keys)
        label_width = min(100.0, max(58.0, plot.width() / max(1, len(label_indices))))
        net_worth_positions = positions([point[3] for point in self._points])
        for point_index in label_indices:
            x = net_worth_positions[point_index].x()
            left = max(plot.left(), min(x - label_width / 2, plot.right() - label_width))
            painter.drawText(
                QRectF(left, plot.bottom() + 8, label_width, 18),
                Qt.AlignmentFlag.AlignCenter,
                self._period_label(self._points[point_index][0], include_day),
            )

    def _draw_legend(self, painter: QPainter, plot: QRectF) -> None:
        legend_font = QFont(self.font())
        legend_font.setPointSize(9)
        legend_font.setBold(True)
        painter.setFont(legend_font)
        slot_width = plot.width() / len(self.SERIES)
        for index, (label, _column, color, _width) in enumerate(self.SERIES):
            left = plot.left() + slot_width * index
            painter.setPen(QPen(QColor(color), 3))
            painter.drawLine(QPointF(left, 15), QPointF(left + 22, 15))
            painter.setPen(QColor(Colors.TEXT_SECONDARY))
            painter.drawText(
                QRectF(left + 29, 5, max(20, slot_width - 33), 20),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )

    @staticmethod
    def _short_money(value: Decimal) -> str:
        absolute = abs(value)
        sign = "-" if value < 0 else ""
        if absolute >= Decimal("1000000"):
            return f"{sign}\u20ac{absolute / Decimal('1000000'):.1f}m"
        if absolute >= Decimal("1000"):
            return f"{sign}\u20ac{absolute / Decimal('1000'):.1f}k"
        return f"{sign}\u20ac{absolute:.0f}"

    @staticmethod
    def _period_label(value: str, include_day: bool) -> str:
        try:
            point_date = date.fromisoformat(value)
        except ValueError:
            return value
        return point_date.strftime("%d %b" if include_day else "%b %Y")
