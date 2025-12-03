"""
Model Download Dialog
===================

Dialog for OPUS-MT model download confirmation and progress.
"""

try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QProgressBar, QTextEdit, QCheckBox, QGroupBox, QDialogButtonBox
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt6.QtGui import QFont, QPixmap, QIcon
except ImportError:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QProgressBar, QTextEdit, QCheckBox, QGroupBox, QDialogButtonBox
    )
    from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal, QTimer
    from PySide6.QtGui import QFont, QPixmap, QIcon

import asyncio
import logging
from typing import Optional, Callable

from src.utils.config import ConfigManager


class ModelDownloadDialog(QDialog):
    """Dialog for OPUS-MT model download confirmation and progress."""
    
    def __init__(self, parent=None, model_name: str = "", language_pair: str = "", config_manager: ConfigManager = None):
        super().__init__(parent)
        self.model_name = model_name
        self.language_pair = language_pair
        self.download_confirmed = False
        self.download_thread = None
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager or ConfigManager()
        
        self.setWindowTitle(self.config_manager.get_ui_text("model_download_dialog.title"))
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel(self.config_manager.get_ui_text("model_download_dialog.header"))
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(14)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header_label)
        
        # Info group
        info_group = QGroupBox(self.config_manager.get_ui_text("model_download_dialog.info_group"))
        info_layout = QVBoxLayout(info_group)
        
        model_label = QLabel(self.config_manager.get_ui_text("model_download_dialog.model_label").format(model_name=self.model_name))
        language_label = QLabel(self.config_manager.get_ui_text("model_download_dialog.language_pair_label").format(language_pair=self.language_pair))
        size_label = QLabel(self.config_manager.get_ui_text("model_download_dialog.size_label"))
        
        info_layout.addWidget(model_label)
        info_layout.addWidget(language_label)
        info_layout.addWidget(size_label)
        
        layout.addWidget(info_group)
        
        # Description
        desc_group = QGroupBox(self.config_manager.get_ui_text("model_download_dialog.description_group"))
        desc_layout = QVBoxLayout(desc_group)
        
        description = QLabel(self.config_manager.get_ui_text("model_download_dialog.description_text"))
        description.setWordWrap(True)
        desc_layout.addWidget(description)
        
        layout.addWidget(desc_group)
        
        # Options
        options_group = QGroupBox(self.config_manager.get_ui_text("model_download_dialog.options_group"))
        options_layout = QVBoxLayout(options_group)
        
        self.auto_download_checkbox = QCheckBox(self.config_manager.get_ui_text("model_download_dialog.auto_download_checkbox"))
        options_layout.addWidget(self.auto_download_checkbox)
        
        layout.addWidget(options_group)
        
        # Progress section (initially hidden)
        self.progress_group = QGroupBox(self.config_manager.get_ui_text("model_download_dialog.progress_group"))
        progress_layout = QVBoxLayout(self.progress_group)
        
        self.progress_label = QLabel(self.config_manager.get_ui_text("model_download_dialog.preparing"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        self.progress_text = QTextEdit()
        self.progress_text.setMaximumHeight(100)
        self.progress_text.setReadOnly(True)
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_text)
        
        self.progress_group.setVisible(False)
        layout.addWidget(self.progress_group)
        
        # Buttons
        self.button_box = QDialogButtonBox()
        self.download_button = QPushButton(self.config_manager.get_ui_text("model_download_dialog.download_button"))
        self.cancel_button = QPushButton(self.config_manager.get_ui_text("model_download_dialog.cancel_button"))
        self.close_button = QPushButton(self.config_manager.get_ui_text("model_download_dialog.close_button"))
        
        self.button_box.addButton(self.download_button, QDialogButtonBox.ButtonRole.AcceptRole)
        self.button_box.addButton(self.cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
        
        self.download_button.clicked.connect(self.start_download)
        self.cancel_button.clicked.connect(self.reject)
        
        layout.addWidget(self.button_box)
        
    def start_download(self):
        """Start the model download process."""
        self.download_confirmed = True
        self.progress_group.setVisible(True)
        
        # Hide download button, show cancel
        self.download_button.setVisible(False)
        self.cancel_button.setText(self.config_manager.get_ui_text("model_download_dialog.pause_cancel_button"))
        
        # Start download thread
        self.download_thread = ModelDownloadThread(self.model_name, self.config_manager)
        self.download_thread.progress_updated.connect(self.update_progress)
        self.download_thread.status_updated.connect(self.update_status)
        self.download_thread.download_finished.connect(self.download_complete)
        self.download_thread.download_error.connect(self.download_failed)
        
        # Make sure thread is properly parented
        self.download_thread.setParent(self)
        self.download_thread.start()
        
    def update_progress(self, value: int, maximum: int):
        """Update progress bar."""
        if maximum > 0:
            self.progress_bar.setRange(0, maximum)
            self.progress_bar.setValue(value)
        else:
            self.progress_bar.setRange(0, 0)  # Indeterminate
            
    def update_status(self, message: str):
        """Update status message."""
        self.progress_label.setText(message)
        self.progress_text.append(f"[{message}]")
        
    def download_complete(self):
        """Handle successful download completion."""
        self.progress_label.setText(self.config_manager.get_ui_text("model_download_dialog.download_complete"))
        self.progress_bar.setValue(self.progress_bar.maximum())
        
        # Replace cancel with close button
        self.button_box.clear()
        self.close_button.clicked.connect(self.accept)
        self.button_box.addButton(self.close_button, QDialogButtonBox.ButtonRole.AcceptRole)
        
        self.update_status(self.config_manager.get_ui_text("model_download_dialog.model_ready"))
        
    def download_failed(self, error: str):
        """Handle download failure."""
        self.progress_label.setText(self.config_manager.get_ui_text("model_download_dialog.download_failed"))
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        
        self.update_status(self.config_manager.get_ui_text("model_download_dialog.error_prefix").format(error=error))
        
        # Show retry option
        self.download_button.setText(self.config_manager.get_ui_text("model_download_dialog.retry_button"))
        self.download_button.setVisible(True)


class ModelDownloadThread(QThread):
    """Thread for downloading OPUS-MT models."""
    
    progress_updated = pyqtSignal(int, int)
    status_updated = pyqtSignal(str)
    download_finished = pyqtSignal()
    download_error = pyqtSignal(str)
    
    def __init__(self, model_name: str):
        super().__init__()
        self.model_name = model_name
        self.logger = logging.getLogger(__name__)
        
    def run(self):
        """Run the download process."""
        try:
            self.status_updated.emit("Transformers kütüphanesi yükleniyor...")
            
            from transformers import MarianMTModel, MarianTokenizer
            import os
            
            self.status_updated.emit("Model indiriliyor...")
            self.progress_updated.emit(0, 0)  # Indeterminate
            
            # Download model with progress callback if possible
            try:
                model = MarianMTModel.from_pretrained(self.model_name)
                self.status_updated.emit("Tokenizer indiriliyor...")
                tokenizer = MarianTokenizer.from_pretrained(self.model_name)
                
                self.status_updated.emit("Model dosyaları doğrulanıyor...")
                
                # Verify model is working
                test_input = tokenizer(["Hello world"], return_tensors="pt", padding=True)
                test_output = model.generate(**test_input, max_new_tokens=10, do_sample=False)
                test_result = tokenizer.decode(test_output[0], skip_special_tokens=True)
                
                if test_result:
                    self.status_updated.emit("Model testi başarılı!")
                    self.download_finished.emit()
                else:
                    self.download_error.emit("Model testi başarısız - model çalışmıyor")
                    
            except Exception as e:
                self.logger.error(f"Model download failed: {e}")
                self.download_error.emit(str(e))
                
        except ImportError as e:
            self.download_error.emit("Transformers kütüphanesi bulunamadı. 'pip install transformers torch' çalıştırın.")
        except Exception as e:
            self.logger.error(f"Download thread error: {e}")
            self.download_error.emit(str(e))