# -*- coding: utf-8 -*-
"""
Tools Interface
===============

Tools page with UnRen, Health Check, and other utilities.
"""

import logging
import asyncio
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox

from qfluentwidgets import (
    CardWidget, PushButton, PrimaryPushButton, BodyLabel, TitleLabel,
    SubtitleLabel, StrongBodyLabel, InfoBar, InfoBarPosition,
    FluentIcon as FIF, ExpandLayout, ScrollArea, MessageBox
)

from src.utils.config import ConfigManager


class ToolsInterface(ScrollArea):
    """Tools and utilities interface."""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.parent_window = parent
        
        self.setObjectName("toolsInterface")
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
        # Title
        title_label = TitleLabel(self.config_manager.get_ui_text("nav_tools", "Araçlar"))
        self.scroll_layout.addWidget(title_label)
        
        subtitle = BodyLabel(self.config_manager.get_ui_text("tools_subtitle", "Yardımcı araçlar ve ek özellikler"))
        self.scroll_layout.addWidget(subtitle)
        
        self.scroll_layout.addSpacing(10)
        
        # UnRen Tools Card
        self._create_unren_card()
        
        # Diagnostics Card
        self._create_diagnostics_card()
        
        # Translation Tools Card
        self._create_translation_tools_card()
        
        # Add stretch at bottom
        self.scroll_layout.addStretch()

    def _create_unren_card(self):
        """Create UnRen tools card."""
        card = CardWidget(self.scroll_widget)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)
        
        # Card title
        title_layout = QHBoxLayout()
        card_title = StrongBodyLabel("🔓 " + self.config_manager.get_ui_text("unren_title", "UnRen Araçları"))
        title_layout.addWidget(card_title)
        title_layout.addStretch()
        card_layout.addLayout(title_layout)
        
        # Description
        desc = BodyLabel(self.config_manager.get_ui_text(
            "unren_desc", 
            "Ren'Py oyunlarındaki .rpa arşivlerini ve .rpyc dosyalarını açmak için UnRen kullanın."
        ))
        desc.setWordWrap(True)
        card_layout.addWidget(desc)
        
        # Buttons row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        run_unren_btn = PrimaryPushButton(self.config_manager.get_ui_text("run_unren_menu", "UnRen Çalıştır"))
        run_unren_btn.setIcon(FIF.PLAY)
        run_unren_btn.clicked.connect(self._run_unren)
        btn_layout.addWidget(run_unren_btn)
        
        redownload_btn = PushButton(self.config_manager.get_ui_text("redownload_unren_menu", "UnRen'i Yeniden İndir"))
        redownload_btn.setIcon(FIF.DOWNLOAD)
        redownload_btn.clicked.connect(self._redownload_unren)
        btn_layout.addWidget(redownload_btn)
        
        btn_layout.addStretch()
        card_layout.addLayout(btn_layout)
        
        self.scroll_layout.addWidget(card)

    def _create_diagnostics_card(self):
        """Create diagnostics tools card."""
        card = CardWidget(self.scroll_widget)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)
        
        # Card title
        card_title = StrongBodyLabel("🔍 " + self.config_manager.get_ui_text("diagnostics_title", "Tanılama Araçları"))
        card_layout.addWidget(card_title)
        
        # Description
        desc = BodyLabel(self.config_manager.get_ui_text(
            "diagnostics_desc",
            "Çeviri kalitesini artırmak için tanılama ve kontrol araçları."
        ))
        desc.setWordWrap(True)
        card_layout.addWidget(desc)
        
        # Buttons grid
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        health_check_btn = PushButton(self.config_manager.get_ui_text("health_check_menu", "Sağlık Kontrolü"))
        health_check_btn.setIcon(FIF.HEART)
        health_check_btn.clicked.connect(self._health_check)
        btn_layout.addWidget(health_check_btn)
        
        font_check_btn = PushButton(self.config_manager.get_ui_text("font_check_menu", "Font Uyumluluğu"))
        font_check_btn.setIcon(FIF.FONT)
        font_check_btn.clicked.connect(self._font_check)
        btn_layout.addWidget(font_check_btn)
        
        btn_layout.addStretch()
        card_layout.addLayout(btn_layout)
        
        self.scroll_layout.addWidget(card)

    def _create_translation_tools_card(self):
        """Create translation tools card."""
        card = CardWidget(self.scroll_widget)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(12)
        
        # Card title
        card_title = StrongBodyLabel("🔄 " + self.config_manager.get_ui_text("translation_tools_title", "Çeviri Araçları"))
        card_layout.addWidget(card_title)
        
        # Description
        desc = BodyLabel(self.config_manager.get_ui_text(
            "translation_tools_desc",
            "Gelişmiş çeviri ve test araçları."
        ))
        desc.setWordWrap(True)
        card_layout.addWidget(desc)
        
        # Buttons row 1
        btn_layout1 = QHBoxLayout()
        btn_layout1.setSpacing(10)
        
        pseudo_btn = PushButton(self.config_manager.get_ui_text("pseudo_menu", "Pseudo-Localization"))
        pseudo_btn.setIcon(FIF.DEVELOPER_TOOLS)
        pseudo_btn.clicked.connect(self._pseudo_localization)
        btn_layout1.addWidget(pseudo_btn)
        
        fuzzy_btn = PushButton(self.config_manager.get_ui_text("fuzzy_menu", "Akıllı Güncelleme (Fuzzy)"))
        fuzzy_btn.setIcon(FIF.SYNC)
        fuzzy_btn.clicked.connect(self._fuzzy_update)
        btn_layout1.addWidget(fuzzy_btn)
        
        btn_layout1.addStretch()
        card_layout.addLayout(btn_layout1)
        
        # Buttons row 2
        btn_layout2 = QHBoxLayout()
        btn_layout2.setSpacing(10)
        
        tl_translate_btn = PrimaryPushButton(self.config_manager.get_ui_text("tl_translate_menu", "TL Klasörünü Çevir"))
        tl_translate_btn.setIcon(FIF.LANGUAGE)
        tl_translate_btn.clicked.connect(self._tl_translate)
        btn_layout2.addWidget(tl_translate_btn)
        
        btn_layout2.addStretch()
        card_layout.addLayout(btn_layout2)
        
        self.scroll_layout.addWidget(card)

    def _run_unren(self):
        """Run UnRen on selected game."""
        from src.gui.unren_mode_dialog import UnRenModeDialog
        
        dialog = UnRenModeDialog(self.config_manager, self)
        if dialog.exec():
            game_path = dialog.get_selected_path()
            if game_path:
                self._execute_unren(game_path, dialog.get_mode())

    def _execute_unren(self, game_path: str, mode: str):
        """Execute UnRen with specified mode."""
        from src.utils.unren_manager import UnRenManager
        
        try:
            unren_manager = UnRenManager(self.config_manager)
            
            # Show progress
            if self.parent_window:
                self.parent_window.show_info_bar(
                    "info",
                    self.config_manager.get_ui_text("unren_running", "UnRen Çalışıyor"),
                    self.config_manager.get_ui_text("unren_please_wait", "Lütfen bekleyin...")
                )
            
            # Run UnRen
            success, message = unren_manager.run_unren(game_path, mode)
            
            if success and self.parent_window:
                self.parent_window.show_info_bar(
                    "success",
                    self.config_manager.get_ui_text("success", "Başarılı"),
                    message
                )
            elif self.parent_window:
                self.parent_window.show_info_bar(
                    "error",
                    self.config_manager.get_ui_text("error", "Hata"),
                    message
                )
                
        except Exception as e:
            self.logger.error(f"UnRen error: {e}")
            if self.parent_window:
                self.parent_window.show_info_bar(
                    "error",
                    self.config_manager.get_ui_text("error", "Hata"),
                    str(e)
                )

    def _redownload_unren(self):
        """Force re-download UnRen."""
        from src.utils.unren_manager import UnRenManager
        
        try:
            unren_manager = UnRenManager(self.config_manager)
            unren_manager.force_redownload()
            
            if self.parent_window:
                self.parent_window.show_info_bar(
                    "success",
                    self.config_manager.get_ui_text("success", "Başarılı"),
                    self.config_manager.get_ui_text("unren_redownloaded", "UnRen yeniden indirildi")
                )
        except Exception as e:
            self.logger.error(f"UnRen redownload error: {e}")
            if self.parent_window:
                self.parent_window.show_info_bar(
                    "error",
                    self.config_manager.get_ui_text("error", "Hata"),
                    str(e)
                )

    def _health_check(self):
        """Show health check dialog."""
        try:
            from src.tools.health_check import run_health_check
        except ImportError:
            self._show_info(
                self.config_manager.get_ui_text("info", "Bilgi"),
                self.config_manager.get_ui_text("feature_not_available", "Bu özellik henüz hazır değil.")
            )
            return
            
        # Ask for directory
        directory = QFileDialog.getExistingDirectory(
            self,
            self.config_manager.get_ui_text("health_check_select_dir", "Oyun Klasörünü Seç"),
            ""
        )
        
        if not directory:
            return
            
        try:
            report = run_health_check(directory, verbose=False)
            result_text = report.summary()
            
            if report.issues:
                result_text += "\n\n" + self.config_manager.get_ui_text("health_issues_found", "Sorunlar Bulundu:") + "\n"
                for issue in report.issues[:10]:
                    result_text += f"\n• [{issue.severity.value.upper()}] {issue.message}"
            
            w = MessageBox(
                self.config_manager.get_ui_text("health_check_title", "Sağlık Kontrolü"),
                result_text,
                self
            )
            w.exec()
        except Exception as e:
            self.logger.error(f"Health check error: {e}")
            self._show_info("Error", str(e))

    def _font_check(self):
        """Show font compatibility check."""
        try:
            from src.tools.font_helper import check_font_for_project
        except ImportError:
            self._show_info(
                self.config_manager.get_ui_text("info", "Bilgi"),
                self.config_manager.get_ui_text("feature_not_available", "Bu özellik henüz hazır değil.")
            )
            return

        # Ask for directory
        directory = QFileDialog.getExistingDirectory(
            self,
            self.config_manager.get_ui_text("font_check_select_dir", "Oyun Klasörünü Seç"),
            ""
        )
        
        if not directory:
            return
            
        try:
            summary = check_font_for_project(directory, "tr", verbose=False)
            result_text = self.config_manager.get_ui_text("font_check_summary", "Kontrol edilen font: {total}\nUyumlu: {comp}\nUyumsuz: {incomp}").format(
                total=summary['fonts_checked'],
                comp=summary['compatible_fonts'],
                incomp=summary['incompatible_fonts']
            )
            
            w = MessageBox(
                self.config_manager.get_ui_text("font_check_title", "Font Uyumluluğu"),
                result_text,
                self
            )
            w.exec()
        except Exception as e:
            self.logger.error(f"Font check error: {e}")
            self._show_info("Error", str(e))

    def _pseudo_localization(self):
        """Show pseudo-localization dialog."""
        # Pseudo translation is actually handled via the main translation pipeline
        # with Engine=PSEUDO. Here we just show info.
        self._show_info(
            self.config_manager.get_ui_text("info", "Bilgi"),
            self.config_manager.get_ui_text("pseudo_engine_hint", "Pseudo-Localization yeteneği Ana Sayfa'da 'Çeviri Motoru' olarak seçilebilir.")
        )

    def _fuzzy_update(self):
        """Show fuzzy update dialog."""
        try:
            from src.tools.fuzzy_matcher import FuzzyMatcher
            self._show_info(
                self.config_manager.get_ui_text("info", "Bilgi"),
                self.config_manager.get_ui_text("fuzzy_engine_hint", "Fuzzy Matching motoru arka planda aktiftir. Detaylı rapor için logları kontrol edin.")
            )
        except ImportError:
            self._show_info(
                self.config_manager.get_ui_text("info", "Bilgi"),
                self.config_manager.get_ui_text("feature_not_available", "Bu özellik henüz hazır değil.")
            )

    def _tl_translate(self):
        """Show TL folder translation dialog."""
        try:
            from src.gui.tl_translate_dialog import TLTranslateDialog
            dialog = TLTranslateDialog(self.config_manager, self)
            dialog.exec()
        except ImportError as e:
            self.logger.error(f"TL translate dialog import error: {e}")
            self._show_info(
                self.config_manager.get_ui_text("info", "Bilgi"),
                self.config_manager.get_ui_text("feature_not_available", "Bu özellik henüz hazır değil.")
            )

    def _show_info(self, title: str, message: str):
        """Show info message."""
        if self.parent_window:
            self.parent_window.show_info_bar("info", title, message)
        else:
            QMessageBox.information(self, title, message)
