from __future__ import annotations

import sqlite3
from datetime import datetime
from decimal import Decimal

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.home_service import HomeAction, HomeBrief, HomeService, UpcomingDecision
from app.ui.components import FittedLabel, apply_soft_shadow, page_layout, primary_button
from app.ui.icons import LineIcon
from app.ui.theme import Colors
from app.ui.workspace import WorkspaceRoute
from app.utils.dates import format_display_date
from app.utils.money import format_money


class HomePage(QWidget):
    route_requested = Signal(object)

    def __init__(
        self,
        db: sqlite3.Connection,
        *,
        on_add_transaction=None,
    ):
        super().__init__()
        self.service = HomeService(db)
        self.on_add_transaction = on_add_transaction or (lambda: None)
        self._brief: HomeBrief | None = None

        add_transaction = primary_button("Add transaction", "plus")
        add_transaction.clicked.connect(self.on_add_transaction)
        layout = page_layout(
            self,
            self._greeting(),
            "Loading what matters most…",
            add_transaction,
        )
        layout.setSpacing(28)
        self.eyebrow = QLabel()
        self.eyebrow.setProperty("role", "homeEyebrow")
        layout.insertWidget(0, self.eyebrow)
        self.summary_label = self._header_subtitle()

        self.primary_band = self._build_primary_band()
        layout.addWidget(self.primary_band)

        self.content_grid = QGridLayout()
        self.content_grid.setContentsMargins(0, 0, 0, 0)
        self.content_grid.setHorizontalSpacing(42)
        self.content_grid.setVerticalSpacing(34)

        self.attention_section, self.attention_layout = self._section(
            "Needs attention"
        )
        self.upcoming_section, self.upcoming_layout = self._section(
            "Upcoming decisions"
        )
        self.safe_card = self._build_safe_card()
        self.recent_section, self.recent_layout = self._section("Recent activity")

        layout.addLayout(self.content_grid)
        layout.addStretch()
        self._layout_columns()

    def _header_subtitle(self) -> QLabel:
        labels = self.findChildren(QLabel)
        for label in labels:
            if label.property("role") == "subtitle":
                return label
        fallback = QLabel()
        fallback.setProperty("role", "subtitle")
        return fallback

    def _build_primary_band(self) -> QFrame:
        band = QFrame()
        band.setProperty("role", "decisionBand")
        band.setMinimumHeight(118)
        band.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        apply_soft_shadow(band, blur_radius=30, y_offset=7, alpha=22)
        layout = QHBoxLayout(band)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(18)

        icon_tile = QFrame()
        icon_tile.setProperty("role", "decisionIcon")
        icon_tile.setFixedSize(50, 50)
        icon_layout = QHBoxLayout(icon_tile)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.addWidget(
            LineIcon("transactions", "#ffffff", 22),
            0,
            Qt.AlignmentFlag.AlignCenter,
        )

        copy = QWidget()
        copy_layout = QVBoxLayout(copy)
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(4)
        eyebrow = QLabel("SINGLE MOST USEFUL ACTION")
        eyebrow.setProperty("role", "decisionEyebrow")
        self.primary_title = QLabel()
        self.primary_title.setProperty("role", "decisionTitle")
        self.primary_title.setWordWrap(True)
        self.primary_detail = QLabel()
        self.primary_detail.setProperty("role", "decisionDetail")
        self.primary_detail.setWordWrap(True)
        copy_layout.addWidget(eyebrow)
        copy_layout.addWidget(self.primary_title)
        copy_layout.addWidget(self.primary_detail)

        self.primary_button = QPushButton("Review")
        self.primary_button.setProperty("variant", "decision")
        self.primary_button.clicked.connect(self._open_primary)

        layout.addWidget(icon_tile, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(copy, 1)
        layout.addWidget(self.primary_button, 0, Qt.AlignmentFlag.AlignVCenter)
        return band

    @staticmethod
    def _section(title: str) -> tuple[QWidget, QVBoxLayout]:
        section = QWidget()
        section.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        heading = QLabel(title)
        heading.setProperty("role", "homeSectionTitle")
        layout.addWidget(heading)
        layout.addSpacing(13)
        return section, layout

    def _build_safe_card(self) -> QFrame:
        card = QFrame()
        card.setProperty("role", "safeSpendCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        apply_soft_shadow(card, blur_radius=26, y_offset=6, alpha=17)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 25, 28, 25)
        layout.setSpacing(10)

        eyebrow = QLabel("SAFE TO SPEND")
        eyebrow.setProperty("role", "homeEyebrow")
        self.safe_title = QLabel("Set up your spending position")
        self.safe_title.setProperty("role", "safeSpendTitle")
        self.safe_title.setWordWrap(True)
        self.safe_detail = QLabel(
            "Choose which accounts are spendable and how much buffer to protect."
        )
        self.safe_detail.setProperty("role", "sectionSubtitle")
        self.safe_detail.setWordWrap(True)

        rule = QFrame()
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setProperty("role", "softDivider")

        supporting = QHBoxLayout()
        supporting.setContentsMargins(0, 0, 0, 0)
        supporting.setSpacing(18)
        known_block = QVBoxLayout()
        known_label = QLabel("KNOWN LIQUID BALANCE")
        known_label.setProperty("role", "metricLabel")
        self.known_liquidity = FittedLabel(
            format_money(Decimal("0")), maximum_size=21, minimum_size=12
        )
        self.known_liquidity.setProperty("role", "safeSupportValue")
        known_block.addWidget(known_label)
        known_block.addWidget(self.known_liquidity)
        supporting.addLayout(known_block, 1)

        setup = QPushButton("Set up")
        setup.setProperty("variant", "soft")
        setup.clicked.connect(
            lambda: self.route_requested.emit(
                WorkspaceRoute("plan", "monthly", action="safe_spend_setup")
            )
        )
        supporting.addWidget(setup, 0, Qt.AlignmentFlag.AlignBottom)

        layout.addWidget(eyebrow)
        layout.addWidget(self.safe_title)
        layout.addWidget(self.safe_detail)
        layout.addSpacing(4)
        layout.addWidget(rule)
        layout.addSpacing(4)
        layout.addLayout(supporting)
        return card

    def refresh(self) -> None:
        brief = self.service.brief()
        self._brief = brief
        self.eyebrow.setText(
            f"HOME · {brief.reference_date.strftime('%A %d %B').upper()}"
        )
        self.summary_label.setText(brief.summary)
        self.primary_title.setText(brief.primary_action.title)
        self.primary_detail.setText(brief.primary_action.detail)
        self.primary_button.setText(brief.primary_action.action_label)
        self.primary_band.setProperty("tone", brief.primary_action.severity)
        self.primary_band.style().unpolish(self.primary_band)
        self.primary_band.style().polish(self.primary_band)

        self.known_liquidity.setText(format_money(brief.available_liquidity))
        self.known_liquidity.setToolTip(format_money(brief.available_liquidity))
        self._populate_attention(brief.attention_items)
        self._populate_upcoming(brief.upcoming)
        self._populate_recent(brief)

    def _populate_attention(self, items: tuple[HomeAction, ...]) -> None:
        self._clear_rows(self.attention_layout)
        if not items:
            self.attention_layout.addWidget(
                self._quiet_message(
                    "No other decisions",
                    "The most useful action is already highlighted above.",
                )
            )
            return
        for item in items:
            self.attention_layout.addWidget(self._attention_row(item))

    def _populate_upcoming(self, items: tuple[UpcomingDecision, ...]) -> None:
        self._clear_rows(self.upcoming_layout)
        if not items:
            self.upcoming_layout.addWidget(
                self._quiet_message(
                    "No dated decisions yet",
                    "Recurring income, bills, and loan payoff dates will appear here.",
                )
            )
            return
        for item in items:
            self.upcoming_layout.addWidget(self._upcoming_row(item))

    def _populate_recent(self, brief: HomeBrief) -> None:
        self._clear_rows(self.recent_layout)
        if not brief.recent_transactions:
            self.recent_layout.addWidget(
                self._quiet_message(
                    "No recent activity",
                    "Your latest income, spending, and transfers will appear here.",
                )
            )
            return
        for transaction in brief.recent_transactions:
            row = QFrame()
            row.setProperty("role", "homeRow")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 13, 0, 13)
            layout.setSpacing(12)
            copy = QVBoxLayout()
            copy.setSpacing(2)
            title = QLabel(transaction.description or "No description")
            title.setProperty("role", "homeRowTitle")
            subtitle = QLabel(format_display_date(transaction.date))
            subtitle.setProperty("role", "homeRowDetail")
            copy.addWidget(title)
            copy.addWidget(subtitle)
            amount = transaction.amount
            amount_text = format_money(amount)
            if transaction.type == "income" and amount > 0:
                amount_text = f"+{amount_text}"
            value = QLabel(amount_text)
            value.setProperty("role", "homeAmount")
            value.setProperty(
                "tone",
                "positive"
                if transaction.type in {"income", "transfer_in"}
                else "negative"
                if transaction.type in {"expense", "transfer_out"}
                else "neutral",
            )
            layout.addLayout(copy, 1)
            layout.addWidget(value, 0, Qt.AlignmentFlag.AlignVCenter)
            self.recent_layout.addWidget(row)

    def _attention_row(self, item: HomeAction) -> QFrame:
        row = QFrame()
        row.setProperty("role", "homeRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 14, 0, 14)
        layout.setSpacing(13)

        dot = QFrame()
        dot.setProperty("role", "attentionDot")
        dot.setProperty("tone", item.severity)
        dot.setFixedSize(9, 9)

        copy = QVBoxLayout()
        copy.setSpacing(3)
        title = QLabel(item.title)
        title.setProperty("role", "homeRowTitle")
        title.setWordWrap(True)
        detail = QLabel(item.detail)
        detail.setProperty("role", "homeRowDetail")
        detail.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(detail)

        open_button = QPushButton(item.action_label)
        open_button.setProperty("variant", "text")
        open_button.clicked.connect(
            lambda _checked=False, route=item.route: self.route_requested.emit(route)
        )
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(copy, 1)
        layout.addWidget(open_button, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    def _upcoming_row(self, item: UpcomingDecision) -> QFrame:
        row = QFrame()
        row.setProperty("role", "homeRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 13, 0, 13)
        layout.setSpacing(14)
        date_label = QLabel(item.date.strftime("%d %b"))
        date_label.setProperty("role", "homeDate")
        date_label.setFixedWidth(62)
        title = QPushButton(item.title)
        title.setProperty("variant", "rowLink")
        title.clicked.connect(
            lambda _checked=False, route=item.route: self.route_requested.emit(route)
        )
        amount = QLabel(
            "Estimate needed"
            if item.amount is None
            else (
                f"+{format_money(item.amount)}"
                if item.transaction_type == "income"
                else f"−{format_money(abs(item.amount))}"
            )
        )
        amount.setProperty("role", "homeAmount")
        amount.setProperty(
            "tone", "positive" if item.transaction_type == "income" else "negative"
        )
        layout.addWidget(date_label)
        layout.addWidget(title, 1)
        layout.addWidget(amount, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    @staticmethod
    def _quiet_message(title: str, detail: str) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(3)
        title_label = QLabel(title)
        title_label.setProperty("role", "homeRowTitle")
        detail_label = QLabel(detail)
        detail_label.setProperty("role", "homeRowDetail")
        detail_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(detail_label)
        return container

    @staticmethod
    def _clear_rows(layout: QVBoxLayout) -> None:
        while layout.count() > 2:
            item = layout.takeAt(2)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _open_primary(self) -> None:
        if self._brief is not None:
            self.route_requested.emit(self._brief.primary_action.route)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_columns()

    def _layout_columns(self) -> None:
        if not hasattr(self, "content_grid"):
            return
        wide = self.width() >= 980
        if getattr(self, "_wide_layout", None) == wide:
            return
        self._wide_layout = wide
        while self.content_grid.count():
            self.content_grid.takeAt(0)
        if wide:
            self.content_grid.addWidget(self.attention_section, 0, 0)
            self.content_grid.addWidget(self.safe_card, 0, 1)
            self.content_grid.addWidget(self.upcoming_section, 1, 0)
            self.content_grid.addWidget(self.recent_section, 1, 1)
            self.content_grid.setColumnStretch(0, 5)
            self.content_grid.setColumnStretch(1, 4)
        else:
            self.content_grid.addWidget(self.attention_section, 0, 0)
            self.content_grid.addWidget(self.safe_card, 1, 0)
            self.content_grid.addWidget(self.upcoming_section, 2, 0)
            self.content_grid.addWidget(self.recent_section, 3, 0)
            self.content_grid.setColumnStretch(0, 1)
            self.content_grid.setColumnStretch(1, 0)

    @staticmethod
    def _greeting() -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "Good morning."
        if hour < 18:
            return "Good afternoon."
        return "Good evening."
