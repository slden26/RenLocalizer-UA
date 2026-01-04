# -*- coding: utf-8 -*-
"""
Home Interface
==============

Main translation page with game selection and translation controls.
"""

import os
import logging
import threading
import asyncio
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox
)
from PyQt6.QtGui import QFont

from qfluentwidgets import (
    CardWidget, PrimaryPushButton, PushButton, LineEdit, ComboBox,
    ProgressBar, ProgressRing, TextEdit, TitleLabel, BodyLabel,
    SubtitleLabel, StrongBodyLabel, InfoBar, InfoBarPosition,
    FluentIcon as FIF, ToolButton, TransparentToolButton
)
from qfluentwidgets import ScrollArea

from src.utils.config import ConfigManager
from src.core.translator import TranslationManager, TranslationEngine, GoogleTranslator, DeepLTranslator, PseudoTranslator
from src.core.proxy_manager import ProxyManager


class HomeInterface(ScrollArea):
    """Main translation interface."""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.parent_window = parent
        
        # Pipeline state
        self.pipeline = None
        self.pipeline_worker = None
        self.current_directory = None
        
        # Initialize managers
        self.proxy_manager = ProxyManager()
        self.translation_manager = TranslationManager(self.proxy_manager)
        self._setup_translation_engines()
        
        # Setup UI
        self.setObjectName("homeInterface")
        self.setWidgetResizable(True)
        
        # Create main widget and layout
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(36, 20, 36, 20)
        self.scroll_layout.setSpacing(20)
        
        self._init_ui()
        self.setWidget(self.scroll_widget)

    def _setup_translation_engines(self):
        """Setup available translation engines."""
        # Google Translator (free)
        google_translator = GoogleTranslator(
            proxy_manager=self.proxy_manager,
            config_manager=self.config_manager
        )
        self.translation_manager.add_translator(TranslationEngine.GOOGLE, google_translator)
        
        # Pseudo-Localization (for testing)
        pseudo_translator = PseudoTranslator(mode="both")
        self.translation_manager.add_translator(TranslationEngine.PSEUDO, pseudo_translator)
        
        # DeepL if API key available
        deepl_key = self.config_manager.get_api_key("deepl")
        if deepl_key:
            deepl_translator = DeepLTranslator(api_key=deepl_key, proxy_manager=self.proxy_manager)
            self.translation_manager.add_translator(TranslationEngine.DEEPL, deepl_translator)

    def _init_ui(self):
        """Initialize the user interface."""
        # Title
        title_label = TitleLabel(self.config_manager.get_ui_text("app_title", "RenLocalizer"))
        title_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self.scroll_layout.addWidget(title_label)
        
        subtitle = BodyLabel(self.config_manager.get_ui_text("app_subtitle", "Professional Ren'Py Translation Tool"))
        subtitle.setObjectName("subtitleLabel")
        self.scroll_layout.addWidget(subtitle)
        
        self.scroll_layout.addSpacing(10)
        
        # Game Selection Card
        self._create_game_selection_card()
        
        # Translation Settings Card
        self._create_translation_settings_card()
        
        # Control Buttons Card
        self._create_control_buttons_card()
        
        # Progress Card
        self._create_progress_card()
        
        # Add stretch at bottom
        self.scroll_layout.addStretch()

    def _create_game_selection_card(self):
        """Create game EXE selection card."""
        card = CardWidget(self.scroll_widget)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)
        
        # Card title
        card_title = StrongBodyLabel(self.config_manager.get_ui_text("input_section", "Oyun Seçimi"))
        card_layout.addWidget(card_title)
        
        # EXE path input row
        path_layout = QHBoxLayout()
        path_layout.setSpacing(10)
        
        self.exe_path_input = LineEdit()
        self.exe_path_input.setPlaceholderText(
            self.config_manager.get_ui_text("game_exe_placeholder", "Oyun EXE dosyasını seçin...")
        )
        self.exe_path_input.setClearButtonEnabled(True)
        path_layout.addWidget(self.exe_path_input, 1)
        
        self.browse_button = PushButton(self.config_manager.get_ui_text("browse", "Gözat"))
        self.browse_button.setIcon(FIF.FOLDER)
        self.browse_button.clicked.connect(self._browse_game_exe)
        path_layout.addWidget(self.browse_button)
        
        card_layout.addLayout(path_layout)
        
        # Status label
        self.game_status_label = BodyLabel("")
        self.game_status_label.setObjectName("gameStatusLabel")
        card_layout.addWidget(self.game_status_label)
        
        self.scroll_layout.addWidget(card)

    def _create_translation_settings_card(self):
        """Create translation settings card."""
        card = CardWidget(self.scroll_widget)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(16)
        
        # Card title
        card_title = StrongBodyLabel(self.config_manager.get_ui_text("translation_settings", "Çeviri Ayarları"))
        card_layout.addWidget(card_title)
        
        # Settings grid
        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(20)
        
        # Source language
        source_layout = QVBoxLayout()
        source_label = BodyLabel(self.config_manager.get_ui_text("source_lang_label", "Kaynak Dil"))
        self.source_lang_combo = ComboBox()
        self.source_lang_combo.addItem(self.config_manager.get_ui_text("auto_detect", "Otomatik"), "auto")
        self.source_lang_combo.addItem("English", "en")
        self.source_lang_combo.addItem("Japanese", "ja")
        source_layout.addWidget(source_label)
        source_layout.addWidget(self.source_lang_combo)
        settings_layout.addLayout(source_layout)
        
        # Target language
        target_layout = QVBoxLayout()
        target_label = BodyLabel(self.config_manager.get_ui_text("target_lang_label", "Hedef Dil"))
        self.target_lang_combo = ComboBox()
        self._populate_target_languages()
        target_layout.addWidget(target_label)
        target_layout.addWidget(self.target_lang_combo)
        settings_layout.addLayout(target_layout)
        
        # Translation engine
        engine_layout = QVBoxLayout()
        engine_label = BodyLabel(self.config_manager.get_ui_text("translation_engine_label", "Çeviri Motoru"))
        self.engine_combo = ComboBox()
        self._populate_engines()
        engine_layout.addWidget(engine_label)
        engine_layout.addWidget(self.engine_combo)
        settings_layout.addLayout(engine_layout)
        
        card_layout.addLayout(settings_layout)
        self.scroll_layout.addWidget(card)

    def _create_control_buttons_card(self):
        """Create control buttons card."""
        card = CardWidget(self.scroll_widget)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(16)
        
        # Start button
        self.start_button = PrimaryPushButton(
            self.config_manager.get_ui_text("start_translation", "Çeviriyi Başlat")
        )
        self.start_button.setIcon(FIF.PLAY)
        self.start_button.clicked.connect(self._start_translation)
        card_layout.addWidget(self.start_button)
        
        # Stop button
        self.stop_button = PushButton(
            self.config_manager.get_ui_text("stop_translation", "Durdur")
        )
        self.stop_button.setIcon(FIF.PAUSE)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_translation)
        card_layout.addWidget(self.stop_button)
        
        card_layout.addStretch()
        
        self.scroll_layout.addWidget(card)

    def _create_progress_card(self):
        """Create progress and log card."""
        card = CardWidget(self.scroll_widget)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)
        
        # Card title
        card_title = StrongBodyLabel(self.config_manager.get_ui_text("progress", "İlerleme"))
        card_layout.addWidget(card_title)
        
        # Stage label
        self.stage_label = SubtitleLabel(self.config_manager.get_ui_text("ready", "Hazır"))
        card_layout.addWidget(self.stage_label)
        
        # Progress bar
        self.progress_bar = ProgressBar()
        self.progress_bar.setValue(0)
        card_layout.addWidget(self.progress_bar)
        
        # Progress label
        self.progress_label = BodyLabel(self.config_manager.get_ui_text("ready", "Hazır"))
        card_layout.addWidget(self.progress_label)
        
        # Log area
        self.log_text = TextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(150)
        self.log_text.setMaximumHeight(250)
        self.log_text.setPlaceholderText(
            self.config_manager.get_ui_text("log_placeholder", "Çeviri logları burada görünecek...")
        )
        card_layout.addWidget(self.log_text)
        
        self.scroll_layout.addWidget(card)

    def _populate_target_languages(self):
        """Populate target language combo box."""
        languages = self.config_manager.get_target_languages_for_ui()
        for code, name in languages:
            self.target_lang_combo.addItem(f"{name} ({code})", userData=code)

    def _populate_engines(self):
        """Populate translation engine combo box."""
        self.engine_combo.clear()
        engines = [
            (TranslationEngine.GOOGLE, self.config_manager.get_ui_text("translation_engines.google", "🌐 Google Translate (Free)")),
            (TranslationEngine.DEEPL, self.config_manager.get_ui_text("translation_engines.deepl", "🔷 DeepL (API Key)")),
        ]
        
        # Add debug engines only if enabled in settings
        if getattr(self.config_manager.translation_settings, 'show_debug_engines', False):
            engines.append(
                (TranslationEngine.PSEUDO, self.config_manager.get_ui_text("pseudo_engine_name", "🧪 Pseudo-Localization (Test)"))
            )
            
        for engine, name in engines:
            self.engine_combo.addItem(name, userData=engine)

    def _browse_game_exe(self):
        """Browse for game EXE file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.config_manager.get_ui_text("select_game_exe_title", "Oyun EXE Dosyası Seç"),
            "",
            "Executable (*.exe);;All Files (*.*)"
        )
        
        if file_path:
            self.exe_path_input.setText(file_path)
            self._validate_game_path(file_path)

    def _validate_game_path(self, file_path: str):
        """Validate selected game path."""
        self.log_text.clear()
        self._add_log("info", self.config_manager.get_ui_text("exe_selected", "Seçilen EXE: {path}").replace("{path}", file_path))
        
        project_dir = os.path.dirname(file_path)
        game_dir = os.path.join(project_dir, 'game')
        
        if os.path.isdir(game_dir):
            self._add_log("info", self.config_manager.get_ui_text("valid_renpy_project", "✅ Geçerli Ren'Py projesi"))
            self.game_status_label.setText("✅ " + self.config_manager.get_ui_text("valid_renpy_project", "Geçerli Ren'Py projesi"))
            
            # Check for .rpy and .rpyc files
            has_rpy = self._has_files_in_dir(game_dir, '.rpy')
            has_rpyc = self._has_files_in_dir(game_dir, '.rpyc')
            
            if has_rpy:
                self._add_log("info", self.config_manager.get_ui_text("rpy_files_found", ".rpy dosyaları bulundu"))
            elif has_rpyc:
                self._add_log("warning", self.config_manager.get_ui_text("only_rpyc_files", "Sadece .rpyc dosyaları var (UnRen gerekli)"))
        else:
            self._add_log("error", self.config_manager.get_ui_text("game_folder_not_found", "❌ 'game' klasörü bulunamadı"))
            self.game_status_label.setText("❌ " + self.config_manager.get_ui_text("game_folder_not_found", "game klasörü bulunamadı"))
        
        self.current_directory = Path(project_dir)
        
        # Save to configuration
        self.config_manager.app_settings.last_input_directory = project_dir
        if self.config_manager.app_settings.auto_save_settings:
            self.config_manager.save_config()

    def _has_files_in_dir(self, directory: str, extension: str) -> bool:
        """Check if directory has files with given extension."""
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.endswith(extension):
                    return True
        return False

    def _add_log(self, level: str, message: str):
        """Add log message to log area."""
        color_map = {
            "info": "#17a2b8",
            "warning": "#ffc107",
            "error": "#dc3545",
            "success": "#28a745"
        }
        color = color_map.get(level, "#6c757d")
        self.log_text.append(f'<span style="color:{color}">{message}</span>')

    def _start_translation(self):
        """Start the translation pipeline."""
        exe_path = self.exe_path_input.text().strip()
        
        if not exe_path:
            self._show_warning(
                self.config_manager.get_ui_text("warning", "Uyarı"),
                self.config_manager.get_ui_text("please_select_exe", "Lütfen bir oyun EXE dosyası seçin")
            )
            return
        
        if not os.path.isfile(exe_path):
            self._show_warning(
                self.config_manager.get_ui_text("warning", "Uyarı"),
                self.config_manager.get_ui_text("exe_not_found", "EXE dosyası bulunamadı")
            )
            return
        
        # Import pipeline
        from src.core.translation_pipeline import TranslationPipeline, PipelineWorker
        
        # Get settings
        target_lang = self.target_lang_combo.currentData()
        source_lang = self.source_lang_combo.currentData()
        engine = self.engine_combo.currentData()
        
        # Get settings from config
        auto_unren = self.config_manager.app_settings.unren_auto_download
        use_proxy = getattr(self.config_manager.proxy_settings, "enabled", False)
        
        # Create pipeline
        self.pipeline = TranslationPipeline(self.config_manager, self.translation_manager)
        self.pipeline.configure(
            game_exe_path=exe_path,
            target_language=target_lang,
            source_language=source_lang,
            engine=engine,
            auto_unren=auto_unren,
            use_proxy=use_proxy
        )
        
        # Connect signals
        self.pipeline.stage_changed.connect(self._on_stage_changed)
        self.pipeline.progress_updated.connect(self._on_progress_updated)
        self.pipeline.log_message.connect(self._on_log_message)
        self.pipeline.finished.connect(self._on_pipeline_finished)
        self.pipeline.show_warning.connect(self._on_show_warning)
        
        # UI state
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.browse_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_text.clear()
        
        self._add_log("info", self.config_manager.get_ui_text("pipeline_starting", "Pipeline başlatılıyor..."))
        
        # Start worker
        self.pipeline_worker = PipelineWorker(self.pipeline)
        self.pipeline_worker.start()

    def _stop_translation(self):
        """Stop the translation pipeline."""
        if self.pipeline:
            self._add_log("warning", self.config_manager.get_ui_text("stop_requested", "Durdurma istendi..."))
            self.pipeline.stop()
            
            if self.pipeline_worker:
                try:
                    self.pipeline_worker.wait(5000)
                except Exception:
                    pass
                self.pipeline_worker = None

    def _on_stage_changed(self, stage: str, message: str):
        """Handle pipeline stage change."""
        stage_keys = {
            "idle": "stage_idle",
            "validating": "stage_validating",
            "unren": "stage_unren",
            "generating": "stage_generating",
            "parsing": "stage_parsing",
            "translating": "stage_translating",
            "saving": "stage_saving",
            "completed": "stage_completed",
            "error": "stage_error"
        }
        
        stage_key = stage_keys.get(stage, "stage_idle")
        display_name = self.config_manager.get_ui_text(stage_key, stage)
        self.stage_label.setText(display_name)
        
        # Update progress bar
        stage_progress = {
            "idle": 0,
            "validating": 5,
            "unren": 15,
            "generating": 30,
            "parsing": 40,
            "translating": 50,
            "saving": 95,
            "completed": 100,
            "error": 0
        }
        
        if stage in stage_progress and stage != "translating":
            self.progress_bar.setValue(stage_progress[stage])

    def _on_progress_updated(self, current: int, total: int, text: str):
        """Handle translation progress update."""
        if total > 0:
            percentage = 50 + int((current / total) * 45)
            self.progress_bar.setValue(percentage)
            self.progress_label.setText(f"{current}/{total}")

    def _on_log_message(self, level: str, message: str):
        """Handle log message from pipeline."""
        self._add_log(level, message)

    def _on_show_warning(self, title: str, message: str):
        """Show warning popup from pipeline."""
        self._show_warning(title, message)

    def _on_pipeline_finished(self, result):
        """Handle pipeline completion."""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.browse_button.setEnabled(True)
        
        if result.success:
            self.progress_bar.setValue(100)
            self._add_log("success", f"✅ {result.message}")
            
            if result.stats:
                stats = result.stats
                self._add_log("info", self.config_manager.get_ui_text("stats_total_info", "📊 Toplam: {count}").format(count=stats['total']))
                self._add_log("info", self.config_manager.get_ui_text("stats_translated_info", "✅ Çevrilen: {count}").format(count=stats['translated']))
                self._add_log("info", self.config_manager.get_ui_text("stats_untranslated_info", "⏳ Çevrilmeyen: {count}").format(count=stats['untranslated']))
            
            if result.output_path:
                self._add_log("info", self.config_manager.get_ui_text("output_path_info", "📁 Çıktı: {path}").format(path=result.output_path))
            
            # Show success InfoBar
            if self.parent_window:
                self.parent_window.show_info_bar(
                    "success",
                    self.config_manager.get_ui_text("success", "Başarılı"),
                    result.message
                )
        else:
            self._add_log("error", f"❌ {result.message}")
            
            if result.error:
                self._add_log("error", self.config_manager.get_ui_text("detail_info", "Detay: {error}").format(error=result.error))
            
            # Show error InfoBar
            if self.parent_window:
                self.parent_window.show_info_bar(
                    "error",
                    self.config_manager.get_ui_text("error", "Hata"),
                    result.message
                )
        
        # Cleanup
        if self.pipeline_worker:
            try:
                self.pipeline_worker.wait(2000)
            except Exception:
                pass
            self.pipeline_worker = None
        
        # Close async sessions
        try:
            threading.Thread(
                target=lambda: asyncio.run(self.translation_manager.close_all()),
                daemon=True
            ).start()
        except Exception:
            pass

    def _show_warning(self, title: str, message: str):
        """Show warning message."""
        if self.parent_window:
            self.parent_window.show_info_bar("warning", title, message)
        else:
            QMessageBox.warning(self, title, message)
