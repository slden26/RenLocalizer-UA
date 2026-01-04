"""
GUI module for RenLocalizer V2
=============================

Note: Classes are imported lazily to avoid Qt import issues.
Import them directly when needed:
    from src.gui.fluent.fluent_main import FluentMainWindow
"""

# Lazy imports - don't import at module level to avoid Qt initialization issues
__all__ = [
    'FluentMainWindow',
    'GlossaryEditorDialog',
    'UnRenModeDialog',
    'TLTranslateDialog',
    'InfoDialog',
    'CustomProxyDialog'
]

def __getattr__(name):
    """Lazy import for GUI classes."""
    if name == 'FluentMainWindow':
        from .fluent.fluent_main import FluentMainWindow
        return FluentMainWindow
    elif name == 'GlossaryEditorDialog':
        from .glossary_dialog import GlossaryEditorDialog
        return GlossaryEditorDialog
    elif name == 'UnRenModeDialog':
        from .unren_mode_dialog import UnRenModeDialog
        return UnRenModeDialog
    elif name == 'TLTranslateDialog':
        from .tl_translate_dialog import TLTranslateDialog
        return TLTranslateDialog
    elif name == 'InfoDialog':
        from .info_dialog import InfoDialog
        return InfoDialog
    elif name == 'CustomProxyDialog':
        from .proxy_dialog import CustomProxyDialog
        return CustomProxyDialog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
