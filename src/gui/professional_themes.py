"""
Professional QSS Theme Generator for RenLocalizer V2
Generates modern, minimal and eye-friendly Qt Style Sheets
"""

from .theme_palettes import DarkTheme, LightTheme, SolarizedTheme

def get_dark_theme_qss():
    """Modern Koyu Tema QSS - Koyu lacivert esintili profesyonel tema"""
    theme = DarkTheme
    
    return f"""
    /* ================================================
       MODERN DARK THEME - Koyu Lacivert Esintili
       ================================================ */
    
    /* Temel Widget Stili - Tüm widget'lar için varsayılan */
    QWidget {{
        background-color: {theme.BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 9pt;
    }}
    
    /* Ana Pencere */
    QMainWindow {{
        background-color: {theme.BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 9pt;
    }}
    
    /* Etiketler - Label */
    QLabel {{
        background-color: transparent;
        color: {theme.TEXT_PRIMARY};
    }}
    
    /* Butonlar - Ana Buton (Primary) */
    QPushButton {{
        background-color: {theme.PRIMARY};
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
        min-height: 28px;
    }}
    
    QPushButton:hover {{
        background-color: {theme.PRIMARY_HOVER};
    }}
    
    QPushButton:pressed {{
        background-color: {theme.PRIMARY_PRESSED};
    }}
    
    QPushButton:disabled {{
        background-color: {theme.TEXT_DISABLED};
        color: {theme.BACKGROUND};
    }}
    
    /* Özel Buton Sınıfları */
    QPushButton[class="success"] {{
        background-color: {theme.SUCCESS};
    }}
    
    QPushButton[class="success"]:hover {{
        background-color: #5CAE60;
    }}
    
    QPushButton[class="error"] {{
        background-color: {theme.ERROR};
    }}
    
    QPushButton[class="error"]:hover {{
        background-color: #E74C3C;
    }}
    
    QPushButton[class="secondary"] {{
        background-color: {theme.SECONDARY};
        color: {theme.BACKGROUND};
    }}
    
    QPushButton[class="secondary"]:hover {{
        background-color: {theme.SECONDARY_HOVER};
    }}
    
    /* Progress Bar - İlerleme Çubuğu */
    QProgressBar {{
        background-color: {theme.PANEL_BACKGROUND};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        text-align: center;
        color: {theme.TEXT_PRIMARY};
        font-weight: 500;
    }}
    
    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                  stop:0 {theme.PRIMARY}, stop:1 {theme.PRIMARY_HOVER});
        border-radius: 3px;
    }}
    
    /* Sekmeler - Tab Widget */
    QTabWidget::pane {{
        background-color: {theme.PANEL_BACKGROUND};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
    }}
    
    QTabBar::tab {{
        background-color: {theme.BACKGROUND};
        color: {theme.TEXT_SECONDARY};
        padding: 8px 16px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        border: 1px solid {theme.BORDER};
        border-bottom: none;
    }}
    
    QTabBar::tab:selected {{
        background-color: {theme.PRIMARY};
        color: #FFFFFF;
        font-weight: 500;
    }}
    
    QTabBar::tab:hover:!selected {{
        background-color: {theme.PANEL_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
    }}
    
    /* Metin Alanları */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {theme.WIDGET_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        padding: 6px;
        selection-background-color: {theme.PRIMARY};
    }}
    
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 2px solid {theme.BORDER_FOCUS};
    }}
    
    /* Açılır Kutular */
    QComboBox {{
        background-color: {theme.WIDGET_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        padding: 6px 8px;
        min-height: 20px;
    }}
    
    QComboBox:focus {{
        border: 2px solid {theme.BORDER_FOCUS};
    }}
    
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 4px solid {theme.TEXT_SECONDARY};
    }}
    
    /* Liste Öğeleri */
    QListWidget, QTreeWidget {{
        background-color: {theme.WIDGET_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        outline: none;
    }}
    
    QListWidget::item, QTreeWidget::item {{
        padding: 4px;
        border-bottom: 1px solid {theme.BORDER};
    }}
    
    QListWidget::item:selected, QTreeWidget::item:selected {{
        background-color: {theme.PRIMARY};
        color: #FFFFFF;
    }}
    
    QListWidget::item:hover, QTreeWidget::item:hover {{
        background-color: {theme.PANEL_BACKGROUND};
    }}
    
    /* Kaydırma Çubukları */
    QScrollBar:vertical {{
        background-color: {theme.PANEL_BACKGROUND};
        width: 12px;
        border-radius: 6px;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {theme.BORDER};
        border-radius: 6px;
        min-height: 20px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {theme.TEXT_DISABLED};
    }}
    
    /* Menüler */
    QMenuBar {{
        background-color: {theme.PANEL_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border-bottom: 1px solid {theme.BORDER};
    }}
    
    QMenuBar::item {{
        padding: 6px 12px;
        background: transparent;
    }}
    
    QMenuBar::item:selected {{
        background-color: {theme.PRIMARY};
        color: #FFFFFF;
    }}
    
    QMenu {{
        background-color: {theme.PANEL_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
    }}
    
    QMenu::item {{
        padding: 6px 20px;
    }}
    
    QMenu::item:selected {{
        background-color: {theme.PRIMARY};
        color: #FFFFFF;
    }}
    
    /* Durum Çubuğu */
    QStatusBar {{
        background-color: {theme.PANEL_BACKGROUND};
        color: {theme.TEXT_SECONDARY};
        border-top: 1px solid {theme.BORDER};
    }}
    
    /* Grup Kutuları */
    QGroupBox {{
        color: {theme.TEXT_PRIMARY};
        font-weight: 500;
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 8px;
    }}
    
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }}
    
    /* Etiketler - Semantic Sınıflar */
    QLabel[class="title"] {{
        color: {theme.TEXT_PRIMARY};
        font-size: 12pt;
        font-weight: bold;
    }}
    
    QLabel[class="subtitle"] {{
        color: {theme.TEXT_SECONDARY};
        font-size: 10pt;
        font-weight: 500;
    }}
    
    QLabel[class="caption"] {{
        color: {theme.TEXT_SECONDARY};
        font-size: 8pt;
    }}
    
    QLabel[class="success"] {{
        color: {theme.SUCCESS};
        font-weight: 500;
    }}
    
    QLabel[class="error"] {{
        color: {theme.ERROR};
        font-weight: 500;
    }}
    
    QLabel[class="warning"] {{
        color: {theme.WARNING};
        font-weight: 500;
    }}
    
    /* Onay Kutuları */
    QCheckBox {{
        color: {theme.TEXT_PRIMARY};
        spacing: 8px;
    }}
    
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {theme.BORDER};
        border-radius: 3px;
        background-color: {theme.WIDGET_BACKGROUND};
    }}
    
    QCheckBox::indicator:checked {{
        background-color: {theme.PRIMARY};
        border-color: {theme.PRIMARY};
    }}
    
    /* Araç İpuçları */
    QToolTip {{
        background-color: {theme.PANEL_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        padding: 4px;
    }}
    """

def get_light_theme_qss():
    """Açık Tema QSS - Temiz ve minimal beyaz esintili tema"""
    theme = LightTheme
    
    return f"""
    /* ================================================
       LIGHT THEME - Temiz ve Minimal
       ================================================ */
    
    /* Temel Widget Stili - Tüm widget'lar için varsayılan */
    QWidget {{
        background-color: {theme.BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 9pt;
    }}
    
    /* Ana Pencere */
    QMainWindow {{
        background-color: {theme.BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 9pt;
    }}
    
    /* Etiketler - Label */
    QLabel {{
        background-color: transparent;
        color: {theme.TEXT_PRIMARY};
    }}
    
    /* Butonlar - Ana Buton (Primary) */
    QPushButton {{
        background-color: {theme.PRIMARY};
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
        min-height: 28px;
    }}
    
    QPushButton:hover {{
        background-color: {theme.PRIMARY_HOVER};
    }}
    
    QPushButton:pressed {{
        background-color: {theme.PRIMARY_PRESSED};
    }}
    
    QPushButton:disabled {{
        background-color: {theme.TEXT_DISABLED};
        color: #FFFFFF;
    }}
    
    /* Özel Buton Sınıfları */
    QPushButton[class="success"] {{
        background-color: {theme.SUCCESS};
    }}
    
    QPushButton[class="success"]:hover {{
        background-color: #2E7A32;
    }}
    
    QPushButton[class="error"] {{
        background-color: {theme.ERROR};
    }}
    
    QPushButton[class="error"]:hover {{
        background-color: #C62828;
    }}
    
    QPushButton[class="secondary"] {{
        background-color: {theme.SECONDARY};
        color: #FFFFFF;
    }}
    
    QPushButton[class="secondary"]:hover {{
        background-color: {theme.SECONDARY_HOVER};
    }}
    
    /* Progress Bar - İlerleme Çubuğu */
    QProgressBar {{
        background-color: {theme.PANEL_BACKGROUND};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        text-align: center;
        color: {theme.TEXT_PRIMARY};
        font-weight: 500;
    }}
    
    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                  stop:0 {theme.PRIMARY}, stop:1 {theme.PRIMARY_HOVER});
        border-radius: 3px;
    }}
    
    /* Sekmeler - Tab Widget */
    QTabWidget::pane {{
        background-color: {theme.PANEL_BACKGROUND};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
    }}
    
    QTabBar::tab {{
        background-color: {theme.BACKGROUND};
        color: {theme.TEXT_SECONDARY};
        padding: 8px 16px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        border: 1px solid {theme.BORDER};
        border-bottom: none;
    }}
    
    QTabBar::tab:selected {{
        background-color: {theme.PRIMARY};
        color: #FFFFFF;
        font-weight: 500;
    }}
    
    QTabBar::tab:hover:!selected {{
        background-color: {theme.PANEL_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
    }}
    
    /* Metin Alanları */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {theme.WIDGET_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        padding: 6px;
        selection-background-color: {theme.PRIMARY};
    }}
    
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 2px solid {theme.BORDER_FOCUS};
    }}
    
    /* Açılır Kutular */
    QComboBox {{
        background-color: {theme.WIDGET_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        padding: 6px 8px;
        min-height: 20px;
    }}
    
    QComboBox:focus {{
        border: 2px solid {theme.BORDER_FOCUS};
    }}
    
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 4px solid {theme.TEXT_SECONDARY};
    }}
    
    /* Liste Öğeleri */
    QListWidget, QTreeWidget {{
        background-color: {theme.WIDGET_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        outline: none;
    }}
    
    QListWidget::item, QTreeWidget::item {{
        padding: 4px;
        border-bottom: 1px solid {theme.BORDER};
    }}
    
    QListWidget::item:selected, QTreeWidget::item:selected {{
        background-color: {theme.PRIMARY};
        color: #FFFFFF;
    }}
    
    QListWidget::item:hover, QTreeWidget::item:hover {{
        background-color: {theme.PANEL_BACKGROUND};
    }}
    
    /* Kaydırma Çubukları */
    QScrollBar:vertical {{
        background-color: {theme.PANEL_BACKGROUND};
        width: 12px;
        border-radius: 6px;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {theme.BORDER};
        border-radius: 6px;
        min-height: 20px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {theme.TEXT_SECONDARY};
    }}
    
    /* Menüler */
    QMenuBar {{
        background-color: {theme.PANEL_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border-bottom: 1px solid {theme.BORDER};
    }}
    
    QMenuBar::item {{
        padding: 6px 12px;
        background: transparent;
    }}
    
    QMenuBar::item:selected {{
        background-color: {theme.PRIMARY};
        color: #FFFFFF;
    }}
    
    QMenu {{
        background-color: {theme.PANEL_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
    }}
    
    QMenu::item {{
        padding: 6px 20px;
    }}
    
    QMenu::item:selected {{
        background-color: {theme.PRIMARY};
        color: #FFFFFF;
    }}
    
    /* Durum Çubuğu */
    QStatusBar {{
        background-color: {theme.PANEL_BACKGROUND};
        color: {theme.TEXT_SECONDARY};
        border-top: 1px solid {theme.BORDER};
    }}
    
    /* Grup Kutuları */
    QGroupBox {{
        color: {theme.TEXT_PRIMARY};
        font-weight: 500;
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 8px;
    }}
    
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }}
    
    /* Etiketler - Semantic Sınıflar */
    QLabel[class="title"] {{
        color: {theme.TEXT_PRIMARY};
        font-size: 12pt;
        font-weight: bold;
    }}
    
    QLabel[class="subtitle"] {{
        color: {theme.TEXT_SECONDARY};
        font-size: 10pt;
        font-weight: 500;
    }}
    
    QLabel[class="caption"] {{
        color: {theme.TEXT_SECONDARY};
        font-size: 8pt;
    }}
    
    QLabel[class="success"] {{
        color: {theme.SUCCESS};
        font-weight: 500;
    }}
    
    QLabel[class="error"] {{
        color: {theme.ERROR};
        font-weight: 500;
    }}
    
    QLabel[class="warning"] {{
        color: {theme.WARNING};
        font-weight: 500;
    }}
    
    /* Onay Kutuları */
    QCheckBox {{
        color: {theme.TEXT_PRIMARY};
        spacing: 8px;
    }}
    
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {theme.BORDER};
        border-radius: 3px;
        background-color: {theme.WIDGET_BACKGROUND};
    }}
    
    QCheckBox::indicator:checked {{
        background-color: {theme.PRIMARY};
        border-color: {theme.PRIMARY};
    }}
    
    /* Araç İpuçları */
    QToolTip {{
        background-color: {theme.PANEL_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        padding: 4px;
    }}
    """

def get_solarized_theme_qss():
    """Göz Dostu Solarized Esintili Tema QSS - Koyu mavi-gri esintili"""
    theme = SolarizedTheme
    
    return f"""
    /* ================================================
       SOLARIZED THEME - Göz Dostu Tema
       ================================================ */
    
    /* Temel Widget Stili - Tüm widget'lar için varsayılan */
    QWidget {{
        background-color: {theme.BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 9pt;
    }}
    
    /* Ana Pencere */
    QMainWindow {{
        background-color: {theme.BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 9pt;
    }}
    
    /* Etiketler - Label */
    QLabel {{
        background-color: transparent;
        color: {theme.TEXT_PRIMARY};
    }}
    
    /* Butonlar - Ana Buton (Primary) */
    QPushButton {{
        background-color: {theme.PRIMARY};
        color: {theme.TEXT_PRIMARY};
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 500;
        min-height: 28px;
    }}
    
    QPushButton:hover {{
        background-color: {theme.PRIMARY_HOVER};
    }}
    
    QPushButton:pressed {{
        background-color: {theme.PRIMARY_PRESSED};
    }}
    
    QPushButton:disabled {{
        background-color: {theme.TEXT_DISABLED};
        color: {theme.BACKGROUND};
    }}
    
    /* Özel Buton Sınıfları */
    QPushButton[class="success"] {{
        background-color: {theme.SUCCESS};
        color: {theme.TEXT_PRIMARY};
    }}
    
    QPushButton[class="success"]:hover {{
        background-color: #6F7F00;
    }}
    
    QPushButton[class="error"] {{
        background-color: {theme.ERROR};
        color: {theme.TEXT_PRIMARY};
    }}
    
    QPushButton[class="error"]:hover {{
        background-color: #B52926;
    }}
    
    QPushButton[class="secondary"] {{
        background-color: {theme.SECONDARY};
        color: {theme.BACKGROUND};
    }}
    
    QPushButton[class="secondary"]:hover {{
        background-color: {theme.SECONDARY_HOVER};
    }}
    
    /* Progress Bar - İlerleme Çubuğu */
    QProgressBar {{
        background-color: {theme.PANEL_BACKGROUND};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        text-align: center;
        color: {theme.TEXT_PRIMARY};
        font-weight: 500;
    }}
    
    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                  stop:0 {theme.PRIMARY}, stop:1 {theme.PRIMARY_HOVER});
        border-radius: 3px;
    }}
    
    /* Sekmeler - Tab Widget */
    QTabWidget::pane {{
        background-color: {theme.PANEL_BACKGROUND};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
    }}
    
    QTabBar::tab {{
        background-color: {theme.BACKGROUND};
        color: {theme.TEXT_SECONDARY};
        padding: 8px 16px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        border: 1px solid {theme.BORDER};
        border-bottom: none;
    }}
    
    QTabBar::tab:selected {{
        background-color: {theme.PRIMARY};
        color: {theme.TEXT_PRIMARY};
        font-weight: 500;
    }}
    
    QTabBar::tab:hover:!selected {{
        background-color: {theme.PANEL_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
    }}
    
    /* Metin Alanları */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {theme.WIDGET_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        padding: 6px;
        selection-background-color: {theme.PRIMARY};
    }}
    
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 2px solid {theme.BORDER_FOCUS};
    }}
    
    /* Açılır Kutular */
    QComboBox {{
        background-color: {theme.WIDGET_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        padding: 6px 8px;
        min-height: 20px;
    }}
    
    QComboBox:focus {{
        border: 2px solid {theme.BORDER_FOCUS};
    }}
    
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 4px solid {theme.TEXT_SECONDARY};
    }}
    
    /* Liste Öğeleri */
    QListWidget, QTreeWidget {{
        background-color: {theme.WIDGET_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        outline: none;
    }}
    
    QListWidget::item, QTreeWidget::item {{
        padding: 4px;
        border-bottom: 1px solid {theme.BORDER};
    }}
    
    QListWidget::item:selected, QTreeWidget::item:selected {{
        background-color: {theme.PRIMARY};
        color: {theme.TEXT_PRIMARY};
    }}
    
    QListWidget::item:hover, QTreeWidget::item:hover {{
        background-color: {theme.PANEL_BACKGROUND};
    }}
    
    /* Kaydırma Çubukları */
    QScrollBar:vertical {{
        background-color: {theme.PANEL_BACKGROUND};
        width: 12px;
        border-radius: 6px;
    }}
    
    QScrollBar::handle:vertical {{
        background-color: {theme.BORDER};
        border-radius: 6px;
        min-height: 20px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background-color: {theme.TEXT_DISABLED};
    }}
    
    /* Menüler */
    QMenuBar {{
        background-color: {theme.PANEL_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border-bottom: 1px solid {theme.BORDER};
    }}
    
    QMenuBar::item {{
        padding: 6px 12px;
        background: transparent;
    }}
    
    QMenuBar::item:selected {{
        background-color: {theme.PRIMARY};
        color: {theme.TEXT_PRIMARY};
    }}
    
    QMenu {{
        background-color: {theme.PANEL_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
    }}
    
    QMenu::item {{
        padding: 6px 20px;
    }}
    
    QMenu::item:selected {{
        background-color: {theme.PRIMARY};
        color: {theme.TEXT_PRIMARY};
    }}
    
    /* Durum Çubuğu */
    QStatusBar {{
        background-color: {theme.PANEL_BACKGROUND};
        color: {theme.TEXT_SECONDARY};
        border-top: 1px solid {theme.BORDER};
    }}
    
    /* Grup Kutuları */
    QGroupBox {{
        color: {theme.TEXT_PRIMARY};
        font-weight: 500;
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 8px;
    }}
    
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }}
    
    /* Etiketler - Semantic Sınıflar */
    QLabel[class="title"] {{
        color: {theme.TEXT_PRIMARY};
        font-size: 12pt;
        font-weight: bold;
    }}
    
    QLabel[class="subtitle"] {{
        color: {theme.TEXT_SECONDARY};
        font-size: 10pt;
        font-weight: 500;
    }}
    
    QLabel[class="caption"] {{
        color: {theme.TEXT_SECONDARY};
        font-size: 8pt;
    }}
    
    QLabel[class="success"] {{
        color: {theme.SUCCESS};
        font-weight: 500;
    }}
    
    QLabel[class="error"] {{
        color: {theme.ERROR};
        font-weight: 500;
    }}
    
    QLabel[class="warning"] {{
        color: {theme.WARNING};
        font-weight: 500;
    }}
    
    /* Onay Kutuları */
    QCheckBox {{
        color: {theme.TEXT_PRIMARY};
        spacing: 8px;
    }}
    
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {theme.BORDER};
        border-radius: 3px;
        background-color: {theme.WIDGET_BACKGROUND};
    }}
    
    QCheckBox::indicator:checked {{
        background-color: {theme.PRIMARY};
        border-color: {theme.PRIMARY};
    }}
    
    /* Araç İpuçları */
    QToolTip {{
        background-color: {theme.PANEL_BACKGROUND};
        color: {theme.TEXT_PRIMARY};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        padding: 4px;
    }}
    """

def get_theme_qss(theme_name):
    """Belirtilen tema için QSS string'ini döndürür"""
    if theme_name == 'dark':
        return get_dark_theme_qss()
    elif theme_name == 'light':
        return get_light_theme_qss()
    elif theme_name == 'solarized':
        return get_solarized_theme_qss()
    else:
        # Varsayılan olarak light tema
        return get_light_theme_qss()

def apply_theme_to_widget(widget, theme_name):
    """Widget'a belirtilen temayı uygular"""
    qss = get_theme_qss(theme_name)
    widget.setStyleSheet(qss)
    print(f"Applied {theme_name} theme successfully")
