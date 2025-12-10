"""
Src module for RenLocalizer V2
=============================

Note: GUI modules are not imported at package level to avoid 
Qt import issues during PyInstaller bundling. Import them directly:
    from src.gui.main_window import MainWindow
"""

from . import core
from . import utils
# gui module is imported lazily to avoid Qt import at package level

__all__ = ['core', 'utils']
