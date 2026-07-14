from app.ui.theme import Colors, Spacing


def app_stylesheet() -> str:
    return f"""
    QWidget {{
        font-family: "Segoe UI";
        font-size: 13px;
        color: {Colors.TEXT};
    }}

    QMainWindow, #AppRoot, #ContentRoot, #PageContent {{
        background: {Colors.BACKGROUND};
    }}

    QScrollArea#PageScroll, QScrollArea#PageScroll > QWidget > QWidget {{
        background: transparent;
        border: none;
    }}

    #Sidebar {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {Colors.SIDEBAR}, stop:1 {Colors.SIDEBAR_DEEP});
        border: none;
    }}

    #SidebarTitle {{
        color: white;
        font-size: 17px;
        font-weight: 700;
    }}

    #SidebarSubtitle, QLabel[role="sidebarMeta"] {{
        color: {Colors.SIDEBAR_MUTED};
        font-size: 11px;
    }}

    #LogoTile {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #6d6ee8, stop:1 #4f46c8);
        border: 1px solid #7d7ef0;
        border-radius: 12px;
    }}

    #SidebarStatus {{
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 12px;
    }}

    #StatusDot {{
        background: #32d583;
        border-radius: 4px;
    }}

    QPushButton {{
        border: 1px solid {Colors.BORDER};
        border-radius: 10px;
        padding: 9px 15px;
        background: {Colors.CARD};
        color: {Colors.TEXT};
        font-weight: 600;
        min-height: 22px;
    }}

    QPushButton:hover {{
        border-color: #cfd4dc;
        background: #f9fafb;
    }}

    QPushButton:pressed {{
        background: #f2f4f7;
    }}

    QPushButton:disabled {{
        background: #f9fafb;
        color: #b1b7c2;
        border-color: #edf0f4;
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
        border-color: #d9dcff;
        color: #4647bd;
    }}

    QPushButton[variant="ghost"] {{
        background: transparent;
        border-color: transparent;
        color: {Colors.TEXT_SECONDARY};
    }}

    QPushButton[variant="ghost"]:hover {{
        background: #f2f4f7;
        color: {Colors.TEXT};
    }}

    QPushButton[variant="danger"] {{
        background: #fff;
        border-color: #fecdca;
        color: {Colors.NEGATIVE};
    }}

    QPushButton[variant="danger"]:hover {{
        background: #fef3f2;
        border-color: #fda29b;
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
        border-radius: 10px;
        font-weight: 600;
        min-height: 24px;
    }}

    QFrame[role="navItem"] {{
        background: transparent;
        border: none;
        border-radius: 11px;
    }}

    QFrame[role="navItem"]:hover {{
        background: rgba(255, 255, 255, 0.06);
    }}

    QFrame[role="navItem"][selected="true"] {{
        background: {Colors.SIDEBAR_SELECTED};
        border-left: 3px solid #818cf8;
    }}

    QLabel[role="navLabel"] {{
        color: #aab4c3;
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
        border-radius: 9px;
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
        border-radius: 9px;
        padding: 6px 12px;
        font-weight: 600;
        min-height: 20px;
    }}

    QPushButton[variant="chip"]:hover {{
        background: #f2f4f7;
    }}

    QPushButton[variant="chip"][selected="true"] {{
        background: {Colors.PRIMARY_SOFT};
        border-color: #d9dcff;
        color: #4647bd;
    }}

    QFrame[role="card"], QFrame[role="metricCard"] {{
        background: {Colors.CARD};
        border: 1px solid {Colors.BORDER};
        border-radius: {Spacing.RADIUS}px;
    }}

    QFrame[role="heroCard"] {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #5051cf, stop:0.55 #6263df, stop:1 #7778e8);
        border: 1px solid #696ae0;
        border-radius: 18px;
    }}

    QFrame[role="toolbar"] {{
        background: #f8fafc;
        border: 1px solid {Colors.BORDER_SOFT};
        border-radius: 12px;
    }}

    QFrame[role="iconTile"] {{
        background: {Colors.PRIMARY_SOFT};
        border: none;
        border-radius: 10px;
    }}

    QLabel[role="eyebrow"] {{
        color: {Colors.PRIMARY};
        font-size: 11px;
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
        font-size: 16px;
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
        font-weight: 600;
    }}

    QLabel[role="metricValue"] {{
        font-size: 27px;
        font-weight: 700;
        color: {Colors.TEXT};
    }}

    QLabel[role="heroLabel"] {{
        color: rgba(255, 255, 255, 0.72);
        font-size: 11px;
        font-weight: 700;
    }}

    QLabel[role="heroValue"] {{
        color: white;
        font-size: 38px;
        font-weight: 700;
    }}

    QLabel[role="heroHelper"] {{
        color: rgba(255, 255, 255, 0.76);
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

    QLabel[role="emptyTitle"] {{
        color: {Colors.TEXT};
        font-weight: 700;
        font-size: 16px;
    }}

    QLabel[role="badge"] {{
        border-radius: 10px;
        padding: 2px 9px;
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
        background: #f8fafc;
        border: 1px solid {Colors.BORDER};
        border-radius: 10px;
        padding: 11px 12px;
        font-family: Consolas;
        color: #344054;
    }}

    QLineEdit, QComboBox, QDateEdit {{
        background: white;
        border: 1px solid #d0d5dd;
        border-radius: 10px;
        padding: 9px 11px;
        min-height: 22px;
        selection-background-color: {Colors.PRIMARY};
    }}

    QLineEdit:hover, QComboBox:hover, QDateEdit:hover {{ border-color: #aeb5c0; }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
        border: 2px solid #8b8df0;
        padding: 8px 10px;
    }}

    QComboBox::drop-down, QDateEdit::drop-down {{
        border: none;
        width: 28px;
    }}

    QCheckBox {{ spacing: 8px; color: {Colors.TEXT_SECONDARY}; }}
    QCheckBox::indicator {{
        width: 17px; height: 17px; border: 1px solid #c7ccd4; border-radius: 5px; background: white;
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

    QHeaderView::section {{
        background: {Colors.HEADER};
        color: {Colors.TEXT_SECONDARY};
        border: none;
        border-bottom: 1px solid {Colors.BORDER};
        padding: 11px 12px;
        font-size: 11px;
        font-weight: 700;
    }}

    QTableWidget::item, QTableView::item, QTreeWidget::item {{
        padding: 8px 11px;
        border-bottom: 1px solid {Colors.BORDER_SOFT};
    }}

    QTableWidget::item:focus, QTableView::item:focus, QTreeWidget::item:focus {{ outline: none; }}

    QDialog {{ background: {Colors.BACKGROUND}; }}
    QDialog QLabel[role="dialogTitle"] {{ font-size: 23px; font-weight: 700; }}

    QStatusBar {{
        background: #ffffff;
        color: {Colors.TEXT_SECONDARY};
        border-top: 1px solid {Colors.BORDER};
        padding: 4px 12px;
        font-size: 11px;
    }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 3px; }}
    QScrollBar::handle:vertical {{ background: #d0d5dd; min-height: 32px; border-radius: 4px; }}
    QScrollBar::handle:vertical:hover {{ background: #aeb5c0; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 3px; }}
    QScrollBar::handle:horizontal {{ background: #d0d5dd; min-width: 32px; border-radius: 4px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    QToolTip {{
        background: #101828;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 6px 8px;
    }}
    """
