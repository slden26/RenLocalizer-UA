"""
GUI module for RenLocalizer V2
=============================

Note: Classes are imported lazily to avoid Qt import issues.
Import them directly when needed:
    from src.gui.main_window import MainWindow
"""

# Lazy imports - don't import at module level to avoid Qt initialization issues
__all__ = [
    'MainWindow',
    'TranslationWorker',
    'SettingsDialog',
    'ApiKeysDialog',
    'GlossaryEditorDialog'
]

def __getattr__(name):
    """Lazy import for GUI classes."""
    if name == 'MainWindow':
        from .main_window import MainWindow
        return MainWindow
    elif name == 'TranslationWorker':
        from .translation_worker import TranslationWorker
        return TranslationWorker
    elif name == 'SettingsDialog':
        from .settings_dialog import SettingsDialog
        return SettingsDialog
    elif name == 'ApiKeysDialog':
        from .api_keys_dialog import ApiKeysDialog
        return ApiKeysDialog
    elif name == 'GlossaryEditorDialog':
        from .glossary_dialog import GlossaryEditorDialog
        return GlossaryEditorDialog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
