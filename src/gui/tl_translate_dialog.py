"""
Dialog for translating existing tl/<lang> folders (Ren'Py SDK outputs).
Uses existing TranslationPipeline translate_existing_tl helper.
"""

import os
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QTextEdit, QFileDialog, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

from src.core.translation_pipeline import TranslationPipeline, PipelineStage, PipelineResult
from src.core.translator import TranslationEngine


class TLTranslateWorker(QThread):
    stage_changed = pyqtSignal(str, str)
    log_message = pyqtSignal(str, str)
    finished = pyqtSignal(object)

    def __init__(self, config, translation_manager, tl_path, target_lang, source_lang, engine, use_proxy):
        super().__init__()
        self.config = config
        self.translation_manager = translation_manager
        self.tl_path = tl_path
        self.target_lang = target_lang
        self.source_lang = source_lang
        self.engine = engine
        self.use_proxy = use_proxy

    def run(self):
        pipeline = TranslationPipeline(self.config, self.translation_manager)
        pipeline.stage_changed.connect(self.stage_changed)
        pipeline.log_message.connect(self.log_message)
        try:
            result = pipeline.translate_existing_tl(
                self.tl_path,
                self.target_lang,
                self.source_lang,
                self.engine,
                self.use_proxy
            )
        except Exception as e:  # noqa: BLE001
            result = PipelineResult(False, f"Hata: {e}", PipelineStage.ERROR, error=str(e))
        self.finished.emit(result)


class TLTranslateDialog(QDialog):
    """Simple dialog to translate an existing tl/<lang> folder."""

    def __init__(self, config_manager, translation_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.translation_manager = translation_manager

        self.worker_thread: Optional[QThread] = None
        self.init_ui()
        self.setWindowTitle(self.config.get_ui_text("tl_translate_title"))
        self.resize(520, 360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # tl path
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText(self.config.get_ui_text("tl_directory_placeholder"))
        browse_btn = QPushButton(self.config.get_ui_text("browse"))
        browse_btn.clicked.connect(self.browse_path)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        form.addRow(self.config.get_ui_text("tl_directory_label"), path_layout)

        # target lang
        self.target_combo = QComboBox()
        for code, name in self.config.get_supported_languages().items():
            if code == "auto":
                continue
            self.target_combo.addItem(f"{name} ({code})", code)
        form.addRow(self.config.get_ui_text("target_lang_label"), self.target_combo)

        # source lang
        self.source_combo = QComboBox()
        self.source_combo.addItem(self.config.get_ui_text("auto_detect"), "auto")
        self.source_combo.addItem("English", "en")
        self.source_combo.addItem("Japanese", "ja")
        form.addRow(self.config.get_ui_text("source_lang_label"), self.source_combo)

        # engine
        self.engine_combo = QComboBox()
        self.engine_combo.addItem(self.config.get_ui_text("translation_engines.google"), TranslationEngine.GOOGLE)
        self.engine_combo.addItem(self.config.get_ui_text("translation_engines.deepl"), TranslationEngine.DEEPL)
        form.addRow(self.config.get_ui_text("translation_engine_label"), self.engine_combo)

        # proxy
        self.proxy_check = QCheckBox(self.config.get_ui_text("enable_proxy_label"))
        self.proxy_check.setChecked(getattr(self.config.proxy_settings, "enabled", False))
        form.addRow(self.proxy_check)

        layout.addLayout(form)

        # progress + log
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        layout.addWidget(self.log)

        # buttons
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton(self.config.get_ui_text("start_translation"))
        self.start_btn.clicked.connect(self.start_translation)
        self.close_btn = QPushButton(self.config.get_ui_text("exit"))
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

    def init_ui(self) -> None:
        """Basic dialog flags and modality."""
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "TL dizini")
        if path:
            self.path_input.setText(path)

    def start_translation(self):
        if self.worker_thread:
            return
        tl_path = self.path_input.text().strip()
        if not tl_path or not os.path.isdir(tl_path):
            self.log.append(f"<span style='color:#dc3545'>{self.config.get_ui_text('tl_invalid_dir')}</span>")
            return
        target_lang = self.target_combo.currentData()
        source_lang = self.source_combo.currentData()
        engine = self.engine_combo.currentData()
        use_proxy = self.proxy_check.isChecked()

        # disable UI
        self.start_btn.setEnabled(False)
        self.progress.setValue(0)
        self.log.clear()

        self.worker_thread = TLTranslateWorker(
            self.config, self.translation_manager, tl_path, target_lang, source_lang, engine, use_proxy
        )
        self.worker_thread.stage_changed.connect(self.on_stage_changed)
        self.worker_thread.log_message.connect(self.on_log_message)
        self.worker_thread.finished.connect(self._handle_finish)
        self.worker_thread.start()

    def _handle_finish(self, result: PipelineResult):
        self.start_btn.setEnabled(True)
        self.worker_thread = None
        if result.stage == PipelineStage.COMPLETED and result.success:
            self.progress.setValue(100)
            self.log.append(f"<span style='color:#28a745'>{result.message}</span>")
        else:
            self.log.append(f"<span style='color:#dc3545'>{result.message}</span>")

    def on_stage_changed(self, stage: str, message: str):
        stage_progress = {
            "parsing": 20,
            "translating": 50,
            "saving": 80,
            "completed": 100,
            "error": 0,
        }
        self.progress.setValue(stage_progress.get(stage, 0))
        if message:
            self.log.append(f"<span style='color:#17a2b8'>[{stage}] {message}</span>")

    def on_log_message(self, level: str, message: str):
        color_map = {
            "info": "#17a2b8",
            "warning": "#ffc107",
            "error": "#dc3545",
            "success": "#28a745",
            "debug": "#6c757d",
        }
        color = color_map.get(level, "#6c757d")
        self.log.append(f"<span style='color:{color}'>{message}</span>")
