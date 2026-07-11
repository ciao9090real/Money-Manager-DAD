from app.ui.theme import Colors, Spacing


def app_stylesheet() -> str:
    return f"""
    QWidget {{
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: 13px;
        color: {Colors.TEXT};
    }}

    QMainWindow, #AppRoot, #ContentRoot {{
        background: {Colors.BACKGROUND};
    }}

    #Sidebar {{
        background: {Colors.SIDEBAR};
        border: none;
    }}

    #SidebarTitle {{
        color: white;
        font-size: 17px;
        font-weight: 700;
    }}

    #SidebarSubtitle {{
        color: {Colors.SIDEBAR_MUTED};
        font-size: 12px;
    }}

    #SidebarMark {{
        background: #eff6ff;
        color: {Colors.PRIMARY_DARK};
        border-radius: 10px;
        font-size: 18px;
        font-weight: 800;
    }}

    QPushButton {{
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 9px 14px;
        background: white;
        color: {Colors.TEXT};
        font-weight: 600;
        min-height: 20px;
    }}

    QPushButton:hover {{
        border-color: #cbd5e1;
        background: #f8fafc;
    }}

    QPushButton[variant="primary"] {{
        background: {Colors.PRIMARY};
        border-color: {Colors.PRIMARY};
        color: white;
    }}

    QPushButton[variant="primary"]:hover {{
        background: {Colors.PRIMARY_DARK};
        border-color: {Colors.PRIMARY_DARK};
    }}

    QPushButton[variant="nav"] {{
        background: transparent;
        border: none;
        color: #d0d5dd;
        text-align: left;
        padding: 11px 12px;
        border-radius: 10px;
        font-weight: 600;
        min-height: 22px;
    }}

    QPushButton[variant="nav"][collapsed="true"] {{
        text-align: center;
        padding: 11px 0;
        font-size: 17px;
    }}

    QPushButton[variant="nav"]:hover {{
        background: #1d2939;
        color: white;
    }}

    QPushButton[variant="nav"][selected="true"] {{
        background: {Colors.SIDEBAR_SELECTED};
        color: white;
    }}

    QFrame[role="navItem"] {{
        background: transparent;
        border: none;
        border-radius: 10px;
    }}

    QFrame[role="navItem"]:hover {{
        background: #1d2939;
    }}

    QFrame[role="navItem"][selected="true"] {{
        background: {Colors.SIDEBAR_SELECTED};
    }}

    QLabel[role="navIcon"] {{
        color: #d0d5dd;
        font-size: 20px;
        font-weight: 750;
    }}

    QLabel[role="navLabel"] {{
        color: #d0d5dd;
        font-size: 13px;
        font-weight: 700;
    }}

    QFrame[role="navItem"]:hover QLabel[role="navIcon"],
    QFrame[role="navItem"]:hover QLabel[role="navLabel"],
    QFrame[role="navItem"][selected="true"] QLabel[role="navIcon"],
    QFrame[role="navItem"][selected="true"] QLabel[role="navLabel"] {{
        color: white;
    }}

    QPushButton[variant="sidebarIcon"] {{
        background: transparent;
        border: 1px solid #1e293b;
        color: #cbd5e1;
        border-radius: 10px;
        padding: 0;
        font-size: 18px;
        font-weight: 800;
    }}

    QPushButton[variant="sidebarIcon"]:hover {{
        background: #1e293b;
        border-color: #334155;
        color: white;
    }}

    QPushButton[variant="chip"] {{
        background: white;
        border: 1px solid {Colors.BORDER};
        color: {Colors.TEXT_SECONDARY};
        border-radius: 14px;
        padding: 6px 12px;
        font-weight: 700;
    }}

    QPushButton[variant="chip"][selected="true"] {{
        background: #eff6ff;
        border-color: #bfdbfe;
        color: {Colors.PRIMARY_DARK};
    }}

    QFrame[role="card"] {{
        background: {Colors.CARD};
        border: 1px solid {Colors.BORDER};
        border-radius: {Spacing.RADIUS}px;
    }}

    QLabel[role="pageTitle"] {{
        font-size: 26px;
        font-weight: 750;
        color: {Colors.TEXT};
    }}

    QLabel[role="subtitle"] {{
        color: {Colors.TEXT_SECONDARY};
    }}

    QLabel[role="sectionTitle"] {{
        font-size: 17px;
        font-weight: 700;
    }}

    QLabel[role="metricLabel"] {{
        color: {Colors.TEXT_SECONDARY};
        font-weight: 600;
    }}

    QLabel[role="metricValue"] {{
        font-size: 24px;
        font-weight: 800;
        color: {Colors.TEXT};
    }}

    QLabel[role="icon"] {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 15px;
    }}

    QLabel[tone="positive"] {{
        color: {Colors.POSITIVE};
    }}

    QLabel[tone="negative"] {{
        color: {Colors.NEGATIVE};
    }}

    QLabel[role="helper"], QLabel[role="emptySubtitle"] {{
        color: {Colors.TEXT_SECONDARY};
    }}

    QLabel[role="emptyTitle"] {{
        color: {Colors.TEXT};
        font-weight: 750;
        font-size: 16px;
    }}

    QLabel[role="badge"] {{
        border-radius: 10px;
        padding: 2px 9px;
        font-size: 12px;
        font-weight: 700;
    }}

    QLabel[role="badge"][tone="neutral"] {{
        background: {Colors.NEUTRAL_BADGE_BG};
        color: {Colors.NEUTRAL_BADGE_TEXT};
    }}

    QLabel[role="badge"][tone="positive"] {{
        background: {Colors.POSITIVE_BADGE_BG};
        color: {Colors.POSITIVE_BADGE_TEXT};
    }}

    QLabel[role="badge"][tone="negative"] {{
        background: {Colors.NEGATIVE_BADGE_BG};
        color: {Colors.NEGATIVE_BADGE_TEXT};
    }}

    QLabel[role="badge"][tone="info"] {{
        background: {Colors.INFO_BADGE_BG};
        color: {Colors.INFO_BADGE_TEXT};
    }}

    QLabel[role="badge"][tone="muted"] {{
        background: {Colors.MUTED_BADGE_BG};
        color: {Colors.MUTED_BADGE_TEXT};
    }}

    QLabel[role="mono"] {{
        background: #f8fafc;
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 10px;
        font-family: Consolas, "Courier New", monospace;
        color: {Colors.TEXT};
    }}

    QLineEdit, QComboBox, QDateEdit {{
        background: white;
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 8px 10px;
        min-height: 22px;
    }}

    QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
        border-color: {Colors.PRIMARY};
    }}

    QTableWidget, QTreeWidget {{
        background: white;
        border: none;
        gridline-color: transparent;
        alternate-background-color: {Colors.ROW_ALT};
        selection-background-color: #dbeafe;
        selection-color: {Colors.TEXT};
        outline: 0;
    }}

    QHeaderView::section {{
        background: {Colors.HEADER};
        color: {Colors.TEXT_SECONDARY};
        border: none;
        border-bottom: 1px solid {Colors.BORDER};
        padding: 9px 10px;
        font-weight: 700;
    }}

    QTableWidget::item, QTreeWidget::item {{
        padding: 7px 10px;
        border-bottom: 1px solid #f1f5f9;
    }}

    QTableWidget::item:focus, QTreeWidget::item:focus {{
        outline: none;
    }}

    QDialog {{
        background: {Colors.BACKGROUND};
    }}

    QStatusBar {{
        background: #eef2f7;
        color: {Colors.TEXT_SECONDARY};
        border-top: 1px solid {Colors.BORDER};
        padding: 4px 12px;
    }}
    """
