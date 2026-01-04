# -*- coding: utf-8 -*-
"""
About Interface
===============

About/Help page with version info, Patreon link, and documentation.
"""

import logging
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtGui import QDesktopServices, QFont

from qfluentwidgets import (
    ScrollArea, CardWidget, PushButton, PrimaryPushButton,
    TitleLabel, BodyLabel, SubtitleLabel, StrongBodyLabel,
    HyperlinkCard, FluentIcon as FIF, InfoBar, InfoBarPosition,
    TextEdit, ImageLabel
)

from src.utils.config import ConfigManager
from src.version import VERSION


class AboutInterface(ScrollArea):
    """About and help interface."""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.parent_window = parent
        
        self.setObjectName("aboutInterface")
        self.setWidgetResizable(True)
        
        # Create main widget and layout
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(36, 20, 36, 20)
        self.scroll_layout.setSpacing(20)
        
        self._init_ui()
        self.setWidget(self.scroll_widget)

    def _init_ui(self):
        """Initialize the user interface."""
        # Banner Image
        self.banner = ImageLabel(self.scroll_widget)
        banner_path = str(Path(__file__).parent / "resources" / "banner.png")
        if Path(banner_path).exists():
            self.banner.setImage(banner_path)
            self.banner.setFixedSize(930, 300)
            self.banner.setScaledContents(True)
            self.banner.setBorderRadius(10, 10, 10, 10)
            self.scroll_layout.addWidget(self.banner, 0, Qt.AlignmentFlag.AlignCenter)
        
        # Title
        title_label = TitleLabel(self.config_manager.get_ui_text("nav_about", "Hakkında"))
        title_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self.scroll_layout.addWidget(title_label)
        
        self.scroll_layout.addSpacing(10)
        
        # App Info Card
        self._create_app_info_card()
        
        # Patreon Support Card
        self._create_patreon_card()
        
        # Features Card
        self._create_features_card()
        
        # Links Card
        self._create_links_card()
        
        # Add stretch at bottom
        self.scroll_layout.addStretch()

    def _create_app_info_card(self):
        """Create application info card."""
        card = CardWidget(self.scroll_widget)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(12)
        
        # App name and version
        app_title = TitleLabel("RenLocalizer")
        app_title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        card_layout.addWidget(app_title)
        
        version_label = SubtitleLabel(f"v{VERSION}")
        card_layout.addWidget(version_label)
        
        desc = BodyLabel(self.config_manager.get_ui_text(
            "app_description",
            "Professional Ren'Py game translation tool with integrated UnRen support, "
            "multiple translation engines, and smart batch processing."
        ))
        desc.setWordWrap(True)
        card_layout.addWidget(desc)
        
        card_layout.addSpacing(8)
        
        # Developer info
        dev_label = BodyLabel(self.config_manager.get_ui_text("developer_label", "Geliştirici: {name}").format(name="LordOfTurk"))
        card_layout.addWidget(dev_label)
        
        license_label = BodyLabel(self.config_manager.get_ui_text("license_label", "Lisans: {type}").format(type="GPL-3.0"))
        card_layout.addWidget(license_label)
        
        card_layout.addSpacing(12)
        
        # Help button
        self.help_btn = PushButton(self.config_manager.get_ui_text("show_detailed_help", "Detaylı Yardımı Göster"))
        self.help_btn.setIcon(FIF.HELP)
        self.help_btn.setFixedWidth(200)
        self.help_btn.clicked.connect(self._show_detailed_help)
        card_layout.addWidget(self.help_btn)
        
        self.scroll_layout.addWidget(card)

    def _create_patreon_card(self):
        """Create Patreon support card."""
        card = CardWidget(self.scroll_widget)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(16)
        
        # Title with heart emoji
        title_layout = QHBoxLayout()
        card_title = StrongBodyLabel("❤️ " + self.config_manager.get_ui_text("support_title", "Destek Olun"))
        card_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_layout.addWidget(card_title)
        title_layout.addStretch()
        card_layout.addLayout(title_layout)
        
        # Description
        desc = BodyLabel(self.config_manager.get_ui_text(
            "support_description",
            "RenLocalizer'ı beğendiyseniz, Patreon üzerinden bizi destekleyebilirsiniz. "
            "Desteğiniz, yeni özellikler geliştirmemize ve projeyi sürdürmemize yardımcı olur."
        ))
        desc.setWordWrap(True)
        card_layout.addWidget(desc)
        
        # Patreon button
        btn_layout = QHBoxLayout()
        
        patreon_btn = PrimaryPushButton("🎁 " + self.config_manager.get_ui_text("support_patreon", "Patreon'da Destek Ol"))
        patreon_btn.setIcon(FIF.HEART)
        patreon_btn.clicked.connect(self._open_patreon)
        btn_layout.addWidget(patreon_btn)
        
        btn_layout.addStretch()
        card_layout.addLayout(btn_layout)
        
        self.scroll_layout.addWidget(card)

    def _create_features_card(self):
        """Create features info card."""
        card = CardWidget(self.scroll_widget)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(12)
        
        # Title
        card_title = StrongBodyLabel("✨ " + self.config_manager.get_ui_text("features_title", "Özellikler"))
        card_layout.addWidget(card_title)
        
        # Features list
        features = [
            ("🔓", self.config_manager.get_ui_text("feature_unren", "Entegre UnRen desteği - .rpa ve .rpyc dosyalarını otomatik açar")),
            ("🌐", self.config_manager.get_ui_text("feature_google", "Google Translate - Ücretsiz, hızlı, 100+ dil desteği")),
            ("🔷", self.config_manager.get_ui_text("feature_deepl", "DeepL API - Yüksek kaliteli çeviriler (API key gerektirir)")),
            ("⚡", self.config_manager.get_ui_text("feature_batch", "Akıllı batch işleme - Hızlı ve verimli çeviri")),
            ("🔄", self.config_manager.get_ui_text("feature_fuzzy", "Fuzzy matching - Mevcut çevirileri güncelle")),
            ("📝", self.config_manager.get_ui_text("feature_glossary", "Özel sözlük desteği - Tutarlı terminoloji")),
            ("🧪", self.config_manager.get_ui_text("feature_pseudo", "Pseudo-localization - UI testi için")),
        ]
        
        for icon, text in features:
            feature_label = BodyLabel(f"{icon} {text}")
            feature_label.setWordWrap(True)
            card_layout.addWidget(feature_label)
        
        self.scroll_layout.addWidget(card)

    def _create_links_card(self):
        """Create external links card."""
        card = CardWidget(self.scroll_widget)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(12)
        
        # Title
        card_title = StrongBodyLabel("🔗 " + self.config_manager.get_ui_text("links_title", "Bağlantılar"))
        card_layout.addWidget(card_title)
        
        # Links buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        github_btn = PushButton(self.config_manager.get_ui_text("github", "GitHub"))
        github_btn.setIcon(FIF.GITHUB)
        github_btn.clicked.connect(lambda: self._on_link_clicked("https://github.com/Lord0fTurk/RenLocalizer", "GitHub"))
        btn_layout.addWidget(github_btn)
        
        docs_btn = PushButton(self.config_manager.get_ui_text("documentation", "Dokümantasyon"))
        docs_btn.setIcon(FIF.DOCUMENT)
        docs_btn.clicked.connect(lambda: self._on_link_clicked("https://github.com/Lord0fTurk/RenLocalizer/wiki", "Dokümantasyon"))
        btn_layout.addWidget(docs_btn)
        
        issues_btn = PushButton(self.config_manager.get_ui_text("report_issue", "Hata Bildir"))
        issues_btn.setIcon(FIF.FEEDBACK)
        issues_btn.clicked.connect(lambda: self._on_link_clicked("https://github.com/Lord0fTurk/RenLocalizer/issues", "Hata Bildir"))
        btn_layout.addWidget(issues_btn)
        
        btn_layout.addStretch()
        card_layout.addLayout(btn_layout)
        
        self.scroll_layout.addWidget(card)

    def _on_link_clicked(self, url: str, label: str):
        """Handle link click with notification."""
        self._open_url(url)
        if self.parent_window:
            self.parent_window.show_info_bar(
                "info",
                self.config_manager.get_ui_text("opening_link", "Bağlantı Açılıyor"),
                f"{label}: {url}",
                duration=2000
            )

    def _open_patreon(self):
        """Open Patreon donation page."""
        patreon_url = "https://www.patreon.com/c/LordOfTurk"
        self._on_link_clicked(patreon_url, "Patreon")
        
        # Show thanks InfoBar (already handled by _on_link_clicked but we want a special one for Patreon)
        if self.parent_window:
            self.parent_window.show_info_bar(
                "success",
                self.config_manager.get_ui_text("patreon_thanks_title", "Teşekkürler!"),
                self.config_manager.get_ui_text("patreon_thanks_content", "Desteklediğiniz için teşekkür ederiz!")
            )

    def _show_detailed_help(self):
        """Show the detailed Information dialog."""
        if self.parent_window:
            self.parent_window.show_info_bar(
                "info",
                self.config_manager.get_ui_text("info", "Bilgi"),
                self.config_manager.get_ui_text("showing_help", "Detaylı yardım penceresi açılıyor...")
            )
        from src.gui.info_dialog import InfoDialog
        dialog = InfoDialog(self)
        dialog.exec()

    def _open_url(self, url: str):
        """Open URL in default browser."""
        QDesktopServices.openUrl(QUrl(url))
