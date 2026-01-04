"""Glossary Editor Dialog
=========================

Simple dialog to edit glossary.json (source term -> preferred translation).
"""

import json
from pathlib import Path
import logging

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QHeaderView, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QWidget, QFileDialog,
    QLabel, QPushButton, QDialogButtonBox
)
from qfluentwidgets import (
    PrimaryPushButton, PushButton, TableWidget, LineEdit, 
    MessageBox, MessageDialog, FluentIcon as FIF
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QCoreApplication
from src.utils.config import ConfigManager
from src.tools.glossary_extractor import GlossaryExtractor
import os
import requests
import urllib.parse


class GlossaryEditorDialog(QDialog):
    """Small dialog to view/edit glossary.json entries."""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)

        # Determine glossary file path from translation settings
        self.glossary_path = Path(self.config_manager.translation_settings.glossary_file)

        self._init_ui()
        self._load_glossary()


    def _init_ui(self):
        """Build dialog layout."""
        self.setWindowTitle(self.config_manager.get_ui_text("glossary_title"))
        self.setModal(True)
        self.resize(600, 400)

        # Icon
        icon_path = Path(__file__).parent.parent.parent / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        layout = QVBoxLayout(self)

        info_label = QLabel(self.config_manager.get_ui_text("glossary_info"))
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Table: Source term | Preferred translation
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([
            self.config_manager.get_ui_text("glossary_source"),
            self.config_manager.get_ui_text("glossary_target"),
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        # Row buttons
        # Row buttons
        btn_layout = QHBoxLayout()
        self.add_row_btn = PushButton(self.config_manager.get_ui_text("glossary_add"))
        self.add_row_btn.setIcon(FIF.ADD)
        self.remove_row_btn = PushButton(self.config_manager.get_ui_text("glossary_remove"))
        self.remove_row_btn.setIcon(FIF.REMOVE)
        self.add_row_btn.clicked.connect(self._add_row)
        self.remove_row_btn.clicked.connect(self._remove_selected_rows)
        
        # Extract Button
        self.extract_btn = PushButton(self.config_manager.get_ui_text("glossary_extract_btn"))
        self.extract_btn.setIcon(QIcon(str(Path(__file__).parent.parent.parent / "resources" / "magic-wand.png"))) 
        self.extract_btn.clicked.connect(self._auto_extract)

        # Copy Button
        self.copy_btn = PushButton(self.config_manager.get_ui_text("glossary_copy_btn"))
        self.copy_btn.setIcon(FIF.COPY)
        self.copy_btn.clicked.connect(self._fill_empty_with_source)

        # Translate Button
        self.translate_btn = PushButton(self.config_manager.get_ui_text("glossary_translate_btn"))
        self.translate_btn.setIcon(FIF.LANGUAGE)
        self.translate_btn.clicked.connect(self._translate_list)
        
        btn_layout.addWidget(self.add_row_btn)
        btn_layout.addWidget(self.remove_row_btn)
        btn_layout.addWidget(self.extract_btn)
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addWidget(self.translate_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # OK / Cancel
        # OK / Cancel
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        self.ok_btn = PrimaryPushButton(self.config_manager.get_ui_text("btn_ok", "Kaydet"))
        self.ok_btn.clicked.connect(self.accept)
        
        self.cancel_btn = PushButton(self.config_manager.get_ui_text("btn_cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        
        bottom_layout.addWidget(self.ok_btn)
        bottom_layout.addWidget(self.cancel_btn)
        layout.addLayout(bottom_layout)

    def _load_glossary(self):
        """Load existing glossary.json into the table."""
        data = {}
        try:
            if self.glossary_path.exists():
                with open(self.glossary_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    if isinstance(raw, dict):
                        data = raw
        except Exception as e:
            self.logger.warning(f"Could not load glossary file {self.glossary_path}: {e}")

        for src, dst in data.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(src)))
            self.table.setItem(row, 1, QTableWidgetItem(str(dst)))

    def _add_row(self):
        """Append an empty row to the table."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(""))
        self.table.setItem(row, 1, QTableWidgetItem(""))

    def _remove_selected_rows(self):
        """Remove selected rows from the table."""
        selected = self.table.selectionModel().selectedRows()
        for index in sorted(selected, key=lambda i: i.row(), reverse=True):
            self.table.removeRow(index.row())

    def _auto_extract(self):
        """Run glossary extractor on current project."""
        # Find project path from config or parent window
        project_path = self.config_manager.app_settings.last_input_directory
        
        if not project_path or not os.path.isdir(project_path):
             self._show_message(
                self.config_manager.get_ui_text("glossary_extract_title"),
                self.config_manager.get_ui_text("glossary_extract_no_project"),
                is_error=True
            )
             return

        try:
            extractor = GlossaryExtractor()
            # Extract terms
            terms = extractor.extract_from_directory(project_path, min_occurrence=3)
            
            if not terms:
                return

            # Add to table only if not exists
            existing_keys = set()
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item:
                    existing_keys.add(item.text())
            
            added_count = 0
            for term in terms.keys():
                if term not in existing_keys:
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    self.table.setItem(row, 0, QTableWidgetItem(str(term)))
                    self.table.setItem(row, 1, QTableWidgetItem("")) # Empty target
                    added_count += 1
            
            self._show_message(
                self.config_manager.get_ui_text("glossary_extract_title"),
                self.config_manager.get_ui_text("glossary_extract_success", count=added_count)
            )
            
        except Exception as e:
            self.logger.error(f"Extraction failed: {e}")

    def _fill_empty_with_source(self):
        """Fill empty targets with source text (preserves original term)."""
        # Identify rows with empty targets
        empty_rows = []
        for row in range(self.table.rowCount()):
            source_item = self.table.item(row, 0)
            target_item = self.table.item(row, 1)
            
            if source_item and source_item.text().strip():
                if not target_item or not target_item.text().strip():
                    empty_rows.append((row, source_item.text()))
        
        if not empty_rows:
            return

        # Confirm
        if not self._show_confirmation(
            self.config_manager.get_ui_text("glossary_copy_btn"),
            self.config_manager.get_ui_text("glossary_copy_confirm", count=len(empty_rows))
        ):
            return

        # Fill
        for row, text in empty_rows:
            self.table.setItem(row, 1, QTableWidgetItem(text))
        
        self._show_message(
            self.config_manager.get_ui_text("glossary_copy_btn"),
            self.config_manager.get_ui_text("glossary_copy_done")
        )

    def _translate_list(self):
        """Translate empty targets in the list using Google Translate (Sync)."""
        # Identify rows with empty targets
        empty_rows = []
        for row in range(self.table.rowCount()):
            source_item = self.table.item(row, 0)
            target_item = self.table.item(row, 1)
            
            if source_item and source_item.text().strip():
                if not target_item or not target_item.text().strip():
                    empty_rows.append((row, source_item.text()))
        
        if not empty_rows:
            return

        # Confirm
        if not self._show_confirmation(
            self.config_manager.get_ui_text("glossary_translate_btn"),
            self.config_manager.get_ui_text("glossary_translate_confirm", count=len(empty_rows))
        ):
            return

        # Translate
        target_lang = "tr"
        if self.config_manager.translation_settings.target_language:
            # Simple mapping or usage of raw code
            target_lang = self.config_manager.translation_settings.target_language.lower()
            if target_lang == "turkish": target_lang = "tr"
            elif target_lang == "english": target_lang = "en"
            # Add more if needed or rely on 2-letter codes from config
        
        for row, text in empty_rows:
            try:
                translated = self._google_translate_sync(text, target=target_lang)
                if translated:
                    self.table.setItem(row, 1, QTableWidgetItem(translated))
                
                # Keep UI responsive
                QCoreApplication.processEvents()
                
            except Exception as e:
                self.logger.error(f"Translation failed for {text}: {e}")
        
        self._show_message(
            self.config_manager.get_ui_text("glossary_translate_btn"),
            self.config_manager.get_ui_text("glossary_translate_done")
        )

    def _show_message(self, title, content, is_error=False):
        """Show a localized message box."""
        w = MessageBox(title, content, self)
        w.yesButton.setText(self.config_manager.get_ui_text("btn_ok"))
        w.cancelButton.hide()
        w.exec()

    def _show_confirmation(self, title, content):
        """Show a localized confirmation dialog."""
        w = MessageBox(title, content, self)
        w.yesButton.setText(self.config_manager.get_ui_text("btn_yes"))
        w.cancelButton.setText(self.config_manager.get_ui_text("btn_no"))
        return w.exec()

    def _google_translate_sync(self, text: str, source: str = "auto", target: str = "tr") -> str:
        """Simple synchronous Google Translate request."""
        try:
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                "client": "gtx",
                "sl": source,
                "tl": target,
                "dt": "t",
                "q": text
            }
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            # data[0][0][0] contains the translated text
            if data and isinstance(data, list) and len(data) > 0:
                result = ""
                for part in data[0]:
                    if part and len(part) > 0:
                        result += part[0]
                return result
            return text
        except Exception as e:
            self.logger.error(f"GT Sync Error: {e}")
            return ""

    def _collect_glossary(self) -> dict:
        """Collect table contents into a dict."""
        result = {}
        for row in range(self.table.rowCount()):
            src_item = self.table.item(row, 0)
            dst_item = self.table.item(row, 1)
            if not src_item or not dst_item:
                continue
            src = (src_item.text() or "").strip()
            dst = (dst_item.text() or "").strip()
            if not src or not dst:
                continue
            result[src] = dst
        return result

    def accept(self):
        """Save glossary.json on OK."""
        try:
            data = self._collect_glossary()
            self.glossary_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.glossary_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # Update config manager in-memory glossary so new translations see it immediately
            self.config_manager.glossary = data
            self.logger.info(f"Glossary saved with {len(data)} entries to {self.glossary_path}")
        except Exception as e:
            self.logger.error(f"Error saving glossary: {e}")
            QMessageBox.critical(
                self,
                self.config_manager.get_ui_text("error"),
                self.config_manager.get_ui_text("glossary_save_error").format(error=str(e)),
            )
        super().accept()
