# -*- coding: utf-8 -*-
"""
Theme Styles Module
===================

Comprehensive stylesheet definitions for light and dark themes.
Designed to work with qfluentwidgets components.
"""

# =============================================================================
# LIGHT THEME COLORS
# =============================================================================
LIGHT_COLORS = {
    # Backgrounds
    "window_bg": "#FFFFFF",
    "nav_bg": "#F5F5F5",
    "card_bg": "#FFFFFF",
    "card_hover_bg": "#FAFAFA",
    "card_border": "#E5E5E5",
    "input_bg": "#FFFFFF",
    "input_border": "#D1D1D1",
    "input_hover_border": "#0078D4",
    
    # Text Colors
    "text_primary": "#1A1A1A",
    "text_secondary": "#606060",
    "text_disabled": "#A0A0A0",
    "text_link": "#0078D4",
    
    # Accent Colors
    "accent": "#0078D4",
    "accent_hover": "#106EBE",
    "accent_pressed": "#005A9E",
    "accent_light": "#F0F6FD",
    
    # Status Colors
    "success": "#107C10",
    "success_bg": "#DFF6DD",
    "warning": "#797600",
    "warning_bg": "#FFF4CE",
    "error": "#D13438",
    "error_bg": "#FDE7E9",
    "info": "#0078D4",
    "info_bg": "#F0F6FD",
    
    # UI Elements
    "scrollbar": "#C0C0C0",
    "scrollbar_hover": "#A0A0A0",
    "divider": "#E0E0E0",
    "shadow": "rgba(0, 0, 0, 0.08)",
}

# =============================================================================
# DARK THEME COLORS (reference for reset)
# =============================================================================
DARK_COLORS = {
    "window_bg": "#202020",
    "nav_bg": "#272727",
    "card_bg": "#2D2D2D",
    "card_hover_bg": "#3A3A3A",
    "card_border": "#404040",
    "input_bg": "#2D2D2D",
    "input_border": "#555555",
    "input_hover_border": "#60CDFF",
    
    "text_primary": "#FFFFFF",
    "text_secondary": "#B0B0B0",
    "text_disabled": "#666666",
    "text_link": "#60CDFF",
    
    "accent": "#60CDFF",
    "accent_hover": "#73D6FF",
    "accent_pressed": "#4CC2FF",
    "accent_light": "#1A3A4A",
    
    "success": "#6CCB5F",
    "success_bg": "#1E3B1E",
    "warning": "#FCE100",
    "warning_bg": "#433519",
    "error": "#FF6B6B",
    "error_bg": "#442222",
    "info": "#60CDFF",
    "info_bg": "#1A3A4A",
    
    "scrollbar": "#555555",
    "scrollbar_hover": "#707070",
    "divider": "#404040",
    "shadow": "rgba(0, 0, 0, 0.3)",
}


def get_light_theme_stylesheet() -> str:
    """
    Generate comprehensive light theme stylesheet for qfluentwidgets.
    This covers all major widget types for consistent light theme appearance.
    """
    c = LIGHT_COLORS
    
    return f"""
    /* ===== GLOBAL STYLES ===== */
    QWidget {{
        background-color: transparent;
        color: {c['text_primary']};
    }}
    
    /* ===== MAIN WINDOW ===== */
    FluentWindow, QMainWindow {{
        background-color: {c['window_bg']};
    }}
    
    QStackedWidget {{
        background-color: {c['window_bg']};
    }}
    
    /* ===== SCROLL AREAS ===== */
    QScrollArea {{
        background-color: {c['window_bg']};
        border: none;
    }}
    
    QScrollArea > QWidget > QWidget {{
        background-color: {c['window_bg']};
    }}
    
    ScrollArea {{
        background-color: {c['window_bg']};
        border: none;
    }}
    
    /* ===== SCROLLBARS ===== */
    QScrollBar:vertical {{
        background-color: transparent;
        width: 12px;
        margin: 0px;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {c['scrollbar']};
        border-radius: 6px;
        min-height: 30px;
        margin: 2px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {c['scrollbar_hover']};
    }}
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    
    QScrollBar:horizontal {{
        background-color: transparent;
        height: 12px;
        margin: 0px;
    }}
    
    QScrollBar::handle:horizontal {{
        background-color: {c['scrollbar']};
        border-radius: 6px;
        min-width: 30px;
        margin: 2px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background-color: {c['scrollbar_hover']};
    }}
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    
    /* ===== CARDS ===== */
    CardWidget {{
        background-color: {c['card_bg']};
        border: 1px solid {c['card_border']};
        border-radius: 8px;
    }}
    
    CardWidget:hover {{
        background-color: {c['card_hover_bg']};
        border-color: {c['input_hover_border']};
    }}
    
    /* ===== SETTING CARDS ===== */
    SettingCard {{
        background-color: {c['card_bg']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
    }}
    
    SettingCard:hover {{
        background-color: {c['card_hover_bg']};
    }}
    
    SettingCardGroup {{
        background-color: transparent;
    }}
    
    ExpandSettingCard {{
        background-color: {c['card_bg']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
    }}
    
    /* ===== LABELS ===== */
    QLabel {{
        color: {c['text_primary']};
        background-color: transparent;
    }}
    
    TitleLabel {{
        color: {c['text_primary']};
        background-color: transparent;
    }}
    
    SubtitleLabel {{
        color: {c['text_primary']};
        background-color: transparent;
    }}
    
    BodyLabel {{
        color: {c['text_secondary']};
        background-color: transparent;
    }}
    
    StrongBodyLabel {{
        color: {c['text_primary']};
        background-color: transparent;
    }}
    
    CaptionLabel {{
        color: {c['text_secondary']};
        background-color: transparent;
    }}
    
    /* ===== BUTTONS ===== */
    QPushButton {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
        padding: 6px 16px;
    }}
    
    QPushButton:hover {{
        background-color: {c['card_hover_bg']};
        border-color: {c['input_hover_border']};
    }}
    
    QPushButton:pressed {{
        background-color: {c['accent_light']};
    }}
    
    PushButton {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
    }}
    
    PushButton:hover {{
        background-color: {c['card_hover_bg']};
    }}
    
    PrimaryPushButton {{
        background-color: {c['accent']};
        color: white;
        border: none;
        border-radius: 6px;
    }}
    
    PrimaryPushButton:hover {{
        background-color: {c['accent_hover']};
    }}
    
    PrimaryPushButton:pressed {{
        background-color: {c['accent_pressed']};
    }}
    
    TransparentToolButton {{
        background-color: transparent;
        border: none;
    }}
    
    TransparentToolButton:hover {{
        background-color: {c['accent_light']};
    }}
    
    /* ===== INPUT FIELDS ===== */
    QLineEdit {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
        padding: 6px 10px;
    }}
    
    QLineEdit:focus {{
        border-color: {c['accent']};
        border-width: 2px;
    }}
    
    QLineEdit:hover {{
        border-color: {c['input_hover_border']};
    }}
    
    LineEdit {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
    }}
    
    LineEdit:focus {{
        border-color: {c['accent']};
    }}
    
    PasswordLineEdit {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
    }}
    
    /* ===== TEXT EDIT / TEXT BROWSER ===== */
    QTextEdit {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
    }}
    
    TextEdit {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
    }}
    
    QPlainTextEdit {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
    }}
    
    /* ===== COMBOBOX ===== */
    QComboBox {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
        padding: 6px 10px;
    }}
    
    QComboBox:hover {{
        border-color: {c['input_hover_border']};
    }}
    
    QComboBox::drop-down {{
        border: none;
        padding-right: 10px;
    }}
    
    QComboBox QAbstractItemView {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        selection-background-color: {c['accent_light']};
        selection-color: {c['text_primary']};
    }}
    
    ComboBox {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
    }}
    
    /* ===== SLIDERS ===== */
    QSlider::groove:horizontal {{
        background-color: {c['input_border']};
        height: 6px;
        border-radius: 3px;
    }}
    
    QSlider::handle:horizontal {{
        background-color: {c['accent']};
        width: 16px;
        height: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }}
    
    QSlider::handle:horizontal:hover {{
        background-color: {c['accent_hover']};
    }}
    
    QSlider::sub-page:horizontal {{
        background-color: {c['accent']};
        border-radius: 3px;
    }}
    
    Slider {{
        background-color: transparent;
    }}
    
    /* ===== CHECKBOXES ===== */
    QCheckBox {{
        color: {c['text_primary']};
        background-color: transparent;
    }}
    
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {c['input_border']};
        border-radius: 4px;
        background-color: {c['input_bg']};
    }}
    
    QCheckBox::indicator:checked {{
        background-color: {c['accent']};
        border-color: {c['accent']};
    }}
    
    QCheckBox::indicator:hover {{
        border-color: {c['input_hover_border']};
    }}
    
    /* ===== SWITCH BUTTON ===== */
    SwitchButton {{
        background-color: transparent;
    }}
    
    /* ===== PROGRESS BAR ===== */
    QProgressBar {{
        background-color: {c['input_border']};
        border: none;
        border-radius: 3px;
        height: 6px;
        text-align: center;
    }}
    
    QProgressBar::chunk {{
        background-color: {c['accent']};
        border-radius: 3px;
    }}
    
    ProgressBar {{
        background-color: {c['input_border']};
        border-radius: 3px;
    }}
    
    /* ===== TAB WIDGET ===== */
    QTabWidget::pane {{
        background-color: {c['card_bg']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
    }}
    
    QTabBar::tab {{
        background-color: {c['nav_bg']};
        color: {c['text_secondary']};
        padding: 8px 16px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
    }}
    
    QTabBar::tab:selected {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
    }}
    
    QTabBar::tab:hover {{
        background-color: {c['card_hover_bg']};
    }}
    
    /* ===== TOOLTIPS ===== */
    QToolTip {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        border-radius: 4px;
        padding: 4px 8px;
    }}
    
    /* ===== MENU ===== */
    QMenu {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        border-radius: 8px;
        padding: 4px;
    }}
    
    QMenu::item {{
        padding: 8px 24px;
        border-radius: 4px;
    }}
    
    QMenu::item:selected {{
        background-color: {c['accent_light']};
    }}
    
    QMenu::separator {{
        height: 1px;
        background-color: {c['divider']};
        margin: 4px 8px;
    }}
    
    /* ===== MESSAGE BOX / DIALOG ===== */
    QDialog {{
        background-color: {c['window_bg']};
    }}
    
    QMessageBox {{
        background-color: {c['window_bg']};
    }}
    
    MessageBox {{
        background-color: {c['window_bg']};
    }}
    
    /* ===== INFO BAR ===== */
    InfoBar {{
        background-color: {c['card_bg']};
        border: 1px solid {c['card_border']};
        border-radius: 8px;
    }}
    
    /* ===== GROUP BOX ===== */
    QGroupBox {{
        background-color: {c['card_bg']};
        border: 1px solid {c['card_border']};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 12px;
    }}
    
    QGroupBox::title {{
        color: {c['text_primary']};
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
    }}
    
    /* ===== TABLE / LIST VIEWS ===== */
    QTableView {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
        gridline-color: {c['divider']};
    }}
    
    QTableView::item {{
        padding: 6px;
    }}
    
    QTableView::item:selected {{
        background-color: {c['accent_light']};
        color: {c['text_primary']};
    }}
    
    QHeaderView::section {{
        background-color: {c['nav_bg']};
        color: {c['text_primary']};
        border: none;
        border-bottom: 1px solid {c['divider']};
        padding: 8px;
    }}
    
    QListView {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
    }}
    
    QListView::item {{
        padding: 6px;
        border-radius: 4px;
    }}
    
    QListView::item:selected {{
        background-color: {c['accent_light']};
        color: {c['text_primary']};
    }}
    
    QListView::item:hover {{
        background-color: {c['card_hover_bg']};
    }}
    
    /* ===== TREE VIEW ===== */
    QTreeView {{
        background-color: {c['card_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['card_border']};
        border-radius: 6px;
    }}
    
    QTreeView::item {{
        padding: 4px;
    }}
    
    QTreeView::item:selected {{
        background-color: {c['accent_light']};
        color: {c['text_primary']};
    }}
    
    QTreeView::item:hover {{
        background-color: {c['card_hover_bg']};
    }}
    
    /* ===== SPIN BOX ===== */
    QSpinBox {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
        padding: 4px 8px;
    }}
    
    QSpinBox:hover {{
        border-color: {c['input_hover_border']};
    }}
    
    QDoubleSpinBox {{
        background-color: {c['input_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['input_border']};
        border-radius: 6px;
        padding: 4px 8px;
    }}
    
    /* ===== FRAME ===== */
    QFrame {{
        background-color: transparent;
    }}
    
    /* ===== SPLITTER ===== */
    QSplitter::handle {{
        background-color: {c['divider']};
    }}
    
    QSplitter::handle:horizontal {{
        width: 1px;
    }}
    
    QSplitter::handle:vertical {{
        height: 1px;
    }}
    """


def get_light_navigation_stylesheet() -> str:
    """
    Specific stylesheet for NavigationInterface in light theme.
    Applied separately to navigation panel.
    """
    c = LIGHT_COLORS
    
    return f"""
    NavigationInterface {{
        background-color: {c['nav_bg']};
        border-right: 1px solid {c['divider']};
    }}
    
    NavigationPanel {{
        background-color: {c['nav_bg']};
    }}
    
    NavigationWidget {{
        background-color: transparent;
    }}
    
    NavigationPushButton {{
        background-color: transparent;
        color: {c['text_primary']};
        border: none;
        border-radius: 6px;
        padding: 8px 12px;
    }}
    
    NavigationPushButton:hover {{
        background-color: {c['accent_light']};
    }}
    
    NavigationPushButton:pressed {{
        background-color: {c['card_border']};
    }}
    
    NavigationPushButton[isSelected="true"] {{
        background-color: {c['accent_light']};
    }}
    
    NavigationTreeWidget {{
        background-color: transparent;
    }}
    
    NavigationSeparator {{
        background-color: {c['divider']};
    }}
    
    QLabel {{
        color: {c['text_primary']};
    }}
    """


def get_light_titlebar_stylesheet() -> str:
    """
    Specific stylesheet for TitleBar in light theme.
    Applied separately to title bar.
    """
    c = LIGHT_COLORS
    
    return f"""
    TitleBar {{
        background-color: {c['nav_bg']};
    }}
    
    QLabel {{
        color: {c['text_primary']};
        background-color: transparent;
    }}
    
    TitleBarButton {{
        background-color: transparent;
        border: none;
    }}
    
    TitleBarButton:hover {{
        background-color: {c['accent_light']};
    }}
    
    MinimizeButton:hover {{
        background-color: {c['accent_light']};
    }}
    
    MaximizeButton:hover {{
        background-color: {c['accent_light']};
    }}
    
    CloseButton:hover {{
        background-color: {c['error']};
    }}
    """


def apply_light_theme_to_widget(widget) -> None:
    """
    Apply light theme colors directly to a widget and its children.
    This is a supplementary method for widgets that don't respond well to stylesheets.
    
    Args:
        widget: QWidget to style
    """
    from PyQt6.QtGui import QPalette, QColor
    from PyQt6.QtWidgets import QWidget
    
    c = LIGHT_COLORS
    
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(c['window_bg']))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(c['text_primary']))
    palette.setColor(QPalette.ColorRole.Base, QColor(c['input_bg']))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(c['card_hover_bg']))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(c['card_bg']))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(c['text_primary']))
    palette.setColor(QPalette.ColorRole.Text, QColor(c['text_primary']))
    palette.setColor(QPalette.ColorRole.Button, QColor(c['card_bg']))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(c['text_primary']))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(c['accent']))
    palette.setColor(QPalette.ColorRole.Link, QColor(c['text_link']))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(c['accent']))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor('#FFFFFF'))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(c['text_disabled']))
    
    widget.setPalette(palette)
