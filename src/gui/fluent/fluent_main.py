# -*- coding: utf-8 -*-
"""
Fluent Main Window
==================

Main application window using PyQt6-Fluent-Widgets with Windows 11 Fluent Design.
"""

import sys
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QDesktopServices
from PyQt6.QtWidgets import QApplication, QMessageBox

from qfluentwidgets import (
    FluentWindow, FluentIcon, NavigationItemPosition,
    setTheme, Theme, setThemeColor, InfoBar, InfoBarPosition
)
from qfluentwidgets import FluentIcon as FIF

from src.utils.config import ConfigManager
from src.utils.update_checker import check_for_updates
from src.version import VERSION


class UpdateCheckWorker(QThread):
    """Run update checks without blocking the UI."""
    finished = pyqtSignal(object)

    def __init__(self, current_version: str, parent=None):
        super().__init__(parent)
        self.current_version = current_version

    def run(self):
        result = check_for_updates(self.current_version)
        self.finished.emit(result)


class FluentMainWindow(FluentWindow):
    """Main application window with Fluent Design."""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Initialize config manager
        self.config_manager = ConfigManager()
        
        # Set window properties
        self.setWindowTitle(f"RenLocalizer v{VERSION}")
        self.setMinimumSize(1000, 700)
        self.showMaximized()
        
        # Set application icon
        self._set_window_icon()
        
        # Apply theme from config (not from system)
        self._apply_theme_from_config()
        
        # Initialize interfaces (pages)
        self._init_interfaces()
        
        # Setup navigation
        self._init_navigation()
        
        self.logger.info("FluentMainWindow initialized successfully")
        
        # Check for updates on startup (delayed to ensure window is fully ready)
        QTimer.singleShot(1000, self._check_for_updates)

    def _apply_theme_from_config(self):
        """Apply theme based on config settings, ignoring system theme."""
        app_theme = getattr(self.config_manager.app_settings, 'app_theme', 'dark')
        self.apply_theme(app_theme)
    
    def apply_theme(self, theme_name: str):
        """Apply the specified theme. Options: 'dark', 'light'."""
        from qfluentwidgets import qconfig
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        
        # Import theme styles
        from src.gui.fluent.theme_styles import (
            get_theme_stylesheet,
            get_navigation_stylesheet,
            get_titlebar_stylesheet,
            apply_theme_palette,
            LIGHT_COLORS,
            DARK_COLORS,
            RED_COLORS,
            TURQUOISE_COLORS,
            GREEN_COLORS,
            NEON_COLORS
        )
        
        # 1. Select Color Palette based on theme name
        if theme_name == "light":
            colors = LIGHT_COLORS
            qconfig.theme = Theme.LIGHT
            setTheme(Theme.LIGHT)
        elif theme_name == "red":
            colors = RED_COLORS
            qconfig.theme = Theme.DARK
            setTheme(Theme.DARK)
        elif theme_name == "turquoise":
            colors = TURQUOISE_COLORS
            qconfig.theme = Theme.DARK
            setTheme(Theme.DARK)
        elif theme_name == "green":
            colors = GREEN_COLORS
            qconfig.theme = Theme.DARK
            setTheme(Theme.DARK)
        elif theme_name == "neon":
            colors = NEON_COLORS
            qconfig.theme = Theme.DARK
            setTheme(Theme.DARK)
        else: # Default or Dark
            colors = DARK_COLORS
            qconfig.theme = Theme.DARK
            setTheme(Theme.DARK)
        
        # Apply accent color to qfluentwidgets internal components
        setThemeColor(colors['accent'])


        # 2. Disable Mica/Acrylic System Effects (Full Internal Control)
        # We handle all backgrounds manually to avoid "white screen" bugs on some Windows versions
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        if hasattr(self, 'setMicaEffectEnabled'):
            self.setMicaEffectEnabled(False)
            
        # 3. Apply Main Stylesheet
        main_stylesheet = get_theme_stylesheet(colors)
        self.setStyleSheet(main_stylesheet)
        
        # 4. Apply Navigation Stylesheet & Palette
        if hasattr(self, 'navigationInterface'):
            if hasattr(self.navigationInterface, 'setAcrylicEnabled'):
                self.navigationInterface.setAcrylicEnabled(False)
            
            self.navigationInterface.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            nav_stylesheet = get_navigation_stylesheet(colors)
            self.navigationInterface.setStyleSheet(nav_stylesheet)
            apply_theme_palette(self.navigationInterface, colors)

        # 5. Apply TitleBar Stylesheet
        if hasattr(self, 'titleBar'):
            self.titleBar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            titlebar_stylesheet = get_titlebar_stylesheet(colors)
            self.titleBar.setStyleSheet(titlebar_stylesheet)
            
            # Sub-components of TitleBar
            if hasattr(self.titleBar, 'titleLabel'):
                self.titleBar.titleLabel.setStyleSheet(f"color: {colors['text_primary']}; background-color: transparent;")
        
        # 6. Apply Palette to Stacked Widget (and children)
        if hasattr(self, 'stackedWidget'):
            apply_theme_palette(self.stackedWidget, colors)
   
        # 7. Apply Palette to Window (Final Fallback)
        from PyQt6.QtGui import QPalette, QColor
        window_palette = self.palette()
        window_palette.setColor(QPalette.ColorRole.Window, QColor(colors['window_bg']))
        window_palette.setColor(QPalette.ColorRole.WindowText, QColor(colors['text_primary']))
        self.setPalette(window_palette)
        
        # Force repaint
        self.update()
        self.repaint()
        
        self.logger.info(f"Applied theme: {theme_name}")

    def _set_window_icon(self):
        """Set window icon with robust path detection."""
        from pathlib import Path
        import sys
        
        if getattr(sys, 'frozen', False):
            # PyInstaller build
            try:
                # Try onefile temp dir (only exists in --onefile mode)
                base_path = Path(sys._MEIPASS)
            except AttributeError:
                # Fallback to onedir executable dir
                base_path = Path(sys.executable).parent
            
            icon_path = base_path / "icon.ico"
        else:
            # Dev mode
            icon_path = Path(__file__).parent.parent.parent.parent / "icon.ico"
        
        # Final fallback check
        if not icon_path.exists():
            # Sometimes working directory is set to correct root
            fallback = Path.cwd() / "icon.ico"
            if fallback.exists():
                icon_path = fallback
        
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _init_interfaces(self):
        """Initialize all page interfaces."""
        # Import interfaces here to avoid circular imports
        from .home_interface import HomeInterface
        from .tools_interface import ToolsInterface
        from .settings_interface import SettingsInterface
        from .about_interface import AboutInterface
        
        # Create interface instances
        self.home_interface = HomeInterface(self.config_manager, self)
        self.tools_interface = ToolsInterface(self.config_manager, self)
        self.settings_interface = SettingsInterface(self.config_manager, self)
        self.about_interface = AboutInterface(self.config_manager, self)
        
        # Connect signals between interfaces
        self.settings_interface.debug_engines_changed.connect(
            self.home_interface._populate_engines
        )

    def _init_navigation(self):
        """Setup navigation sidebar."""
        # Add main navigation items
        self.addSubInterface(
            self.home_interface,
            FIF.HOME,
            self.config_manager.get_ui_text("nav_home", "Ana Sayfa")
        )
        
        self.addSubInterface(
            self.tools_interface,
            FIF.DEVELOPER_TOOLS,
            self.config_manager.get_ui_text("nav_tools", "Araçlar")
        )
        
        self.addSubInterface(
            self.settings_interface,
            FIF.SETTING,
            self.config_manager.get_ui_text("nav_settings", "Ayarlar")
        )
        
        # Add separator before bottom items
        self.navigationInterface.addSeparator()
        
        # Add Patreon support link at bottom
        self.navigationInterface.addItem(
            routeKey='patreon',
            icon=FIF.HEART,
            text=self.config_manager.get_ui_text("nav_support", "Destek Ol"),
            onClick=self._open_patreon,
            selectable=False,
            position=NavigationItemPosition.BOTTOM
        )
        
        # Add about at bottom
        self.addSubInterface(
            self.about_interface,
            FIF.INFO,
            self.config_manager.get_ui_text("nav_about", "Hakkında"),
            position=NavigationItemPosition.BOTTOM
        )

    def _open_patreon(self):
        """Open Patreon donation page."""
        url = QUrl("https://www.patreon.com/c/LordOfTurk")
        QDesktopServices.openUrl(url)
        
        # Show info bar
        InfoBar.success(
            title=self.config_manager.get_ui_text("patreon_thanks_title", "Teşekkürler!"),
            content=self.config_manager.get_ui_text("patreon_thanks_content", "Desteklediğiniz için teşekkür ederiz!"),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )

    def _check_for_updates(self, manual=False):
        """Check for updates in background."""
        if not manual and not getattr(self.config_manager.app_settings, 'check_for_updates', True):
            self.logger.info("Automatic update check disabled in settings")
            return
            
        self._manual_update_check = manual # Set flag before starting
        self.update_worker = UpdateCheckWorker(VERSION, self)
        self.update_worker.finished.connect(self._on_update_check_finished)
        self.update_worker.start()

    def _on_update_check_finished(self, result):
        """Handle update check results."""
        try:
            # Detect if this was a manual check (triggered from settings)
            is_manual = getattr(self, "_manual_update_check", False)
            self._manual_update_check = False # Reset flag

            # Safety check for None result
            if result is None:
                self.logger.warning("Update check returned None result")
                if is_manual:
                    self.show_info_bar(
                        "error",
                        self.config_manager.get_ui_text("error", "Hata"),
                        self.config_manager.get_ui_text("update_check_unavailable", "Güncelleme kontrolü şu anda kullanılamıyor.")
                    )
                return

            if result.error:
                self.logger.warning(f"Update check failed: {result.error}")
                if is_manual:
                    self.show_info_bar(
                        "error",
                        self.config_manager.get_ui_text("error", "Hata"),
                        self.config_manager.get_ui_text("update_check_failed", "Güncelleme kontrolü başarısız: {error}").format(error=result.error)
                    )
                return

            if result.update_available:
                self.logger.info(f"Update available: {result.latest_version}")
                
                # Show only QMessageBox (no overlapping InfoBar)
                reply = QMessageBox.information(
                    self,
                    self.config_manager.get_ui_text("update_available_title", "Update Available"),
                    self.config_manager.get_ui_text("update_available_message", "A new version {latest} is available (current: {current}). Download now?").format(latest=result.latest_version, current=VERSION),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    QDesktopServices.openUrl(QUrl(result.release_url))
            else:
                # No update available
                self.logger.info(f"Already at latest version: {VERSION}")
                if is_manual:
                    self.show_info_bar(
                        "success",
                        self.config_manager.get_ui_text("success", "Başarılı"),
                        self.config_manager.get_ui_text("update_up_to_date", "Güncelsiniz (v{current})").format(current=VERSION)
                    )
        except Exception as e:
            self.logger.error(f"Error handling update check result: {e}")
            if getattr(self, "_manual_update_check", False):
                self.show_info_bar(
                    "error",
                    self.config_manager.get_ui_text("error", "Hata"),
                    str(e)
                )

    def show_info_bar(self, level: str, title: str, content: str, duration: int = 3000):
        """Show an InfoBar notification."""
        if level == "success":
            InfoBar.success(title, content, orient=Qt.Orientation.Horizontal,
                          isClosable=True, position=InfoBarPosition.TOP,
                          duration=duration, parent=self)
        elif level == "warning":
            InfoBar.warning(title, content, orient=Qt.Orientation.Horizontal,
                          isClosable=True, position=InfoBarPosition.TOP,
                          duration=duration, parent=self)
        elif level == "error":
            InfoBar.error(title, content, orient=Qt.Orientation.Horizontal,
                         isClosable=True, position=InfoBarPosition.TOP,
                         duration=duration, parent=self)
        else:
            InfoBar.info(title, content, orient=Qt.Orientation.Horizontal,
                        isClosable=True, position=InfoBarPosition.TOP,
                        duration=duration, parent=self)

    def closeEvent(self, event):
        """Handle window close event."""
        # Save any pending settings
        try:
            self.config_manager.save_config()
        except Exception as e:
            self.logger.error(f"Error saving config on close: {e}")
        
        super().closeEvent(event)
