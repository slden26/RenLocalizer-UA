# -*- coding: utf-8 -*-
"""
RenLocalizer V2 Launcher
Cross-platform launcher for Windows and Unix systems
"""

import sys
import os
from pathlib import Path

def get_app_dir() -> Path:
    """Get the application directory - works for both dev and frozen exe."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        return Path(sys.executable).parent
    else:
        # Running in development
        return Path(__file__).parent

# Set working directory to app dir for consistent paths
APP_DIR = get_app_dir()
os.chdir(APP_DIR)

from src.version import VERSION

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    try:
        from src.gui.main_window import MainWindow
        from src.utils.config import ConfigManager
        
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QIcon
        except ImportError:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtGui import QIcon
        
        # Create application
        app = QApplication(sys.argv)
        app.setApplicationName("RenLocalizer")
        app.setApplicationVersion(VERSION)
        
        # Set application icon - use APP_DIR for frozen exe
        icon_path = APP_DIR / "icon.ico"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
        
        # Create main window
        window = MainWindow()
        window.show()
        
        # Run application
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"Error starting RenLocalizer V2: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
