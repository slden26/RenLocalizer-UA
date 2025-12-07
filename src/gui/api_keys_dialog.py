"""
API Keys Dialog
==============

Dialog for managing API keys for translation services.
"""

import logging

try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit, 
        QPushButton, QDialogButtonBox, QGroupBox, QTextEdit,
        QHBoxLayout, QMessageBox, QTabWidget
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont, QIcon
except ImportError:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit, 
        QPushButton, QDialogButtonBox, QGroupBox, QTextEdit,
        QHBoxLayout, QMessageBox, QTabWidget
    )
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QIcon

from src.utils.config import ConfigManager
from src.gui.professional_themes import get_theme_qss

class ApiKeysDialog(QDialog):
    """Dialog for managing API keys."""
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        self.init_ui()
        self.load_api_keys()
        self.apply_theme()
    
    def apply_theme(self):
        """Apply current theme to dialog."""
        current_theme = self.config_manager.get_setting('ui.theme', 'dark')
        qss = get_theme_qss(current_theme)
        self.setStyleSheet(qss)
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("API Anahtarları")  # API Keys in Turkish
        self.setModal(True)
        
        # Set dialog icon
        from pathlib import Path
        icon_path = Path(__file__).parent.parent.parent / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel(self.tr(
            "Enter your API keys for translation services. "
            "Free services (like Google Translate web) don't require API keys."
        ))
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create tabs for each service
        self.create_google_tab()
        self.create_deepl_tab()
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def create_google_tab(self):
        """Create Google Translate API tab."""
        widget = QGroupBox()
        layout = QVBoxLayout(widget)
        
        # Info
        info = QLabel(self.tr(
            "Google Translate API provides high-quality translations with support for many languages.\\n"
            "Note: The free web version is used by default and doesn't require an API key."
        ))
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # API Key input
        form_layout = QFormLayout()
        self.google_key_input = QLineEdit()
        self.google_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.google_key_input.setPlaceholderText("AIza...")
        form_layout.addRow(self.tr("API Key:"), self.google_key_input)
        layout.addLayout(form_layout)
        
        # Show/Hide button
        show_button = QPushButton(self.tr("Show/Hide"))
        show_button.clicked.connect(lambda: self.toggle_password_visibility(self.google_key_input))
        form_layout.addWidget(show_button)
        
        # Instructions
        instructions = QTextEdit()
        instructions.setMaximumHeight(150)
        instructions.setReadOnly(True)
        instructions.setHtml(self.tr(
            "<b>How to get Google Translate API key:</b><br>"
            "1. Go to <a href='https://console.cloud.google.com/'>Google Cloud Console</a><br>"
            "2. Create a new project or select existing one<br>"
            "3. Enable the 'Cloud Translation API'<br>"
            "4. Go to 'Credentials' and create an API key<br>"
            "5. Copy the API key and paste it above<br><br>"
            "<b>Note:</b> Google Cloud Translation API is a paid service."
        ))
        layout.addWidget(instructions)
        
        self.tab_widget.addTab(widget, "Google")
    
    def create_deepl_tab(self):
        """Create DeepL API tab."""
        widget = QGroupBox()
        layout = QVBoxLayout(widget)
        
        # Info
        info = QLabel(self.tr(
            "DeepL provides high-quality translations, especially for European languages.\\n"
            "They offer both free and pro plans."
        ))
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # API Key input
        form_layout = QFormLayout()
        self.deepl_key_input = QLineEdit()
        self.deepl_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.deepl_key_input.setPlaceholderText("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:fx")
        form_layout.addRow(self.tr("API Key:"), self.deepl_key_input)
        layout.addLayout(form_layout)
        
        # Show/Hide button
        show_button = QPushButton(self.tr("Show/Hide"))
        show_button.clicked.connect(lambda: self.toggle_password_visibility(self.deepl_key_input))
        form_layout.addWidget(show_button)
        
        # Instructions
        instructions = QTextEdit()
        instructions.setMaximumHeight(150)
        instructions.setReadOnly(True)
        instructions.setHtml(self.tr(
            "<b>How to get DeepL API key:</b><br>"
            "1. Go to <a href='https://www.deepl.com/pro-api'>DeepL API</a><br>"
            "2. Sign up for a free or paid account<br>"
            "3. Go to your account settings<br>"
            "4. Find the 'API' section<br>"
            "5. Copy your authentication key<br><br>"
            "<b>Free plan:</b> 500,000 characters/month<br>"
            "<b>Pro plan:</b> Starts at $6.99/month"
        ))
        layout.addWidget(instructions)
        
        self.tab_widget.addTab(widget, "DeepL")
    
    
    def toggle_password_visibility(self, line_edit: QLineEdit):
        """Toggle password visibility for a line edit."""
        if line_edit.echoMode() == QLineEdit.EchoMode.Password:
            line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            line_edit.setEchoMode(QLineEdit.EchoMode.Password)
    
    def load_api_keys(self):
        """Load existing API keys."""
        self.google_key_input.setText(self.config_manager.get_api_key("google"))
        self.deepl_key_input.setText(self.config_manager.get_api_key("deepl"))
    
    def save_api_keys(self):
        """Save API keys to configuration."""
        self.config_manager.set_api_key("google", self.google_key_input.text().strip())
        self.config_manager.set_api_key("deepl", self.deepl_key_input.text().strip())
        
        self.logger.info("API keys saved")
    
    def accept(self):
        """Accept and save API keys."""
        self.save_api_keys()
        super().accept()
    
    def tr(self, text: str) -> str:
        """Translate UI text."""
        return self.config_manager.get_ui_text(text)
