from app.ui.theme import Colors, Spacing


def app_stylesheet() -> str:
    return f"""
    QWidget {{
        font-family: "Segoe UI Variable", "Segoe UI";
        font-size: 13px;
        color: {Colors.TEXT};
    }}

    QMainWindow, #AppRoot, #ContentRoot, #PageCanvas, #PageContent {{
        background: {Colors.BACKGROUND};
    }}

    QScrollArea#PageScroll, QScrollArea#PageScroll > QWidget > QWidget {{
        background: transparent;
        border: none;
    }}

    #Sidebar {{
        background: {Colors.SIDEBAR};
        border: none;
    }}

    #SidebarTitle {{
        color: white;
        font-size: 16px;
        font-weight: 700;
    }}

    QLabel[role="sidebarMeta"] {{
        color: {Colors.SIDEBAR_MUTED};
        font-size: 10px;
    }}

    QPushButton#LogoButton {{
        background: {Colors.PRIMARY};
        border: 1px solid #318671;
        border-radius: 8px;
        padding: 0;
        min-height: 0;
        color: white;
        font-size: 20px;
        font-weight: 700;
    }}

    QPushButton#LogoButton:hover {{
        background: {Colors.PRIMARY_DARK};
        border-color: #55a48f;
    }}

    #SidebarStatus {{
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
    }}

    #StatusDot {{
        background: #55d6a9;
        border-radius: 4px;
    }}

    QPushButton {{
        border: 1px solid {Colors.BORDER};
        border-radius: 7px;
        padding: 9px 14px;
        background: {Colors.CARD};
        color: {Colors.TEXT};
        font-weight: 600;
        min-height: 22px;
    }}

    QPushButton:hover {{
        border-color: #b9c9c3;
        background: #f7faf8;
    }}

    QPushButton:pressed {{
        background: #edf3f0;
    }}

    QPushButton:disabled {{
        background: #f7f9f8;
        color: #aab5b1;
        border-color: #e9eeeb;
    }}

    QPushButton[variant="primary"] {{
        background: {Colors.PRIMARY};
        border-color: {Colors.PRIMARY};
        color: white;
        padding-left: 17px;
        padding-right: 17px;
    }}

    QPushButton[variant="primary"]:hover {{
        background: {Colors.PRIMARY_DARK};
        border-color: {Colors.PRIMARY_DARK};
    }}

    QPushButton[variant="soft"] {{
        background: {Colors.PRIMARY_SOFT};
        border-color: #c9e3da;
        color: {Colors.PRIMARY_DARK};
    }}

    QPushButton[variant="ghost"] {{
        background: transparent;
        border-color: transparent;
        color: {Colors.TEXT_SECONDARY};
    }}

    QPushButton[variant="ghost"]:hover {{
        background: #edf3f0;
        color: {Colors.TEXT};
    }}

    QPushButton[variant="danger"] {{
        background: #fff;
        border-color: #f1c6c3;
        color: {Colors.NEGATIVE};
    }}

    QPushButton[variant="danger"]:hover {{
        background: #fdf0ef;
        border-color: #e9aaa5;
    }}

    QPushButton[variant="hero"] {{
        background: rgba(255, 255, 255, 0.13);
        border: 1px solid rgba(255, 255, 255, 0.22);
        color: white;
        border-radius: 9px;
        padding: 7px 11px;
        min-height: 18px;
    }}

    QPushButton[variant="hero"]:hover {{
        background: rgba(255, 255, 255, 0.22);
        border-color: rgba(255, 255, 255, 0.32);
    }}

    QPushButton[variant="nav"] {{
        background: transparent;
        border: none;
        color: #a9b3c2;
        text-align: left;
        padding: 11px 12px;
        border-radius: 8px;
        font-weight: 600;
        min-height: 24px;
    }}

    QFrame[role="navItem"] {{
        background: transparent;
        border: none;
        border-radius: 7px;
    }}

    QFrame[role="navItem"]:hover {{
        background: rgba(255, 255, 255, 0.055);
    }}

    QFrame[role="navItem"][selected="true"] {{
        background: {Colors.SIDEBAR_SELECTED};
        border-left: 3px solid #67d4b2;
    }}

    QFrame[role="navItem"][selected="true"][collapsed="true"] {{
        border-left: none;
        border: 1px solid rgba(103, 212, 178, 0.45);
    }}

    QLabel[role="navLabel"] {{
        color: #a7b9b3;
        font-size: 13px;
        font-weight: 600;
    }}

    QFrame[role="navItem"]:hover QLabel[role="navLabel"],
    QFrame[role="navItem"][selected="true"] QLabel[role="navLabel"] {{
        color: white;
    }}

    QPushButton[variant="sidebarIcon"] {{
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        color: #cbd5e1;
        border-radius: 7px;
        padding: 0;
        font-size: 17px;
    }}

    QPushButton[variant="sidebarIcon"]:hover {{
        background: rgba(255, 255, 255, 0.09);
        color: white;
    }}

    QPushButton[variant="chip"] {{
        background: transparent;
        border: 1px solid transparent;
        color: {Colors.TEXT_SECONDARY};
        border-radius: 7px;
        padding: 7px 12px;
        font-weight: 600;
        min-height: 20px;
    }}

    QPushButton[variant="chip"]:hover {{
        background: #edf3f0;
    }}

    QPushButton[variant="chip"][selected="true"] {{
        background: {Colors.PRIMARY_SOFT};
        border-color: #c9e3da;
        color: {Colors.PRIMARY_DARK};
    }}

    QFrame[role="card"], QFrame[role="metricCard"], QFrame[role="forecastCard"] {{
        background: {Colors.CARD};
        border: 1px solid {Colors.BORDER};
        border-radius: {Spacing.RADIUS}px;
    }}

    QFrame[role="metricCard"] {{
        border-top: 3px solid #d9e4e0;
    }}

    QFrame[role="metricCard"][tone="positive"] {{
        border-top-color: {Colors.POSITIVE};
    }}

    QFrame[role="metricCard"][tone="negative"] {{
        border-top-color: {Colors.NEGATIVE};
    }}

    QWidget[role="forecastMetric"] {{
        border-left: 1px solid {Colors.BORDER_SOFT};
    }}

    QWidget[role="forecastStatus"][tone="positive"] {{
        border-left: 4px solid {Colors.POSITIVE};
    }}

    QWidget[role="forecastStatus"][tone="negative"] {{
        border-left: 4px solid {Colors.NEGATIVE};
    }}

    QWidget[role="forecastStatus"][tone="neutral"] {{
        border-left: 4px solid {Colors.BORDER};
    }}

    QLabel[role="forecastMessage"] {{
        color: {Colors.TEXT};
        font-size: 17px;
        font-weight: 700;
    }}

    QFrame[role="heroCard"] {{
        background: #1b493d;
        border: 1px solid #285e50;
        border-radius: {Spacing.RADIUS}px;
    }}

    QFrame[role="toolbar"] {{
        background: {Colors.HEADER};
        border: none;
        border-radius: 7px;
    }}

    QFrame[role="quickActions"] {{
        background: transparent;
        border: none;
    }}

    QFrame[role="scopeBar"] {{
        background: #edf3f0;
        border: 1px solid #d8e4df;
        border-radius: {Spacing.RADIUS}px;
    }}

    QFrame[role="accountDetailCard"] {{
        background: #f8fbf9;
        border: 1px solid #d5e3de;
        border-radius: {Spacing.RADIUS}px;
    }}

    QLabel[role="detailTitle"] {{
        color: {Colors.TEXT};
        font-size: 21px;
        font-weight: 700;
    }}

    QLabel[role="detailBalance"] {{
        color: {Colors.TEXT};
        font-size: 28px;
        font-weight: 700;
    }}

    QFrame[role="iconTile"] {{
        background: {Colors.PRIMARY_SOFT};
        border: none;
        border-radius: 8px;
    }}

    QLabel[role="eyebrow"] {{
        color: {Colors.PRIMARY};
        font-size: 10px;
        font-weight: 700;
    }}

    QLabel[role="pageTitle"] {{
        font-size: 28px;
        font-weight: 700;
        color: {Colors.TEXT};
    }}

    QLabel[role="subtitle"] {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 13px;
    }}

    QLabel[role="sectionTitle"] {{
        font-size: 15px;
        font-weight: 700;
        color: {Colors.TEXT};
    }}

    QLabel[role="sectionSubtitle"] {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 12px;
    }}

    QLabel[role="metricLabel"] {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 12px;
        font-weight: 700;
    }}

    QLabel[role="metricValue"] {{
        font-size: 25px;
        font-weight: 700;
        color: {Colors.TEXT};
    }}

    QLabel[role="heroLabel"] {{
        color: rgba(222, 246, 238, 0.72);
        font-size: 11px;
        font-weight: 700;
    }}

    QLabel[role="heroValue"] {{
        color: white;
        font-size: 38px;
        font-weight: 700;
    }}

    QLabel[role="heroHelper"] {{
        color: rgba(222, 246, 238, 0.74);
        font-size: 12px;
    }}

    QLabel[role="icon"] {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 15px;
    }}

    QLabel[tone="positive"] {{ color: {Colors.POSITIVE}; }}
    QLabel[tone="negative"] {{ color: {Colors.NEGATIVE}; }}

    QLabel[role="helper"], QLabel[role="emptySubtitle"] {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 12px;
    }}

    QLabel[role="count"] {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 11px;
        font-weight: 600;
    }}

    QLabel[role="emptyTitle"] {{
        color: {Colors.TEXT};
        font-weight: 700;
        font-size: 16px;
    }}

    QLabel[role="badge"] {{
        border-radius: 8px;
        padding: 3px 9px;
        font-size: 11px;
        font-weight: 600;
    }}

    QLabel[role="badge"][tone="neutral"] {{
        background: {Colors.NEUTRAL_BADGE_BG}; color: {Colors.NEUTRAL_BADGE_TEXT};
    }}
    QLabel[role="badge"][tone="positive"] {{
        background: {Colors.POSITIVE_BADGE_BG}; color: {Colors.POSITIVE_BADGE_TEXT};
    }}
    QLabel[role="badge"][tone="negative"] {{
        background: {Colors.NEGATIVE_BADGE_BG}; color: {Colors.NEGATIVE_BADGE_TEXT};
    }}
    QLabel[role="badge"][tone="info"] {{
        background: {Colors.INFO_BADGE_BG}; color: {Colors.INFO_BADGE_TEXT};
    }}
    QLabel[role="badge"][tone="muted"] {{
        background: {Colors.MUTED_BADGE_BG}; color: {Colors.MUTED_BADGE_TEXT};
    }}

    QLabel[role="mono"] {{
        background: {Colors.HEADER};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 11px 12px;
        font-family: Consolas;
        color: #344054;
    }}

    QLineEdit[role="mono"] {{
        background: {Colors.HEADER};
        border: 1px solid {Colors.BORDER};
        font-family: Consolas;
        color: #344054;
    }}

    QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {{
        background: white;
        border: 1px solid #cbd7d2;
        border-radius: 7px;
        padding: 9px 11px;
        min-height: 24px;
        selection-background-color: {Colors.PRIMARY};
    }}

    QLineEdit:hover, QComboBox:hover, QDateEdit:hover,
    QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: #91aaa1; }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 2px solid #58a78f;
        padding: 8px 10px;
    }}

    QComboBox::drop-down, QDateEdit::drop-down {{
        border: none;
        width: 34px;
    }}

    QDateEdit::down-arrow {{
        image: none;
        width: 0;
        height: 0;
    }}

    QCalendarWidget#BookingCalendar {{
        background: white;
        border: 1px solid {Colors.BORDER};
    }}

    QCalendarWidget#BookingCalendar QWidget#qt_calendar_navigationbar {{
        background: {Colors.PRIMARY_SOFT};
        border-bottom: 1px solid {Colors.BORDER_SOFT};
        min-height: 38px;
    }}

    QCalendarWidget#BookingCalendar QToolButton {{
        background: transparent;
        border: none;
        border-radius: 6px;
        color: {Colors.TEXT};
        font-weight: 600;
        min-height: 28px;
        padding: 3px 8px;
    }}

    QCalendarWidget#BookingCalendar QToolButton:hover {{
        background: rgba(25, 127, 101, 0.10);
    }}

    QCalendarWidget#BookingCalendar QSpinBox {{
        background: white;
        border: 1px solid {Colors.BORDER};
        border-radius: 6px;
        padding: 4px 8px;
    }}

    QCalendarWidget#BookingCalendar QAbstractItemView {{
        background: white;
        alternate-background-color: white;
        color: {Colors.TEXT};
        selection-background-color: {Colors.PRIMARY};
        selection-color: white;
        outline: none;
        padding: 0;
    }}

    QCalendarWidget#BookingCalendar QTableView::item {{
        border: none;
        padding: 0;
    }}

    QCalendarWidget#BookingCalendar QHeaderView::section {{
        background: white;
        border: none;
        padding: 0;
        font-size: 11px;
    }}

    QCheckBox {{ spacing: 8px; color: {Colors.TEXT_SECONDARY}; }}
    QCheckBox::indicator {{
        width: 17px; height: 17px; border: 1px solid #bdcbc5; border-radius: 4px; background: white;
    }}
    QCheckBox::indicator:checked {{ background: {Colors.PRIMARY}; border-color: {Colors.PRIMARY}; }}

    QTableWidget, QTableView, QTreeWidget {{
        background: white;
        border: none;
        gridline-color: transparent;
        alternate-background-color: {Colors.ROW_ALT};
        selection-background-color: {Colors.PRIMARY_SOFT};
        selection-color: {Colors.TEXT};
        outline: 0;
    }}

    QTableWidget::item:selected, QTableView::item:selected, QTreeWidget::item:selected {{
        background: {Colors.PRIMARY_SOFT};
        color: {Colors.TEXT};
    }}

    QHeaderView::section {{
        background: {Colors.HEADER};
        color: {Colors.TEXT_SECONDARY};
        border: none;
        border-bottom: 1px solid {Colors.BORDER};
        padding: 12px 12px;
        font-size: 11px;
        font-weight: 700;
    }}

    QTableWidget::item, QTableView::item, QTreeWidget::item {{
        padding: 9px 12px;
        border-bottom: 1px solid {Colors.BORDER_SOFT};
    }}

    QTableWidget::item:focus, QTableView::item:focus, QTreeWidget::item:focus {{ outline: none; }}

    QDialog {{ background: {Colors.BACKGROUND}; }}
    QDialog[role="sheet"] {{ background: {Colors.BACKGROUND}; }}
    QDialog QLabel[role="dialogTitle"] {{
        font-size: 21px;
        font-weight: 700;
        color: {Colors.TEXT};
    }}

    QFrame[role="dialogIcon"] {{
        background: {Colors.PRIMARY_SOFT};
        border: 1px solid #cae3da;
        border-radius: 8px;
    }}

    QFrame[role="formSurface"] {{
        background: white;
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
    }}

    QFrame[role="toast"] {{
        background: #14221e;
        border: 1px solid #2d463e;
        border-radius: 8px;
    }}

    QFrame[role="toastDot"] {{
        background: #55d6a9;
        border: none;
        border-radius: 4px;
    }}

    QLabel[role="toastText"] {{
        color: white;
        font-size: 12px;
        font-weight: 600;
    }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 3px; }}
    QScrollBar::handle:vertical {{ background: #c8d3cf; min-height: 32px; border-radius: 4px; }}
    QScrollBar::handle:vertical:hover {{ background: #9fb1aa; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 3px; }}
    QScrollBar::handle:horizontal {{ background: #c8d3cf; min-width: 32px; border-radius: 4px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    QToolTip {{
        background: #14221e;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 6px 8px;
    }}
    """
