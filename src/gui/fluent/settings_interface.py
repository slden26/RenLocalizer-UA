# -*- coding: utf-8 -*-
"""
Settings Interface
==================

Settings page with Fluent SettingCards for all application configurations.
"""

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog

from qfluentwidgets import (
    ScrollArea, ExpandLayout, SettingCardGroup, PushSettingCard,
    SwitchSettingCard, PrimaryPushSettingCard, HyperlinkCard,
    SettingCard, ComboBox, Slider, LineEdit, PasswordLineEdit,
    FluentIcon as FIF, TitleLabel, BodyLabel, InfoBar, InfoBarPosition,
    qconfig, MessageBox
)
from qfluentwidgets import TextEdit

from src.utils.config import ConfigManager, Language


class SettingsInterface(ScrollArea):
    """Settings interface with Fluent SettingCards."""
    
    # Signal emitted when language changes
    language_changed = pyqtSignal()
    # Signal emitted when debug engines toggle changes
    debug_engines_changed = pyqtSignal(bool)

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.parent_window = parent
        
        self.setObjectName("settingsInterface")
        self.setWidgetResizable(True)
        
        # Create main widget and layout
        self.scroll_widget = QWidget()
        self.expand_layout = ExpandLayout(self.scroll_widget)
        self.expand_layout.setContentsMargins(36, 20, 36, 20)
        self.expand_layout.setSpacing(28)
        
        self._init_ui()
        self.setWidget(self.scroll_widget)

    def _init_ui(self):
        """Initialize the user interface."""
        # Title
        title_label = TitleLabel(self.config_manager.get_ui_text("nav_settings", "Ayarlar"))
        self.expand_layout.addWidget(title_label)
        
        # General Settings Group
        self._create_general_group()
        
        # Translation Settings Group
        self._create_translation_group()
        
        # API Keys Group
        self._create_api_keys_group()
        
        # Proxy Settings Group
        self._create_proxy_group()
        
        # Advanced Settings Group
        self._create_advanced_group()

    def _create_general_group(self):
        """Create general settings group."""
        self.general_group = SettingCardGroup(
            self.config_manager.get_ui_text("settings_general", "Genel Ayarlar"),
            self.scroll_widget
        )
        
        # Application Language
        self.language_card = SettingCard(
            icon=FIF.LANGUAGE,
            title=self.config_manager.get_ui_text("ui_language", "Uygulama Dili"),
            content=self.config_manager.get_ui_text("ui_language_desc", "Arayüz dilini değiştir"),
            parent=self.general_group
        )
        self.language_combo = ComboBox(self.language_card)
        # Populate languages dynamically from ConfigManager
        # Use limited UI language options (Turkish, English, Russian)
        all_langs = self.config_manager.get_ui_language_options()
        self._ui_lang_codes = [item['api'] for item in all_langs]
        ui_labels = [item['native'] for item in all_langs]
        self.language_combo.addItems(ui_labels)
        self.language_combo.setFixedWidth(160)
        self.language_card.hBoxLayout.addWidget(self.language_combo, 0, Qt.AlignmentFlag.AlignRight)
        self.language_card.hBoxLayout.addSpacing(16)
        
        # Set current language
        current_lang = self.config_manager.app_settings.ui_language
        try:
            idx = self._ui_lang_codes.index(current_lang)
        except ValueError:
            idx = 0
        self.language_combo.setCurrentIndex(idx)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        self.general_group.addSettingCard(self.language_card)
        
        # Application Theme (requires restart for consistent rendering)
        self.theme_card = SettingCard(
            icon=FIF.CONSTRACT,
            title=self.config_manager.get_ui_text("app_theme", "Uygulama Teması"),
            content=self.config_manager.get_ui_text("app_theme_desc", "Arayüz renklerini değiştir (Windows ayarlarından bağımsız)"),
            parent=self.general_group
        )
        
        # Theme mapping (index -> theme_key)
        self.THEME_MAP = [
            ("dark", self.config_manager.get_ui_text("theme_dark", "🌙 Koyu")),
            ("light", self.config_manager.get_ui_text("theme_light", "☀️ Açık")),
            ("red", self.config_manager.get_ui_text("theme_red", "🔴 Kırmızı")),
            ("turquoise", self.config_manager.get_ui_text("theme_turquoise", "🔵 Turkuaz")),
            ("green", self.config_manager.get_ui_text("theme_green", "🌿 Yeşil")),
            ("neon", self.config_manager.get_ui_text("theme_neon", "🌈 Neon")),
        ]
        
        self.theme_combo = ComboBox(self.theme_card)
        for theme_key, theme_label in self.THEME_MAP:
            self.theme_combo.addItem(theme_label)
        self.theme_combo.setFixedWidth(150)
        self.theme_card.hBoxLayout.addWidget(self.theme_combo, 0, Qt.AlignmentFlag.AlignRight)
        self.theme_card.hBoxLayout.addSpacing(16)
        
        # Set current theme from config
        start_theme = getattr(self.config_manager.app_settings, 'app_theme', 'dark')
        # Find index for the current theme
        start_index = 0
        for i, (theme_key, _) in enumerate(self.THEME_MAP):
            if theme_key == start_theme:
                start_index = i
                break
        self.theme_combo.setCurrentIndex(start_index)
            
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self.general_group.addSettingCard(self.theme_card)
        
        # Check for Updates
        self.check_updates_card = SwitchSettingCard(
            icon=FIF.UPDATE,
            title=self.config_manager.get_ui_text("check_updates", "Güncellemeleri Kontrol Et"),
            content=self.config_manager.get_ui_text("check_updates_desc", "Uygulama açılışında yeni sürüm kontrolü yap"),
            parent=self.general_group
        )
        self.check_updates_card.switchButton.setChecked(self.config_manager.app_settings.check_for_updates)
        self.check_updates_card.switchButton.checkedChanged.connect(self._on_check_updates_changed)
        self.general_group.addSettingCard(self.check_updates_card)
        
        # Manual Check for updates button
        self.check_now_card = PushSettingCard(
            text=self.config_manager.get_ui_text("check_updates_now_button", "Kontrol Et"),
            icon=FIF.SYNC,
            title=self.config_manager.get_ui_text("check_updates_now_label", "Şimdi Kontrol Et"),
            content=self.config_manager.get_ui_text("check_updates_now_tooltip", "Güncellemeleri şimdi manuel olarak tara"),
            parent=self.general_group
        )
        self.check_now_card.clicked.connect(self._check_updates_now)
        self.general_group.addSettingCard(self.check_now_card)
        
        # Output Format setting removed - defaulting to 'old_new' always
        
        self.expand_layout.addWidget(self.general_group)

    def _create_translation_group(self):
        """Create translation settings group."""
        self.translation_group = SettingCardGroup(
            self.config_manager.get_ui_text("settings_translation", "Çeviri Ayarları"),
            self.scroll_widget
        )
        
        # Batch size
        self.batch_size_card = SettingCard(
            icon=FIF.TILES,
            title=self.config_manager.get_ui_text("batch_size", "Batch Boyutu"),
            content=self.config_manager.get_ui_text("batch_size_desc", "Aynı anda çevrilecek metin sayısı"),
            parent=self.translation_group
        )
        self.batch_size_slider = Slider(Qt.Orientation.Horizontal, self.batch_size_card)
        self.batch_size_slider.setRange(1, 500)
        self.batch_size_slider.setFixedWidth(200)
        self.batch_size_label = BodyLabel(str(self.config_manager.translation_settings.max_batch_size), self.batch_size_card)
        
        self.batch_size_card.hBoxLayout.addWidget(self.batch_size_label, 0, Qt.AlignmentFlag.AlignRight)
        self.batch_size_card.hBoxLayout.addSpacing(8)
        self.batch_size_card.hBoxLayout.addWidget(self.batch_size_slider, 0, Qt.AlignmentFlag.AlignRight)
        self.batch_size_card.hBoxLayout.addSpacing(16)
        
        self.batch_size_slider.setValue(self.config_manager.translation_settings.max_batch_size)
        self.batch_size_slider.valueChanged.connect(self._on_batch_size_slider_changed)
        self.translation_group.addSettingCard(self.batch_size_card)
        
        # Max concurrent requests
        self.concurrent_card = SettingCard(
            icon=FIF.SPEED_HIGH,
            title=self.config_manager.get_ui_text("max_concurrent", "Eşzamanlı İstek"),
            content=self.config_manager.get_ui_text("max_concurrent_desc", "Aynı anda yapılacak maksimum istek sayısı"),
            parent=self.translation_group
        )
        self.concurrent_slider = Slider(Qt.Orientation.Horizontal, self.concurrent_card)
        self.concurrent_slider.setRange(1, 64)
        self.concurrent_slider.setFixedWidth(200)
        self.concurrent_label = BodyLabel(str(self.config_manager.translation_settings.max_concurrent_threads), self.concurrent_card)
        
        self.concurrent_card.hBoxLayout.addWidget(self.concurrent_label, 0, Qt.AlignmentFlag.AlignRight)
        self.concurrent_card.hBoxLayout.addSpacing(8)
        self.concurrent_card.hBoxLayout.addWidget(self.concurrent_slider, 0, Qt.AlignmentFlag.AlignRight)
        self.concurrent_card.hBoxLayout.addSpacing(16)
        
        self.concurrent_slider.setValue(self.config_manager.translation_settings.max_concurrent_threads)
        self.concurrent_slider.valueChanged.connect(self._on_concurrent_slider_changed)
        self.translation_group.addSettingCard(self.concurrent_card)
        
        # Retry count
        self.retry_card = SettingCard(
            icon=FIF.SYNC,
            title=self.config_manager.get_ui_text("retry_count", "Yeniden Deneme"),
            content=self.config_manager.get_ui_text("retry_count_desc", "Hata durumunda yeniden deneme sayısı"),
            parent=self.translation_group
        )
        self.retry_slider = Slider(Qt.Orientation.Horizontal, self.retry_card)
        self.retry_slider.setRange(1, 10)
        self.retry_slider.setFixedWidth(200)
        self.retry_label = BodyLabel(str(self.config_manager.translation_settings.max_retries), self.retry_card)
        
        self.retry_card.hBoxLayout.addWidget(self.retry_label, 0, Qt.AlignmentFlag.AlignRight)
        self.retry_card.hBoxLayout.addSpacing(8)
        self.retry_card.hBoxLayout.addWidget(self.retry_slider, 0, Qt.AlignmentFlag.AlignRight)
        self.retry_card.hBoxLayout.addSpacing(16)
        
        self.retry_slider.setValue(self.config_manager.translation_settings.max_retries)
        self.retry_slider.valueChanged.connect(self._on_retry_slider_changed)
        self.translation_group.addSettingCard(self.retry_card)
        
        # Glossary editor
        self.glossary_card = PushSettingCard(
            text=self.config_manager.get_ui_text("edit", "Düzenle"),
            icon=FIF.BOOK_SHELF,
            title=self.config_manager.get_ui_text("glossary", "Sözlük"),
            content=self.config_manager.get_ui_text("glossary_desc", "Özel çeviri terimleri tanımla"),
            parent=self.translation_group
        )
        self.glossary_card.clicked.connect(self._open_glossary_editor)
        self.translation_group.addSettingCard(self.glossary_card)
        
        self.expand_layout.addWidget(self.translation_group)

    def _create_api_keys_group(self):
        """Create API keys settings group."""
        self.api_group = SettingCardGroup(
            self.config_manager.get_ui_text("settings_api", "API Anahtarları"),
            self.scroll_widget
        )
        
        # Google API Key (though usually not needed for web version, some apps use it)
        self.google_api_card = SettingCard(
            icon=FIF.GLOBE,
            title=self.config_manager.get_ui_text("google_api_title", "Google Translate API Key"),
            content=self.config_manager.get_ui_text("google_api_desc", "Free web version doesn't require API key"),
            parent=self.api_group
        )
        self.google_key_input = PasswordLineEdit(self.google_api_card)
        self.google_key_input.setFixedWidth(300)
        self.google_key_input.setText(self.config_manager.api_keys.google_api_key)
        self.google_key_input.textChanged.connect(lambda v: self._on_api_key_changed("google", v))
        self.google_api_card.hBoxLayout.addWidget(self.google_key_input, 0, Qt.AlignmentFlag.AlignRight)
        self.google_api_card.hBoxLayout.addSpacing(16)
        self.api_group.addSettingCard(self.google_api_card)
        
        # DeepL API Key
        self.deepl_api_card = SettingCard(
            icon=FIF.DICTIONARY,
            title=self.config_manager.get_ui_text("deepl_api_title", "DeepL API Key"),
            content=self.config_manager.get_ui_text("deepl_api_desc", "API key required for high quality translations"),
            parent=self.api_group
        )
        self.deepl_key_input = PasswordLineEdit(self.deepl_api_card)
        self.deepl_key_input.setFixedWidth(300)
        self.deepl_key_input.setText(self.config_manager.api_keys.deepl_api_key)
        self.deepl_key_input.textChanged.connect(lambda v: self._on_api_key_changed("deepl", v))
        self.deepl_api_card.hBoxLayout.addWidget(self.deepl_key_input, 0, Qt.AlignmentFlag.AlignRight)
        self.deepl_api_card.hBoxLayout.addSpacing(16)
        self.api_group.addSettingCard(self.deepl_api_card)
        
        # OpenRouter API Key
        self.openrouter_api_card = SettingCard(
            icon=FIF.GLOBE,
            title=self.config_manager.get_ui_text("openrouter_api_title", "OpenRouter API Key"),
            content=self.config_manager.get_ui_text("openrouter_api_desc", "API key for OpenRouter (required for model access)"),
            parent=self.api_group
        )
        self.openrouter_key_input = PasswordLineEdit(self.openrouter_api_card)
        self.openrouter_key_input.setFixedWidth(300)
        self.openrouter_key_input.setText(self.config_manager.api_keys.openrouter_api_key)
        self.openrouter_key_input.textChanged.connect(lambda v: self._on_api_key_changed("openrouter", v))
        self.openrouter_api_card.hBoxLayout.addWidget(self.openrouter_key_input, 0, Qt.AlignmentFlag.AlignRight)
        self.openrouter_api_card.hBoxLayout.addSpacing(16)
        self.api_group.addSettingCard(self.openrouter_api_card)

        # OpenRouter Model Selection
        self.openrouter_model_card = SettingCard(
            icon=FIF.BOOK_SHELF,
            title=self.config_manager.get_ui_text("openrouter_model_title", "OpenRouter Model"),
            content=self.config_manager.get_ui_text("openrouter_model_desc", "Enter OpenRouter model (e.g. google/gemini-2.0-flash-exp:free)"),
            parent=self.api_group
        )
        # Use a free-form LineEdit so user can paste their model identifier
        self.openrouter_model_input = LineEdit(self.openrouter_model_card)
        cur_model = getattr(self.config_manager.translation_settings, 'openrouter_model', '') or ''
        self.openrouter_model_input.setFixedWidth(360)
        self.openrouter_model_input.setText(cur_model)
        self.openrouter_model_card.hBoxLayout.addWidget(self.openrouter_model_input, 0, Qt.AlignmentFlag.AlignRight)
        self.openrouter_model_card.hBoxLayout.addSpacing(16)
        self.openrouter_model_input.textChanged.connect(lambda v: self._on_openrouter_model_text_changed(v))
        self.api_group.addSettingCard(self.openrouter_model_card)

        # System prompt for OpenRouter
        self.openrouter_sysprompt_card = SettingCard(
            icon=FIF.BOOK_SHELF,
            title=self.config_manager.get_ui_text("openrouter_system_prompt_title", "OpenRouter System Prompt"),
            content=self.config_manager.get_ui_text("openrouter_system_prompt_desc", "Optional system prompt passed to the model (helps control behavior)."),
            parent=self.api_group
        )
        self.openrouter_sysprompt_input = LineEdit(self.openrouter_sysprompt_card)
        cur_sp = getattr(self.config_manager.translation_settings, 'openrouter_system_prompt', '') or ''
        self.openrouter_sysprompt_input.setFixedWidth(600)
        self.openrouter_sysprompt_input.setText(cur_sp)
        self.openrouter_sysprompt_card.hBoxLayout.addWidget(self.openrouter_sysprompt_input, 0, Qt.AlignmentFlag.AlignRight)
        self.openrouter_sysprompt_card.hBoxLayout.addSpacing(16)
        self.openrouter_sysprompt_input.textChanged.connect(lambda v: self._on_openrouter_sysprompt_changed(v))
        self.api_group.addSettingCard(self.openrouter_sysprompt_card)

        # Temperature slider
        self.openrouter_temp_card = SettingCard(
            icon=FIF.SPEED_HIGH,
            title=self.config_manager.get_ui_text("openrouter_temperature_title", "OpenRouter Temperature"),
            content=self.config_manager.get_ui_text("openrouter_temperature_desc", "Sampling temperature for model (0.0 - 2.0)."),
            parent=self.api_group
        )
        self.openrouter_temp_slider = Slider(Qt.Orientation.Horizontal, self.openrouter_temp_card)
        self.openrouter_temp_slider.setRange(0, 200)
        self.openrouter_temp_slider.setFixedWidth(200)
        # Label to show float value
        cur_temp = getattr(self.config_manager.translation_settings, 'openrouter_temperature', 0.0)
        self.openrouter_temp_label = BodyLabel(str(cur_temp), self.openrouter_temp_card)
        self.openrouter_temp_card.hBoxLayout.addWidget(self.openrouter_temp_label, 0, Qt.AlignmentFlag.AlignRight)
        self.openrouter_temp_card.hBoxLayout.addSpacing(8)
        self.openrouter_temp_card.hBoxLayout.addWidget(self.openrouter_temp_slider, 0, Qt.AlignmentFlag.AlignRight)
        self.openrouter_temp_card.hBoxLayout.addSpacing(16)
        # Initialize slider position
        try:
            pos = int(round(float(cur_temp) * 100))
        except Exception:
            pos = 0
        self.openrouter_temp_slider.setValue(pos)
        self.openrouter_temp_slider.valueChanged.connect(self._on_openrouter_temp_changed)
        self.api_group.addSettingCard(self.openrouter_temp_card)
        
        self.expand_layout.addWidget(self.api_group)

    def _create_proxy_group(self):
        """Create proxy settings group."""
        self.proxy_group = SettingCardGroup(
            self.config_manager.get_ui_text("settings_proxy", "Proxy Ayarları"),
            self.scroll_widget
        )
        
        # Enable proxy
        self.proxy_enabled_card = SwitchSettingCard(
            icon=FIF.VPN,
            title=self.config_manager.get_ui_text("proxy_enabled", "Proxy Kullan"),
            content=self.config_manager.get_ui_text("proxy_enabled_desc", "Çeviri isteklerinde proxy kullan"),
            configItem=None,
            parent=self.proxy_group
        )
        self.proxy_enabled_card.switchButton.setChecked(self.config_manager.proxy_settings.enabled)
        self.proxy_enabled_card.switchButton.checkedChanged.connect(self._on_proxy_enabled_changed)
        self.proxy_group.addSettingCard(self.proxy_enabled_card)
        
        # Refresh proxies button
        self.refresh_proxy_card = PushSettingCard(
            text=self.config_manager.get_ui_text("refresh", "Yenile"),
            icon=FIF.SYNC,
            title=self.config_manager.get_ui_text("refresh_proxies", "Proxy Listesini Yenile"),
            content=self.config_manager.get_ui_text("refresh_proxies_desc", "Ücretsiz proxy listesini güncelle"),
            parent=self.proxy_group
        )
        self.refresh_proxy_card.clicked.connect(self._refresh_proxies)
        self.proxy_group.addSettingCard(self.refresh_proxy_card)
        
        # Manual proxies
        self.manual_proxy_card = PushSettingCard(
            text=self.config_manager.get_ui_text("edit", "Düzenle"),
            icon=FIF.EDIT,
            title=self.config_manager.get_ui_text("manual_proxies", "Manuel Proxyler"),
            content=self.config_manager.get_ui_text("manual_proxies_desc", "Kendi proxylerinizi buraya ekle"),
            parent=self.proxy_group
        )
        self.manual_proxy_card.clicked.connect(self._open_custom_proxy_dialog)
        self.proxy_group.addSettingCard(self.manual_proxy_card)
        
        self.expand_layout.addWidget(self.proxy_group)

    def _create_advanced_group(self):
        """Create advanced settings group."""
        self.advanced_group = SettingCardGroup(
            self.config_manager.get_ui_text("settings_advanced", "Gelişmiş"),
            self.scroll_widget
        )
        
        # Auto UnRen
        self.auto_unren_card = SwitchSettingCard(
            icon=FIF.COMMAND_PROMPT,
            title=self.config_manager.get_ui_text("auto_unren", "Otomatik UnRen"),
            content=self.config_manager.get_ui_text("auto_unren_desc", "Gerektiğinde otomatik olarak UnRen çalıştır"),
            configItem=None,
            parent=self.advanced_group
        )
        self.auto_unren_card.switchButton.setChecked(self.config_manager.app_settings.unren_auto_download)
        self.auto_unren_card.switchButton.checkedChanged.connect(self._on_auto_unren_changed)
        self.advanced_group.addSettingCard(self.auto_unren_card)
        
        # UnRen path
        self.unren_path_card = PushSettingCard(
            text=self.config_manager.get_ui_text("browse", "Gözat"),
            icon=FIF.FOLDER,
            title=self.config_manager.get_ui_text("unren_path", "UnRen Yolu"),
            content=self.config_manager.app_settings.unren_custom_path or self.config_manager.get_ui_text("unren_path_default", "Varsayılan konum"),
            parent=self.advanced_group
        )
        self.unren_path_card.clicked.connect(self._browse_unren_path)
        self.advanced_group.addSettingCard(self.unren_path_card)
        
        # Deep scan
        self.deep_scan_card = SwitchSettingCard(
            icon=FIF.SEARCH,
            title=self.config_manager.get_ui_text("deep_scan", "Derin Tarama"),
            content=self.config_manager.get_ui_text("deep_scan_desc", "RPYC dosyalarını AST ile analiz et (yavaş)"),
            configItem=None,
            parent=self.advanced_group
        )
        self.deep_scan_card.switchButton.setChecked(
            self.config_manager.translation_settings.enable_deep_scan
        )
        self.deep_scan_card.switchButton.checkedChanged.connect(self._on_deep_scan_changed)
        self.advanced_group.addSettingCard(self.deep_scan_card)
        
        # Show Debug Engines
        self.debug_engines_card = SwitchSettingCard(
            icon=FIF.DEVELOPER_TOOLS,
            title=self.config_manager.get_ui_text("show_debug_engines", "Hata Ayıklama Motorlarını Göster"),
            content=self.config_manager.get_ui_text("show_debug_engines_desc", "Pseudo-Localization gibi geliştirici araçlarını ana listede göster"),
            configItem=None,
            parent=self.advanced_group
        )
        self.debug_engines_card.switchButton.setChecked(
            getattr(self.config_manager.translation_settings, 'show_debug_engines', False)
        )
        self.debug_engines_card.switchButton.checkedChanged.connect(self._on_debug_engines_changed)
        self.advanced_group.addSettingCard(self.debug_engines_card)
        
        # Restore defaults
        self.restore_defaults_card = PrimaryPushSettingCard(
            text=self.config_manager.get_ui_text("restore_defaults", "Varsayılanlara Dön"),
            icon=FIF.HISTORY,
            title=self.config_manager.get_ui_text("restore_defaults_title", "Ayarları Sıfırla"),
            content=self.config_manager.get_ui_text("restore_defaults_desc", "Tüm ayarları varsayılan değerlere döndür"),
            parent=self.advanced_group
        )
        self.restore_defaults_card.clicked.connect(self._restore_defaults)
        self.advanced_group.addSettingCard(self.restore_defaults_card)
        
        self.expand_layout.addWidget(self.advanced_group)

    # ==================== Event Handlers ====================

    def _on_language_changed(self, index: int):
        """Handle language change."""
        # Map selected index to API language code saved in config
        try:
            new_lang = self._ui_lang_codes[index]
        except Exception:
            new_lang = self.config_manager.app_settings.ui_language or 'en'
        self.config_manager.app_settings.ui_language = new_lang
        self.config_manager.save_config()
        
        # Emit signal
        self.language_changed.emit()
        
        # Show restart notification
        if self.parent_window:
            self.parent_window.show_info_bar(
                "info",
                self.config_manager.get_ui_text("language_changed", "Dil Değiştirildi"),
                self.config_manager.get_ui_text("language_restart", "Değişikliklerin tam olarak uygulanması için uygulamayı yeniden başlatın.")
            )


    def _on_theme_changed(self, index: int):
        """Handle theme change - applies immediately using index-based mapping."""
        # Get theme key from index using THEME_MAP
        if index < 0 or index >= len(self.THEME_MAP):
            new_theme = "dark"
        else:
            new_theme = self.THEME_MAP[index][0]
        
        print(f"[Theme] User selected index {index} -> theme: {new_theme}")  # Debug
        
        # Save to config
        self.config_manager.app_settings.app_theme = new_theme
        self.config_manager.save_config()
        
        # Apply theme immediately
        applied = False
        if self.parent_window and hasattr(self.parent_window, 'apply_theme'):
            print(f"[Theme] Applying via parent_window.apply_theme()")
            self.parent_window.apply_theme(new_theme)
            applied = True
        
        # Show info bar
        if self.parent_window and applied:
            self.parent_window.show_info_bar(
                "success",
                self.config_manager.get_ui_text("theme_changed", "Tema Güncellendi"),
                self.config_manager.get_ui_text("theme_applied", "Tema başarıyla uygulandı.")
            )

    def _on_update_check_changed(self, checked: bool):
        """Handle update check toggle."""
        self.config_manager.app_settings.check_for_updates = checked
        self.config_manager.save_config()


    def _on_api_key_changed(self, service: str, value: str):
        """Handle API key change."""
        self.config_manager.set_api_key(service, value)

    def _on_openrouter_model_changed(self, index: int, models: list):
        """Handle OpenRouter model selection change."""
        try:
            model = models[index]
        except Exception:
            model = getattr(self.config_manager.translation_settings, 'openrouter_model', '')
        self.config_manager.translation_settings.openrouter_model = model
        self.config_manager.save_config()

    def _on_openrouter_model_text_changed(self, text: str):
        """Handle free-form OpenRouter model text change."""
        try:
            self.config_manager.translation_settings.openrouter_model = text.strip()
            self.config_manager.save_config()
        except Exception:
            pass

    def _on_openrouter_sysprompt_changed(self, text: str):
        try:
            self.config_manager.translation_settings.openrouter_system_prompt = text
            self.config_manager.save_config()
        except Exception:
            pass

    def _on_openrouter_temp_changed(self, value: int):
        # slider value is 0..200 -> map to 0.00..2.00
        temp = round(value / 100.0, 2)
        try:
            self.openrouter_temp_label.setText(str(temp))
        except Exception:
            pass
        try:
            self.config_manager.translation_settings.openrouter_temperature = float(temp)
            self.config_manager.save_config()
        except Exception:
            pass

    def _on_batch_size_slider_changed(self, value: int):
        """Handle batch size slider change."""
        self.batch_size_label.setText(str(value))
        self.config_manager.translation_settings.max_batch_size = value
        self.config_manager.save_config()

    def _on_concurrent_slider_changed(self, value: int):
        """Handle concurrent requests slider change."""
        self.concurrent_label.setText(str(value))
        self.config_manager.translation_settings.max_concurrent_threads = value
        self.config_manager.save_config()

    def _on_retry_slider_changed(self, value: int):
        """Handle retry count slider change."""
        self.retry_label.setText(str(value))
        self.config_manager.translation_settings.max_retries = value
        self.config_manager.save_config()

    def _open_glossary_editor(self):
        """Open glossary editor dialog."""
        try:
            from src.gui.glossary_dialog import GlossaryEditorDialog
            dialog = GlossaryEditorDialog(self.config_manager, self)
            dialog.exec()
        except Exception as e:
            self.logger.error(f"Error opening glossary editor: {e}")


    def _on_proxy_enabled_changed(self, checked: bool):
        """Handle proxy enable toggle."""
        self.config_manager.proxy_settings.enabled = checked
        self.config_manager.save_config()

    def _refresh_proxies(self):
        """Refresh proxy list."""
        import asyncio
        import threading
        from src.core.proxy_manager import ProxyManager
        
        def run_refresh():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                pm = ProxyManager()
                loop.run_until_complete(pm.initialize())
                
                stats = pm.get_proxy_stats()
                self.logger.info(f"Proxy refresh: {stats['working_proxies']}/{stats['total_proxies']}")
                
                # Show success notification
                if self.parent_window:
                    # Thread safety: use QTimer or just hope InfoBar handles it (usually does via signals)
                    # For safety in complex UI, it's better to use signals, but direct call often works in simple cases
                    from PyQt6.QtCore import QMetaObject, Q_ARG
                    QMetaObject.invokeMethod(self.parent_window, "show_info_bar",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, "success"),
                        Q_ARG(str, self.config_manager.get_ui_text("success", "Başarılı")),
                        Q_ARG(str, self.config_manager.get_ui_text("proxy_refresh_success", "Proxy listesi güncellendi: {working}/{total} aktif.")
                              .format(working=stats['working_proxies'], total=stats['total_proxies']))
                    )
            except Exception as e:
                self.logger.error(f"Proxy refresh error: {e}")
                if self.parent_window:
                    QMetaObject.invokeMethod(self.parent_window, "show_info_bar",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, "error"),
                        Q_ARG(str, self.config_manager.get_ui_text("error", "Hata")),
                        Q_ARG(str, str(e))
                    )
            finally:
                loop.close()
        
        thread = threading.Thread(target=run_refresh, daemon=True)
        thread.start()
        
        if self.parent_window:
            self.parent_window.show_info_bar(
                "info",
                self.config_manager.get_ui_text("proxy_refreshing", "Proxy Yenileniyor"),
                self.config_manager.get_ui_text("proxy_refresh_started", "Proxy listesi arka planda güncelleniyor...")
            )

    def _open_custom_proxy_dialog(self):
        """Open custom proxy dialog."""
        try:
            from src.gui.proxy_dialog import CustomProxyDialog
            dialog = CustomProxyDialog(self.config_manager, self)
            dialog.exec()
        except Exception as e:
            self.logger.error(f"Error opening proxy dialog: {e}")

    def _on_check_updates_changed(self, checked: bool):
        """Handle check updates toggle."""
        self.config_manager.app_settings.check_for_updates = checked
        self.config_manager.save_config()

    def _check_updates_now(self):
        """Trigger manual update check."""
        if self.parent_window:
            self.parent_window.show_info_bar(
                "info",
                self.config_manager.get_ui_text("update_check_title", "Güncelleme Kontrolü"),
                self.config_manager.get_ui_text("update_checking", "Yeni sürüm kontrol ediliyor...")
            )
            self.parent_window._check_for_updates(manual=True)

    def _on_auto_unren_changed(self, checked: bool):
        """Handle auto UnRen toggle."""
        self.config_manager.app_settings.unren_auto_download = checked
        self.config_manager.save_config()

    def _browse_unren_path(self):
        """Browse for UnRen path."""
        folder = QFileDialog.getExistingDirectory(
            self,
            self.config_manager.get_ui_text("select_unren_folder", "UnRen Klasörü Seç"),
            ""
        )
        if folder:
            self.config_manager.app_settings.unren_custom_path = folder
            self.config_manager.save_config()
            self.unren_path_card.setContent(folder)

    def _on_deep_scan_changed(self, checked: bool):
        """Handle deep scan toggle."""
        self.config_manager.translation_settings.enable_deep_scan = checked
        self.config_manager.save_config()

    def _on_debug_engines_changed(self, checked: bool):
        """Handle debug engines toggle."""
        self.config_manager.translation_settings.show_debug_engines = checked
        self.config_manager.save_config()
        
        # Emit signal to notify other components
        self.debug_engines_changed.emit(checked)
        
        # Notify home interface if possible via a general setting change signal or just hint
        if self.parent_window:
            self.parent_window.show_info_bar(
                "info",
                self.config_manager.get_ui_text("success", "Başarılı"),
                self.config_manager.get_ui_text("debug_engines_changed", "Ayar kaydedildi. Ana sayfadaki liste güncellendi.")
            )

    def _restore_defaults(self):
        """Restore default settings."""
        # Show confirmation dialog
        w = MessageBox(
            self.config_manager.get_ui_text("confirm", "Onay"),
            self.config_manager.get_ui_text("restore_confirm", "Tüm ayarlar varsayılan değerlere döndürülecek. Emin misiniz?"),
            self
        )
        
        if w.exec():
            try:
                # Reset to defaults
                self.config_manager.reset_to_defaults()
                self.config_manager.save_config()
                
                if self.parent_window:
                    self.parent_window.show_info_bar(
                        "success",
                        self.config_manager.get_ui_text("success", "Başarılı"),
                        self.config_manager.get_ui_text("defaults_restored", "Ayarlar varsayılana döndürüldü. Lütfen uygulamayı yeniden başlatın.")
                    )
            except Exception as e:
                self.logger.error(f"Error restoring defaults: {e}")
