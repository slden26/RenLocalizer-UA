# -*- coding: utf-8 -*-
"""
Custom Proxy Dialog
===================

Dialog to edit manual proxy list.
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QDialogButtonBox, QLabel
from PyQt6.QtCore import Qt

class CustomProxyDialog(QDialog):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        
        self.setWindowTitle(self.config_manager.get_ui_text("manual_proxies", "Manuel Proxyler"))
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        
        info_label = QLabel(self.config_manager.get_ui_text("manual_proxies_desc", "Kendi proxylerinizi buraya ekleyin (host:port)"))
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        self.text_edit = QPlainTextEdit(self)
        # Load existing proxies
        proxies = getattr(self.config_manager.proxy_settings, "manual_proxies", []) or []
        self.text_edit.setPlainText("\n".join(proxies))
        layout.addWidget(self.text_edit)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_proxies(self):
        text = self.text_edit.toPlainText()
        return [line.strip() for line in text.split('\n') if line.strip()]

    def accept(self):
        proxies = self.get_proxies()
        self.config_manager.proxy_settings.manual_proxies = proxies
        self.config_manager.save_config()
        super().accept()
