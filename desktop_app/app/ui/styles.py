from app.ui.theme import Colors, Spacing


def app_stylesheet() -> str:
    return f"""
    QWidget {{
        font-family: "Inter Variable", "Segoe UI Variable", "Segoe UI";
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
        border: 1px solid {Colors.PRIMARY};
        border-radius: 8px;
        padding: 0;
        min-height: 0;
        color: white;
        font-size: 20px;
        font-weight: 700;
    }}

    QPushButton#LogoButton:hover {{
        background: {Colors.PRIMARY_DARK};
        border-color: #7290a0;
    }}

    #SidebarStatus {{
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
    }}

    #StatusDot {{
        background: #76b89d;
        border-radius: 4px;
    }}

    QPushButton {{
        border: 1px solid {Colors.BORDER};
        border-radius: 9px;
        padding: 9px 14px;
        background: {Colors.CARD};
        color: {Colors.TEXT};
        font-weight: 600;
        min-height: 22px;
    }}

    QPushButton:hover {{
        border-color: #c7cdca;
        background: #f7f8f6;
    }}

    QPushButton:pressed {{
        background: #eef0ee;
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
        border-color: #d5e1e7;
        color: {Colors.PRIMARY_DARK};
    }}

    QPushButton[variant="ghost"] {{
        background: transparent;
        border-color: transparent;
        color: {Colors.TEXT_SECONDARY};
    }}

    QPushButton[variant="ghost"]:hover {{
        background: #f0f2f0;
        color: {Colors.TEXT};
    }}

    QPushButton[variant="quiet"] {{
        background: transparent;
        border-color: transparent;
        color: {Colors.TEXT_SECONDARY};
    }}

    QPushButton[variant="quiet"]:hover {{
        background: #f0f2f0;
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
        border-radius: 10px;
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
        color: #aeb4b1;
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
        border-left: 3px solid #8faebd;
    }}

    QFrame[role="navItem"][selected="true"][collapsed="true"] {{
        border-left: none;
        border: 1px solid rgba(143, 174, 189, 0.55);
    }}

    QLabel[role="navLabel"] {{
        color: #abb1ae;
        font-size: 14px;
        font-weight: 650;
    }}

    QLabel[role="navDescription"] {{
        color: #737f80;
        font-size: 10px;
        font-weight: 450;
    }}

    QFrame[role="navItem"]:hover QLabel[role="navLabel"],
    QFrame[role="navItem"][selected="true"] QLabel[role="navLabel"] {{
        color: white;
    }}

    QFrame[role="navItem"][selected="true"] QLabel[role="navDescription"] {{
        color: #9ba8a9;
    }}

    #WorkspaceBar {{
        background: rgba(246, 244, 239, 0.96);
        border: none;
        border-bottom: 1px solid {Colors.BORDER};
    }}

    QLabel[role="workspaceLabel"] {{
        color: {Colors.TEXT_MUTED};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
    }}

    QPushButton[variant="workspaceTab"] {{
        background: transparent;
        border: none;
        border-radius: 7px;
        color: {Colors.TEXT_SECONDARY};
        font-size: 12px;
        font-weight: 600;
        min-height: 20px;
        padding: 7px 11px;
    }}

    QPushButton[variant="workspaceTab"]:hover {{
        background: rgba(54, 93, 114, 0.06);
        color: {Colors.TEXT};
    }}

    QPushButton[variant="workspaceTab"][selected="true"] {{
        background: {Colors.CARD};
        color: {Colors.PRIMARY_DARK};
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
        background: #f0f2f0;
    }}

    QPushButton[variant="chip"][selected="true"] {{
        background: {Colors.PRIMARY_SOFT};
        border-color: #d5e1e7;
        color: {Colors.PRIMARY_DARK};
    }}

    QFrame[role="card"], QFrame[role="metricCard"], QFrame[role="forecastCard"] {{
        background: {Colors.CARD};
        border: none;
        border-radius: {Spacing.RADIUS}px;
    }}

    QFrame[role="metricCard"] {{
        border: none;
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
        background: {Colors.CARD};
        border: none;
        border-radius: 20px;
    }}

    QFrame[role="monthPulse"] {{
        background: {Colors.CARD};
        border: none;
        border-radius: 16px;
    }}

    QWidget[role="pulseRow"] {{
        border-bottom: 1px solid {Colors.BORDER_SOFT};
    }}

    QLabel[role="pulseValue"] {{
        color: {Colors.TEXT};
        font-size: 17px;
        font-weight: 700;
    }}

    QFrame[role="workflowRail"] {{
        background: #f3f4f2;
        border: 1px solid {Colors.BORDER};
        border-radius: 11px;
    }}

    QLabel[role="workflowStep"] {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 12px;
        font-weight: 700;
        padding: 8px 10px;
    }}

    QLabel[role="workflowStep"][active="true"] {{
        color: {Colors.PRIMARY_DARK};
        background: {Colors.PRIMARY_SOFT};
        border-radius: 8px;
    }}

    QLabel[role="statementSource"] {{
        color: {Colors.TEXT_SECONDARY};
        background: #f5f6f4;
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 7px 10px;
        font-size: 11px;
    }}

    QFrame[role="importPreviewCard"] {{
        background: {Colors.CARD};
        border: none;
        border-radius: 14px;
    }}

    QFrame[role="importSummary"] {{
        background: #f5f6f4;
        border: none;
        border-radius: 10px;
    }}

    QFrame[role="toolbar"] {{
        background: transparent;
        border: none;
        border-radius: 0;
    }}

    QFrame[role="quickActions"] {{
        background: {Colors.CARD};
        border: none;
        border-radius: 14px;
    }}

    QFrame[role="scopeBar"] {{
        background: {Colors.CARD};
        border: none;
        border-radius: {Spacing.RADIUS}px;
    }}

    QFrame[role="accountDetailCard"] {{
        background: {Colors.CARD};
        border: none;
        border-radius: {Spacing.RADIUS}px;
    }}

    QFrame[role="workspace"] {{
        background: {Colors.CARD};
        border: none;
        border-radius: {Spacing.RADIUS}px;
    }}

    QFrame[role="metricBoard"] {{
        background: {Colors.CARD};
        border: none;
        border-radius: 16px;
    }}

    QFrame[role="metricCell"] {{
        background: transparent;
        border: none;
        border-radius: 0;
    }}

    QFrame[role="metricCell"][divider="true"] {{
        border-right: 1px solid {Colors.BORDER};
    }}

    QLabel[role="detailTitle"] {{
        color: {Colors.TEXT};
        font-size: 21px;
        font-weight: 700;
    }}

    QLabel[role="tablePrimary"] {{
        color: {Colors.TEXT};
        font-size: 11px;
        font-weight: 600;
    }}

    QLabel[role="tableSecondary"] {{
        color: {Colors.TEXT_MUTED};
        font-size: 10px;
    }}

    QLabel[role="detailBalance"] {{
        font-family: "Space Grotesk", "Inter Variable";
        color: {Colors.TEXT};
        font-size: 28px;
        font-weight: 600;
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
        font-size: 30px;
        font-weight: 600;
        color: {Colors.TEXT};
    }}

    QLabel[role="subtitle"] {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 13px;
    }}

    QLabel[role="sectionTitle"] {{
        font-size: 16px;
        font-weight: 600;
        color: {Colors.TEXT};
    }}

    QLabel[role="sectionSubtitle"] {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 12px;
    }}

    QLabel[role="metricLabel"] {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 11px;
        font-weight: 500;
    }}

    QLabel[role="metricValue"] {{
        font-family: "Space Grotesk", "Inter Variable";
        font-size: 24px;
        font-weight: 600;
        color: {Colors.TEXT};
    }}

    QLabel[role="heroLabel"] {{
        color: {Colors.TEXT_MUTED};
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1px;
    }}

    QLabel[role="heroValue"] {{
        font-family: "Space Grotesk", "Inter Variable";
        color: {Colors.TEXT};
        font-size: 50px;
        font-weight: 600;
    }}

    QLabel[role="heroSnapshotValue"] {{
        font-family: "Space Grotesk", "Inter Variable";
        color: {Colors.TEXT};
        font-size: 21px;
        font-weight: 600;
    }}

    QLabel[role="heroSnapshotLabel"] {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 11px;
    }}

    QLabel[role="heroHelper"] {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 12px;
    }}

    QLabel[role="heroChange"] {{
        background: {Colors.POSITIVE_BADGE_BG};
        border: none;
        border-radius: 12px;
        color: {Colors.POSITIVE};
        font-size: 12px;
        font-weight: 600;
        padding: 5px 10px;
    }}

    QLabel[role="heroChange"][tone="negative"] {{
        background: {Colors.NEGATIVE_BADGE_BG};
        color: {Colors.NEGATIVE};
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
        font-weight: 600;
        font-size: 16px;
    }}

    QFrame[role="emptyIcon"] {{
        background: {Colors.HEADER};
        border: none;
        border-radius: 11px;
    }}

    QLabel[role="badge"] {{
        border-radius: 12px;
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
        border: 1px solid #d5d9d6;
        border-radius: 8px;
        padding: 10px 11px;
        min-height: 24px;
        selection-background-color: {Colors.PRIMARY};
    }}

    QLineEdit:hover, QComboBox:hover, QDateEdit:hover,
    QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: #aeb9bd; }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 2px solid {Colors.PRIMARY};
        padding: 9px 10px;
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
        background: {Colors.CARD};
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

    QFrame[role="passwordField"] {{
        background: white;
        border: 1px solid rgba(24, 32, 35, 0.08);
        border-radius: 14px;
    }}

    QFrame[role="passwordField"]:hover {{
        border-color: rgba(54, 93, 114, 0.35);
    }}

    QFrame[role="passwordField"][focused="true"] {{
        border: 2px solid {Colors.PRIMARY};
    }}

    QLineEdit[role="passwordInput"] {{
        background: transparent;
        border: none;
        border-radius: 0;
        padding: 0;
        min-height: 40px;
        font-size: 16px;
        font-weight: 650;
        letter-spacing: 0.3px;
        selection-background-color: {Colors.PRIMARY};
    }}

    QLineEdit[role="passwordInput"]:hover,
    QLineEdit[role="passwordInput"]:focus {{
        border: none;
        padding: 0;
    }}

    QToolButton[role="passwordToggle"] {{
        background: transparent;
        border: none;
        border-radius: 8px;
        padding: 5px;
    }}

    QToolButton[role="passwordToggle"]:hover {{
        background: {Colors.PRIMARY_SOFT};
    }}

    QToolButton[role="passwordToggle"]:focus {{
        border: 2px solid {Colors.TEXT};
        padding: 3px;
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

    QLabel[role="homeEyebrow"] {{
        color: {Colors.TEXT_MUTED};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.1px;
    }}

    QLabel[role="homeSectionTitle"] {{
        color: {Colors.TEXT};
        font-size: 20px;
        font-weight: 650;
    }}

    QFrame[role="decisionBand"] {{
        background: {Colors.PRIMARY_DARK};
        border: none;
        border-radius: 18px;
    }}

    QFrame[role="decisionBand"][tone="urgent"] {{
        background: #2f505f;
    }}

    QFrame[role="decisionIcon"] {{
        background: rgba(255, 255, 255, 0.14);
        border: none;
        border-radius: 12px;
    }}

    QLabel[role="decisionEyebrow"] {{
        color: rgba(255, 255, 255, 0.66);
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.8px;
    }}

    QLabel[role="decisionTitle"] {{
        color: white;
        font-size: 18px;
        font-weight: 650;
    }}

    QLabel[role="decisionDetail"] {{
        color: rgba(255, 255, 255, 0.70);
        font-size: 11px;
    }}

    QPushButton[variant="decision"] {{
        background: white;
        border: none;
        border-radius: 10px;
        color: {Colors.PRIMARY_DARK};
        padding: 10px 17px;
    }}

    QPushButton[variant="decision"]:hover {{
        background: #f3f4f2;
    }}

    QFrame[role="homeRow"] {{
        background: transparent;
        border: none;
        border-bottom: 1px solid {Colors.BORDER};
    }}

    QLabel[role="homeRowTitle"] {{
        color: {Colors.TEXT};
        font-size: 13px;
        font-weight: 600;
    }}

    QLabel[role="homeRowDetail"], QLabel[role="homeDate"] {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 11px;
    }}

    QLabel[role="homeAmount"] {{
        color: {Colors.TEXT};
        font-family: "Space Grotesk", "Inter Variable";
        font-size: 13px;
        font-weight: 600;
    }}

    QLabel[role="homeAmount"][tone="positive"] {{
        color: {Colors.POSITIVE};
    }}

    QLabel[role="homeAmount"][tone="negative"] {{
        color: {Colors.NEGATIVE};
    }}

    QFrame[role="attentionDot"] {{
        background: {Colors.WARNING};
        border: none;
        border-radius: 4px;
        margin-top: 4px;
    }}

    QFrame[role="attentionDot"][tone="urgent"] {{
        background: {Colors.NEGATIVE};
    }}

    QPushButton[variant="text"] {{
        background: transparent;
        border: none;
        color: {Colors.PRIMARY_DARK};
        font-size: 11px;
        padding: 5px 3px;
    }}

    QPushButton[variant="text"]:hover {{
        background: transparent;
        color: {Colors.PRIMARY};
        text-decoration: underline;
    }}

    QPushButton[variant="rowLink"] {{
        background: transparent;
        border: none;
        color: {Colors.TEXT};
        font-size: 13px;
        font-weight: 600;
        padding: 4px 0;
        text-align: left;
    }}

    QPushButton[variant="rowLink"]:hover {{
        background: transparent;
        color: {Colors.PRIMARY_DARK};
    }}

    QFrame[role="safeSpendCard"], QFrame[role="forecastHero"],
    QFrame[role="positionHero"] {{
        background: {Colors.CARD};
        border: none;
        border-radius: 18px;
    }}

    QFrame[role="forecastHero"][tone="positive"] {{
        border-left: 4px solid {Colors.POSITIVE};
    }}

    QFrame[role="forecastHero"][tone="negative"] {{
        border-left: 4px solid {Colors.NEGATIVE};
    }}

    QFrame[role="forecastHero"][tone="neutral"] {{
        border-left: 4px solid {Colors.BORDER};
    }}

    QLabel[role="safeSpendTitle"] {{
        color: {Colors.TEXT};
        font-family: "Space Grotesk", "Inter Variable";
        font-size: 27px;
        font-weight: 600;
    }}

    QLabel[role="safeSupportValue"], QLabel[role="positionFact"] {{
        color: {Colors.TEXT};
        font-family: "Space Grotesk", "Inter Variable";
        font-size: 20px;
        font-weight: 600;
    }}

    QLabel[role="positionFact"][tone="negative"] {{
        color: {Colors.NEGATIVE};
    }}

    QLabel[role="positionValue"] {{
        color: {Colors.TEXT};
        font-family: "Space Grotesk", "Inter Variable";
        font-size: 48px;
        font-weight: 600;
    }}

    QLabel[role="forecastHeroTitle"] {{
        color: {Colors.TEXT};
        font-size: 21px;
        font-weight: 650;
    }}

    QLabel[role="forecastHeroValue"] {{
        color: {Colors.TEXT};
        font-family: "Space Grotesk", "Inter Variable";
        font-size: 36px;
        font-weight: 600;
    }}

    QFrame[role="softDivider"] {{
        color: {Colors.BORDER};
        background: {Colors.BORDER};
        border: none;
        max-height: 1px;
    }}

    QFrame[role="honestNotice"] {{
        background: rgba(54, 93, 114, 0.05);
        border: 1px solid rgba(54, 93, 114, 0.10);
        border-radius: 12px;
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
