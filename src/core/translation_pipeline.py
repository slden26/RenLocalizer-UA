# -*- coding: utf-8 -*-
"""
Integrated Translation Pipeline
================================

Tek tıkla çeviri: EXE → UnRen → Translate → Çeviri → Kaydet

Bu modül tüm çeviri sürecini entegre bir pipeline olarak yönetir.
"""

import os
import logging
import asyncio
import re
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import shutil  # En tepeye ekleyin
from src.utils.encoding import normalize_to_utf8_sig, read_text_safely

from PyQt6.QtCore import QObject, pyqtSignal, QThread

from src.utils.config import ConfigManager
from src.utils.sdk_finder import find_renpy_sdks
from src.utils.unren_manager import UnRenManager
from src.core.tl_parser import TLParser, TranslationFile, TranslationEntry, get_translation_stats
from src.core.parser import RenPyParser
from src.core.translator import (
    TranslationManager,
    TranslationRequest,
    TranslationEngine,
    GoogleTranslator,
    DeepLTranslator,
)
from src.core.output_formatter import RenPyOutputFormatter
from src.core.diagnostics import DiagnosticReport


# Ren'Py dil kodları -> API dil kodları dönüşümü
# Merkezi config'den dinamik olarak oluşturulur
def _get_renpy_to_api_lang():
    """Get Ren'Py to API language mapping from centralized config."""
    try:
        from src.utils.config import ConfigManager
        config = ConfigManager()
        return config.get_renpy_to_api_map()
    except Exception:
        # Fallback for edge cases where config is not available
        return {
            "turkish": "tr", "english": "en", "german": "de", "french": "fr",
            "spanish": "es", "italian": "it", "portuguese": "pt", "russian": "ru",
            "polish": "pl", "dutch": "nl", "japanese": "ja", "korean": "ko",
            "chinese": "zh", "chinese_s": "zh-CN", "chinese_t": "zh-TW",
            "thai": "th", "vietnamese": "vi", "indonesian": "id", "malay": "ms",
            "hindi": "hi", "persian": "fa", "arabic": "ar", "czech": "cs",
            "danish": "da", "finnish": "fi", "greek": "el", "hebrew": "he",
            "hungarian": "hu", "norwegian": "no", "romanian": "ro", "swedish": "sv",
            "ukrainian": "uk", "bulgarian": "bg", "catalan": "ca", "croatian": "hr",
            "slovak": "sk", "slovenian": "sl", "serbian": "sr",
        }

# Initialize at module load - used throughout the pipeline
RENPY_TO_API_LANG = _get_renpy_to_api_lang()


class PipelineStage(Enum):
    """Pipeline aşamaları"""
    IDLE = "idle"
    VALIDATING = "validating"
    UNREN = "unren"
    GENERATING = "generating"
    PARSING = "parsing"
    TRANSLATING = "translating"
    SAVING = "saving"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class PipelineResult:
    """Pipeline sonucu"""
    success: bool
    message: str
    stage: PipelineStage
    stats: Optional[Dict] = None
    output_path: Optional[str] = None
    error: Optional[str] = None


class TranslationPipeline(QObject):
    """
    Entegre çeviri pipeline'ı.
    
    Akış:
    1. Proje doğrulama
    2. UnRen (gerekirse)
    3. Translate komutu ile tl/<dil>/ oluşturma
    4. tl/<dil>/*.rpy dosyalarını parse etme
    5. old "..." metinlerini çevirme
    6. new "..." alanlarına yazma ve kaydetme
    """

    def _find_rpymc_files(self, directory: str) -> list:
        """Klasörde ve alt klasörlerinde .rpymc dosyalarını bulur."""
        rpymc_files = []
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.endswith('.rpymc'):
                    rpymc_files.append(os.path.join(root, f))
        return rpymc_files

    def _extract_strings_from_rpymc_ast(self, ast_root) -> list:
        """
        AST'den stringleri çıkarır. Tüm metin tiplerini (tek satır, çok satır, uzun paragraflar dahil) eksiksiz yakalar.
        Özellikle 'text', 'content', 'value', 'caption', 'label', 'description' gibi alanları öncelikli kontrol eder.
        """
        strings = set()
        PRIORITY_KEYS = ['text', 'content', 'value', 'caption', 'label', 'description', 'message', 'body']
        def walk(node):
            if isinstance(node, str):
                s = node.strip()
                if len(s) > 2 and not all(c in '\n\r\t ' for c in s):
                    strings.add(s)
            elif isinstance(node, (list, tuple)):
                for item in node:
                    walk(item)
            elif isinstance(node, dict):
                # Önce öncelikli anahtarları gez
                for key in PRIORITY_KEYS:
                    if key in node:
                        walk(node[key])
                # Sonra kalanları gez
                for k, v in node.items():
                    if k not in PRIORITY_KEYS:
                        walk(v)
            elif hasattr(node, '__dict__'):
                d = vars(node)
                for key in PRIORITY_KEYS:
                    if key in d:
                        walk(d[key])
                for k, v in d.items():
                    if k not in PRIORITY_KEYS:
                        walk(v)
        walk(ast_root)
        result = list(strings)
        for i, s in enumerate(result[:3]):
            self.log_message.emit('info', f"[DEBUG] .rpymc extract örnek string {i+1}: {repr(s)[:120]}")
        return result
    
    # Signals
    stage_changed = pyqtSignal(str, str)  # stage, message
    progress_updated = pyqtSignal(int, int, str)  # current, total, text
    log_message = pyqtSignal(str, str)  # level, message
    finished = pyqtSignal(object)  # PipelineResult
    show_warning = pyqtSignal(str, str)  # title, message - for popup warnings
    
    def __init__(
        self,
        config: ConfigManager,
        translation_manager: TranslationManager,
        parent=None
    ):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        
        self.config = config
        self.translation_manager = translation_manager
        self.unren_manager = UnRenManager(config)
        self.tl_parser = TLParser()
        self.diagnostic_report = DiagnosticReport()
        # Use a less alarming name for error log, e.g. pipeline_debug.log
        self.error_log_path = Path("pipeline_debug.log")
        self.normalize_count = 0
        
        # State
        self.current_stage = PipelineStage.IDLE
        self.should_stop = False
        self.is_running = False
        # Settings (default values; overridden via configure)
        self.game_exe_path: Optional[str] = None
        self.project_path: Optional[str] = None
        self.target_language: str = "turkish"
        self.source_language: str = "en"
        self.engine: TranslationEngine = TranslationEngine.GOOGLE
        self.auto_unren: bool = True
        self.use_proxy: bool = False

    def _log_error(self, message: str):
        """Persist errors for later inspection (not shown to user as 'fatal')."""
        # Only log if debug mode is enabled or config allows debug logs
        if getattr(self.config, 'debug_mode', False) or getattr(self, 'always_log_errors', False):
            try:
                with self.error_log_path.open("a", encoding="utf-8") as f:
                    f.write(message + "\n")
            except Exception:
                self.logger.debug(f"Error log yazılamadı: {message}")
        # Also record diagnostic-level errors
        try:
            self.diagnostic_report.mark_skipped('pipeline', f'error:{message}')
        except Exception:
            pass
    
    def configure(
        self,
        game_exe_path: str,
        target_language: str,
        source_language: str = "en",
        engine: TranslationEngine = TranslationEngine.GOOGLE,
        auto_unren: bool = True,
        use_proxy: bool = False,
        include_deep_scan: bool = False,
        include_rpyc: bool = False
    ):
        """Pipeline ayarlarını yapılandır"""
        self.include_deep_scan = include_deep_scan
        self.include_rpyc = include_rpyc
        self.game_exe_path = game_exe_path
        # Normalize project path: if the selected EXE is inside a 'game' folder,
        # prefer the parent directory as the project root to match the
        # expected structure (root/game/...)
        candidate = os.path.dirname(game_exe_path)
        try:
            if os.path.basename(candidate).lower() == 'game':
                # EXE located inside <project>/game/Game.exe; use project root
                candidate = os.path.dirname(candidate)
                self.log_message.emit('info', self.config.get_ui_text('pipeline_project_normalize_game'))
            elif not os.path.isdir(os.path.join(candidate, 'game')):
                # If candidate lacks a game folder but parent has it, use parent
                parent = os.path.dirname(candidate)
                if os.path.isdir(os.path.join(parent, 'game')):
                    candidate = parent
                    self.log_message.emit('info', self.config.get_ui_text('pipeline_project_normalize_parent'))
        except Exception:
            # Defensive: if any error occurs, fall back to dirname
            candidate = os.path.dirname(game_exe_path)
        # If normalization adjusted the path, notify the UI via a warning
        original = os.path.dirname(game_exe_path)
        self.project_path = candidate
        if os.path.normcase(original) != os.path.normcase(candidate):
            # Emit a friendly warning to explain what's changed
            try:
                title = self.config.get_ui_text('warning')
                template = self.config.get_ui_text('pipeline_project_normalized')
                message = template.replace('{path}', str(candidate))
                self.show_warning.emit(title, message)
            except Exception:
                # ignore any UI failure
                pass
        self.target_language = target_language
        self.source_language = source_language
        self.engine = engine
        self.auto_unren = auto_unren
        self.use_proxy = use_proxy
    
    def stop(self):
        """Pipeline'ı durdur"""
        self.should_stop = True
        self.log_message.emit("warning", self.config.get_ui_text("stop_requested"))
    
    def _set_stage(self, stage: PipelineStage, message: str = ""):
        """Aşamayı değiştir ve sinyal gönder"""
        self.current_stage = stage
        self.stage_changed.emit(stage.value, message)
        self.log_message.emit("info", f"[{stage.value.upper()}] {message}")
    
    def run(self):
        """Pipeline'ı çalıştır"""
        self.is_running = True
        self.should_stop = False
        
        try:
            result = self._run_pipeline()
            self.finished.emit(result)
        except Exception as e:
            self.logger.exception("Pipeline hatası")
            result = PipelineResult(
                success=False,
                message=f"Beklenmeyen hata: {str(e)}",
                stage=PipelineStage.ERROR,
                error=str(e)
            )
            self.finished.emit(result)
        finally:
            self.is_running = False
    
    def _run_pipeline(self) -> PipelineResult:
        """Ana pipeline akışı"""
        
        # 1. Doğrulama
        self._set_stage(PipelineStage.VALIDATING, self.config.get_ui_text("stage_validating"))
        
        if not self.game_exe_path or not os.path.isfile(self.game_exe_path):
            return PipelineResult(
                success=False,
                message=self.config.get_ui_text("pipeline_invalid_exe"),
                stage=PipelineStage.ERROR
            )
        
        # Ensure project_path is normalized in case the user selected an EXE
        # inside a 'game' subfolder or in a nested path.
        project_path = self.project_path
        try:
            # If project_path currently points to a 'game' folder, normalize up one level
            if os.path.basename(project_path).lower() == 'game':
                self.log_message.emit('info', self.config.get_ui_text('pipeline_project_normalize_game'))
                project_path = os.path.dirname(project_path)
            # If project_path doesn't have a 'game' folder but parent does, normalize up
            elif not os.path.isdir(os.path.join(project_path, 'game')):
                parent = os.path.dirname(project_path)
                if os.path.isdir(os.path.join(parent, 'game')):
                    self.log_message.emit('info', self.config.get_ui_text('pipeline_project_normalize_parent'))
                    project_path = parent
        except Exception:
            # on failure, leave project_path as-is
            pass
        game_dir = os.path.join(project_path, 'game')
        
        if not os.path.isdir(game_dir):
            return PipelineResult(
                success=False,
                message=self.config.get_ui_text("pipeline_game_folder_missing"),
                stage=PipelineStage.ERROR
            )
        
        # .rpy dosyası kontrolü
        has_rpy = self._has_rpy_files(game_dir)
        has_rpyc = self._has_rpyc_files(game_dir)
        has_rpa = self._has_rpa_files(game_dir)  # Arşiv dosyası kontrolü

        # .rpymc dosyalarını bul ve gerçek AST tabanlı okuyucuyu kullan
        rpymc_files = self._find_rpymc_files(game_dir)
        self.rpymc_entries = []
        if rpymc_files:
            from src.core.rpyc_reader import extract_texts_from_rpyc
            for rpymc_path in rpymc_files:
                try:
                    texts = extract_texts_from_rpyc(rpymc_path)
                    for t in texts:
                        text_val = t.get('text') or ""
                        if not text_val:
                            continue
                        ctx_path = t.get('context_path') or []
                        if isinstance(ctx_path, str):
                            ctx_path = [ctx_path]
                        entry = TranslationEntry(
                            original_text=text_val,
                            translated_text="",
                            file_path=str(rpymc_path),
                            line_number=t.get('line_number', 0) or 0,
                            entry_type="rpymc",
                            character=t.get('character'),
                            source_comment=None,
                            block_id=None,
                            context_path=ctx_path,
                            translation_id=TLParser.make_translation_id(
                                    str(rpymc_path), t.get('line_number', 0) or 0, text_val, ctx_path, t.get('raw_text')
                                )
                        )
                        self.rpymc_entries.append(entry)
                except Exception as e:
                    msg = f".rpymc extraction failed: {rpymc_path} ({e})"
                    self.log_message.emit('warning', msg)
                    self._log_error(msg)

            # DEBUG: .rpymc entry sayısını logla
            self.log_message.emit('info', self.config.get_log_text('rpymc_entry_count', count=len(self.rpymc_entries)))
        
        if self.should_stop:
            return self._stopped_result()
        
        # 2. UnRen (gerekirse) - .rpyc VEYA .rpa dosyası varsa çalıştır
        needs_unren = not has_rpy and (has_rpyc or has_rpa) and self.auto_unren
        if needs_unren:
            self.log_message.emit("info", self.config.get_log_text('unren_needed', has_rpy=has_rpy, has_rpyc=has_rpyc, has_rpa=has_rpa))
            self._set_stage(PipelineStage.UNREN, self.config.get_ui_text("stage_unren"))
            
            success = self._run_unren(project_path)
            
            if not success:
                return PipelineResult(
                    success=False,
                    message=self.config.get_ui_text("unren_launch_failed").format(error=""),
                    stage=PipelineStage.ERROR
                )
            
            # Tekrar kontrol
            has_rpy = self._has_rpy_files(game_dir)
        
        if not has_rpy:
            return PipelineResult(
                success=False,
                message=self.config.get_ui_text("pipeline_no_rpy_files"),
                stage=PipelineStage.ERROR
            )
        
        if self.should_stop:
            return self._stopped_result()
        
        # 2.5. Kaynak dosyaları çevrilebilir hale getir
        self._set_stage(PipelineStage.GENERATING, self.config.get_ui_text("stage_generating"))
        self._make_source_translatable(game_dir)
        
        if self.should_stop:
            return self._stopped_result()
        
        # 3. Translate komutu
        self._set_stage(PipelineStage.GENERATING, f"{self.config.get_ui_text('stage_generating')} ({self.target_language})")
        
        tl_dir = os.path.join(game_dir, 'tl', self.target_language)
        
        # Zaten varsa atla
        if not os.path.isdir(tl_dir) or not self._has_rpy_files(tl_dir):
            success = self._run_translate_command(project_path)
            
            if not success:
                return PipelineResult(
                    success=False,
                    message=self.config.get_ui_text("pipeline_translate_failed"),
                    stage=PipelineStage.ERROR
                )
        else:
            self.log_message.emit("info", self.config.get_ui_text("pipeline_tl_exists_skip").replace("{lang}", str(self.target_language)))
        
        if self.should_stop:
            return self._stopped_result()
        
        # 4. Parse
        self._set_stage(PipelineStage.PARSING, self.config.get_ui_text("stage_parsing"))
        
        # Ren'Py klasör adı ile API/ISO kodunu eşle
        reverse_lang_map = {v.lower(): k for k, v in RENPY_TO_API_LANG.items()}
        renpy_lang = reverse_lang_map.get(self.target_language.lower(), self.target_language)

        tl_path = os.path.join(game_dir, 'tl')
        tl_files = self.tl_parser.parse_directory(tl_path, renpy_lang)


        # Yaln?zca hedef dil alt?ndaki dosyalar? kabul et; di?er dil klas?rlerini hari? tut
        target_tl_dir = os.path.normcase(os.path.join(tl_path, renpy_lang))
        filtered_files: List[TranslationFile] = []
        for tl_file in tl_files:
            fp_norm = os.path.normcase(tl_file.file_path)
            if fp_norm.startswith(target_tl_dir):
                tl_file.entries = [
                    e for e in tl_file.entries
                    if os.path.normcase(e.file_path or tl_file.file_path).startswith(target_tl_dir)
                ]
                filtered_files.append(tl_file)
            else:
                self.log_message.emit("info", self.config.get_log_text('other_lang_folder_skipped', path=tl_file.file_path))
        tl_files = filtered_files


        # Phase 5: Deep Scan Integration
        if getattr(self, 'include_deep_scan', False):
            self.log_message.emit("info", self.config.get_log_text('deep_scan_running'))
            try:
                parser = RenPyParser()
                # Scan source files
                scan_res = parser.extract_combined(
                    str(game_dir), include_rpy=True, include_rpyc=True, 
                    include_deep_scan=True, recursive=True
                )
                
                existing = {e.original_text for t in tl_files for e in t.entries}
                missing = []
                for entries in scan_res.values():
                    for e in entries:
                        txt = e.get('text')
                        if txt and txt not in existing and len(txt) > 1:
                            missing.append(e)
                            existing.add(txt)
                
                if missing:
                     self.log_message.emit("info", self.config.get_log_text('deep_scan_found', count=len(missing)))
                     deepscan_dir = os.path.join(tl_path, renpy_lang)
                     os.makedirs(deepscan_dir, exist_ok=True)
                     d_file = os.path.join(deepscan_dir, "strings_deepscan.rpy")
                     
                     lines = ["# Deep Scan generated translations", f"translate {renpy_lang} strings:\n"]
                     for m in missing:
                         o = m['text'].replace('"', '\\"').replace('\n', '\\n')
                         if m.get('context'): lines.append(f"    # context: {m['context']}")
                         lines.append(f'    old "{o}"\n    new ""\n')
                         
                     with open(d_file, 'w', encoding="utf-8") as f:
                         f.write('\n'.join(lines))
                         
                     # Add new file to pipeline processing
                     for ntf in self.tl_parser.parse_directory(deepscan_dir, renpy_lang):
                         if os.path.normcase(ntf.file_path) == os.path.normcase(d_file):
                             tl_files.append(ntf)
                             break
            except Exception as e:
                self.log_message.emit("warning", self.config.get_log_text('deep_scan_error', error=str(e)))

        # Hata raporunda görülen UnicodeDecodeError'ları engellemek için tl çıktısını
        # tümüyle UTF-8-SIG formatında normalize et (renpy loader katı UTF-8 kullanıyor).
        try:
            normalized = self._normalize_tl_encodings(os.path.join(tl_path, renpy_lang))
            if normalized:
                self.log_message.emit("info", f"{normalized} tl dosyası UTF-8'e normalize edildi")
                self.normalize_count = normalized
        except Exception as e:
            msg = f"tl encoding normalize başarısız: {e}"
            self.log_message.emit("warning", msg)
            self._log_error(msg)
        
        if not tl_files:
            return PipelineResult(
                success=False,
                message=self.config.get_ui_text("pipeline_files_not_found_parse"),
                stage=PipelineStage.ERROR
            )
        
        # Çevrilmemiş girişleri topla
        all_entries = []
        for tl_file in tl_files:
            all_entries.extend(tl_file.get_untranslated())

        # Initialize diagnostic report
        try:
            self.diagnostic_report.project = os.path.basename(os.path.abspath(game_dir))
            self.diagnostic_report.target_language = self.target_language
            for tl_file in tl_files:
                # record extracted counts based on entries
                for e in tl_file.entries:
                    fp = e.file_path or tl_file.file_path
                    self.diagnostic_report.add_extracted(fp, {
                        'text': e.original_text,
                        'line_number': e.line_number,
                        'context_path': getattr(e, 'context_path', [])
                    })
        except Exception:
            pass
        
        if not all_entries:
            stats = get_translation_stats(tl_files)
            if game_dir and os.path.isdir(game_dir):
                self._create_language_init_file(str(game_dir))
            return PipelineResult(
                success=True,
                message=self.config.get_ui_text("pipeline_all_already_translated"),
                stage=PipelineStage.COMPLETED,
                stats=stats,
                output_path=tl_dir
            )
        
        self.log_message.emit("info", self.config.get_ui_text("pipeline_entries_to_translate").replace("{count}", str(len(all_entries))))
        
        if self.should_stop:
            return self._stopped_result()
        
        # --- .rpymc entry'lerini all_entries'ye ekle ---
        if getattr(self, 'rpymc_entries', None):
            self.log_message.emit('info', f"[RPYMC] {len(self.rpymc_entries)} adet .rpymc entry ekleniyor")
            all_entries.extend(self.rpymc_entries)
        
        # 5. Çeviri
        self._set_stage(PipelineStage.TRANSLATING, self.config.get_ui_text("stage_translating"))
        
        translations = self._translate_entries(all_entries)
        
        if self.should_stop:
            return self._stopped_result()
        
        if not translations:
            return PipelineResult(
                success=False,
                message=self.config.get_ui_text("pipeline_translate_failed"),
                stage=PipelineStage.ERROR
            )
        
        # 6. Kaydetme
        self._set_stage(PipelineStage.SAVING, self.config.get_ui_text("stage_saving"))
        
        saved_count = 0
        for tl_file in tl_files:
            # Bu dosyaya ait çevirileri filtrele
            file_translations = {}
            for entry in tl_file.entries:
                # original_text kullan (old_text property olarak da çalışır)
                tid = getattr(entry, 'translation_id', '') or TLParser.make_translation_id(
                    entry.file_path, entry.line_number, entry.original_text
                )
                if tid in translations:
                    file_translations[tid] = translations[tid]
                elif entry.original_text in translations:
                    file_translations[entry.original_text] = translations[entry.original_text]
            
            if file_translations:
                success = self.tl_parser.save_translations(tl_file, file_translations)
                if success:
                    saved_count += 1
                    # Diagnostics: mark written entries
                    try:
                        for tid in file_translations.keys():
                            # find file path
                            fp = tl_file.file_path
                            self.diagnostic_report.mark_written(fp, tid)
                    except Exception:
                        pass
        
        # 7. Dil başlatma kodu oluştur (game/ klasörüne)
        self._create_language_init_file(game_dir)
        
        # Final istatistikler
        # Dosyaları yeniden parse et
        tl_files_updated = self.tl_parser.parse_directory(tl_path, self.target_language)
        stats = get_translation_stats(tl_files_updated)

        # Write diagnostics JSON next to tl folder
        try:
            diag_path = os.path.join(tl_dir, 'diagnostics', f'diagnostic_{self.target_language}.json')
            self.diagnostic_report.write(diag_path)
            self.log_message.emit('info', f"Diagnostic report yazildiıldı: {diag_path}")
        except Exception:
            pass
        
        # Hedef dil icin dil baslatici dosyasi olustur
        if game_dir and os.path.isdir(game_dir):
            self._create_language_init_file(str(game_dir))

        self._set_stage(PipelineStage.COMPLETED, self.config.get_ui_text("stage_completed"))
        summary = self.config.get_ui_text("pipeline_completed_summary").replace("{translated}", str(len(translations))).replace("{saved}", str(saved_count))
        if self.normalize_count:
            summary += f" | Normalize edilen tl dosyası: {self.normalize_count}"
        
        return PipelineResult(
            success=True,
            message=summary,
            stage=PipelineStage.COMPLETED,
            stats=stats,
            output_path=tl_dir
        )
    
    def _stopped_result(self) -> PipelineResult:
        """Durduruldu sonucu"""
        return PipelineResult(
            success=False,
            message=self.config.get_ui_text("pipeline_user_stopped"),
            stage=PipelineStage.IDLE
        )
    
    def _has_rpy_files(self, directory: str) -> bool:
        """Klasörde .rpy dosyası var mı?"""
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.endswith('.rpy'):
                    return True
        return False
    
    def _has_rpyc_files(self, directory: str) -> bool:
        """Klasörde .rpyc dosyası var mı?"""
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.endswith('.rpyc'):
                    return True
        return False
    
    def _has_rpa_files(self, directory: str) -> bool:
        """Klasörde .rpa arşiv dosyası var mı?"""
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.endswith('.rpa'):
                    return True
        return False

    def _normalize_tl_encodings(self, tl_dir: str) -> int:
        """
        tl/<lang> içindeki .rpy dosyalarını UTF-8-SIG'e yeniden yazar.
        Ren'Py loader'ı 'python_strict' ile okuduğu için geçersiz byte'lar
        (örn. 0xBE) oyunu düşürüyor; burada tamamını normalize ediyoruz.
        """
        tl_path = Path(tl_dir)
        if not tl_path.exists():
            return 0

        normalized = 0
        for file_path in tl_path.rglob("*.rpy"):
            try:
                if normalize_to_utf8_sig(file_path):
                    normalized += 1
            except Exception as e:
                self.log_message.emit("warning", self.config.get_log_text('encoding_normalize_failed', path=file_path, error=str(e)))
        return normalized
    
    def _create_language_init_file(self, game_dir: str):
        """
        Dil baslangic dosyasini olusturur.
        game/ klasorune yazilir, boylece oyun baslarken varsayilan dil ayarlanir.
        """
        try:
            # Hedef dil kodunu hesapla; ISO gelirse Ren'Py adina cevir
            language_code = (getattr(self, 'target_language', None) or '').strip().lower()
            if not language_code:
                try:
                    language_code = getattr(self.config.translation_settings, 'target_language', '') or ''
                except Exception:
                    language_code = ''
            original_input = language_code
            reverse_lang_map = {v.lower(): k for k, v in RENPY_TO_API_LANG.items()}
            if language_code:
                language_code = reverse_lang_map.get(language_code, language_code)
            else:
                # Hedef bilinmiyorsa tl alt klasorlerini kontrol et; yalnizca tek klasor varsa kullan
                tl_root = Path(game_dir) / "tl"
                subdirs = sorted([p.name for p in tl_root.iterdir() if p.is_dir()]) if tl_root.exists() else []
                if len(subdirs) == 1:
                    language_code = subdirs[0].lower()
                    self.log_message.emit("info", self.config.get_log_text('target_lang_auto', lang=language_code))
                else:
                    language_code = 'turkish'
                    self.log_message.emit("warning", self.config.get_log_text('target_lang_default'))

            # Once eski otomatik init dosyalarini temizle ki tek dosya aktif kalsin
            try:
                for existing in Path(game_dir).glob("a0_*_language.rpy"):
                    if existing.name != f"a0_{language_code}_language.rpy":
                        existing.unlink(missing_ok=True)
                        self.log_message.emit("info", self.config.get_log_text('old_lang_init_deleted', name=existing.name))
            except Exception:
                pass

            # Dosya adi: a0_[lang]_language.rpy (RenPy dokumantasyonuna uygun, one cikar)
            init_file = os.path.join(game_dir, f'a0_{language_code}_language.rpy')

            self.log_message.emit(
                "info",
                self.config.get_ui_text("pipeline_lang_init_check").replace("{path}", init_file)
                + f" | dil={language_code} (input={original_input or 'none'})"
            )

            # Zaten varsa sil ve yeniden olustur (guncellemek icin)
            if os.path.exists(init_file):
                os.remove(init_file)
                self.log_message.emit("info", self.config.get_ui_text("pipeline_lang_init_update"))

            # Sade ve dinamik baslaticinin icerigi
            content = f'define config.language = "{language_code}"\n'

            with open(init_file, 'w', encoding='utf-8-sig', newline='\n') as f:
                f.write(content)

            self.log_message.emit("info", self.config.get_ui_text("pipeline_lang_init_created").replace("{path}", init_file))

        except Exception as e:
            self.log_message.emit("warning", self.config.get_ui_text("pipeline_lang_init_failed").format(error=e))






    def translate_existing_tl(
        self,
        tl_root_path: str,
        target_language: str,
        source_language: str = "auto",
        engine: TranslationEngine = TranslationEngine.GOOGLE,
        use_proxy: bool = False,
    ) -> PipelineResult:
        """
        Var olan tl/<dil> klasorundeki .rpy dosyalarini (Ren'Py SDK ile uretildi)
        dogrudan cevirir. Oyunun EXE'sine gerek yoktur.
        """
        # GUI ISO kodu (fr/en/tr) gonderir; Ren'Py klasor adi icin ters cevir
        reverse_lang_map = {v.lower(): k for k, v in RENPY_TO_API_LANG.items()}
        target_iso = (target_language or "").lower()
        renpy_lang = reverse_lang_map.get(target_iso, target_iso)

        # Konfigure et
        self.target_language = target_iso
        self.source_language = source_language
        self.engine = engine
        self.use_proxy = use_proxy
        self.project_path = os.path.abspath(Path(tl_root_path).parent.parent) if tl_root_path else None

        # Stage: PARSING
        self._set_stage(PipelineStage.PARSING, self.config.get_ui_text("stage_parsing"))

        # tl_path / lang_dir coz
        p = Path(tl_root_path)
        lang_dir: Optional[Path] = None
        tl_path: Optional[Path] = None

        target_dir_names: List[str] = []
        for name in [renpy_lang, target_iso]:
            if name and name not in target_dir_names:
                target_dir_names.append(name)

        def matches_name(path_obj: Path) -> bool:
            return path_obj.name.lower() in target_dir_names

        # 1) Kullanici zaten tl/<lang> secmis
        if matches_name(p) and p.parent.name.lower() == "tl":
            lang_dir = p
            tl_path = p.parent
        # 2) Kullanici tl dizinini secmis (game/tl)
        elif p.name.lower() == "tl":
            tl_path = p
            for name in target_dir_names:
                candidate = tl_path / name
                if candidate.exists():
                    lang_dir = candidate
                    break
        # 3) Kullanici oyun/project root secmis
        if lang_dir is None and (p / "tl").exists():
            tl_path = p / "tl"
            for name in target_dir_names:
                candidate = tl_path / name
                if candidate.exists():
                    lang_dir = candidate
                    break
        # 4) Son care: secilen dizin altinda dil klasoru var mi?
        if lang_dir is None:
            for name in target_dir_names:
                candidate = p / name
                if candidate.exists():
                    lang_dir = candidate
                    tl_path = p if p.name.lower() == "tl" else p.parent if p.parent.name.lower() == "tl" else p
                    break
        # 5) Ad uyusmasa bile kullanici dogrudan dil klasorunu secmis olabilir
        if lang_dir is None and p.is_dir():
            try:
                has_rpy = next(p.rglob("*.rpy"), None) is not None
            except Exception:
                has_rpy = False
            if has_rpy:
                lang_dir = p
                tl_path = p.parent if p.parent else p

        if lang_dir is None:
            return PipelineResult(
                success=False,
                message=f"TL dil klasoru bulunamadi: {p} ({'/'.join(target_dir_names)})",
                stage=PipelineStage.ERROR,
            )

        if not lang_dir.exists():
            return PipelineResult(
                success=False,
                message=f"TL dil klasoru bulunamadi: {lang_dir}",
                stage=PipelineStage.ERROR,
            )

        # Bilgilendirici log
        self.log_message.emit(
            "info",
            f"TL dizini: {tl_path} | Dil klasoru: {lang_dir.name} (input={target_language})",
        )

        # Oyun dizinini tahmin et (tl/<lang> altindaysa bir ust = game)
        game_dir = None
        try:
            if lang_dir.parent.name.lower() == "tl":
                game_dir = lang_dir.parent.parent
            elif tl_path and tl_path.name.lower() == "tl":
                game_dir = tl_path.parent
        except Exception:
            game_dir = None

        tl_files = self.tl_parser.parse_directory(str(tl_path), lang_dir.name)

        # Yalnizca hedef dil altindaki dosyalari kabul et; diger dil klasorlerini haric tut
        target_tl_dir = os.path.normcase(os.path.join(str(tl_path), lang_dir.name))
        filtered_files: List[TranslationFile] = []
        for tl_file in tl_files:
            fp_norm = os.path.normcase(tl_file.file_path)
            if fp_norm.startswith(target_tl_dir):
                tl_file.entries = [
                    e for e in tl_file.entries
                    if os.path.normcase(e.file_path or tl_file.file_path).startswith(target_tl_dir)
                ]
                filtered_files.append(tl_file)
            else:
                self.log_message.emit("info", f"Baska dil klasoru atlandi: {tl_file.file_path}")
        tl_files = filtered_files

        # Encode normalizasyonu (hedef dil klasoru)
        try:
            normalized = self._normalize_tl_encodings(str(lang_dir))
            if normalized:
                self.log_message.emit("info", f"{normalized} tl dosyasi UTF-8'e normalize edildi")
                self.normalize_count = normalized
        except Exception as e:
            msg = f"tl encoding normalize basarisiz: {e}"
            self.log_message.emit("warning", msg)
            self._log_error(msg)

        if not tl_files:
            return PipelineResult(
                success=False,
                message=self.config.get_ui_text("pipeline_files_not_found_parse"),
                stage=PipelineStage.ERROR,
            )

        # Cevrilecek girisleri topla
        all_entries: List[TranslationEntry] = []
        for tl_file in tl_files:
            all_entries.extend(tl_file.get_untranslated())

        # Diagnostics baslangic bilgisi
        try:
            self.diagnostic_report.project = os.path.basename(os.path.abspath(tl_root_path))
            self.diagnostic_report.target_language = self.target_language
            for tl_file in tl_files:
                for e in tl_file.entries:
                    fp = e.file_path or tl_file.file_path
                    self.diagnostic_report.add_extracted(fp, {
                        'text': e.original_text,
                        'line_number': e.line_number,
                        'context_path': getattr(e, 'context_path', [])
                    })
        except Exception:
            pass

        if not all_entries:
            stats = get_translation_stats(tl_files)
            return PipelineResult(
                success=True,
                message=self.config.get_ui_text("pipeline_all_already_translated"),
                stage=PipelineStage.COMPLETED,
                stats=stats,
                output_path=str(lang_dir)
            )

        self.log_message.emit("info", self.config.get_ui_text("pipeline_entries_to_translate").replace("{count}", str(len(all_entries))))

        # Stage: TRANSLATING
        self._set_stage(PipelineStage.TRANSLATING, self.config.get_ui_text("stage_translating"))
        translations = self._translate_entries(all_entries)

        if not translations:
            return PipelineResult(
                success=False,
                message=self.config.get_ui_text("pipeline_translate_failed"),
                stage=PipelineStage.ERROR
            )

        # Stage: SAVING
        self._set_stage(PipelineStage.SAVING, self.config.get_ui_text("stage_saving"))
        saved_count = 0
        for tl_file in tl_files:
            file_translations: Dict[str, str] = {}
            for entry in tl_file.entries:
                tid = getattr(entry, 'translation_id', '') or TLParser.make_translation_id(
                    entry.file_path, entry.line_number, entry.original_text
                )
                if tid in translations:
                    file_translations[tid] = translations[tid]
                elif entry.original_text in translations:
                    file_translations[entry.original_text] = translations[entry.original_text]

            if file_translations:
                success = self.tl_parser.save_translations(tl_file, file_translations)
                if success:
                    saved_count += 1
                    try:
                        for tid in file_translations.keys():
                            fp = tl_file.file_path
                            self.diagnostic_report.mark_written(fp, tid)
                    except Exception:
                        pass

        # Final istatistikler
        tl_files_updated = self.tl_parser.parse_directory(str(tl_path), lang_dir.name)
        stats = get_translation_stats(tl_files_updated)

        # Diagnostics JSON yaz
        try:
            diag_path = os.path.join(str(lang_dir), 'diagnostics', f'diagnostic_{self.target_language}.json')
            self.diagnostic_report.write(diag_path)
            self.log_message.emit('info', f"Diagnostic report yazildi: {diag_path}")
        except Exception:
            pass

        # Hedef dil icin dil baslatici dosyasi olustur
        if game_dir and game_dir.exists():
            self._create_language_init_file(str(game_dir))

        self._set_stage(PipelineStage.COMPLETED, self.config.get_ui_text("stage_completed"))
        summary = self.config.get_ui_text("pipeline_completed_summary").replace("{translated}", str(len(translations))).replace("{saved}", str(saved_count))
        if self.normalize_count:
            summary += f" | Normalize edilen tl dosyasi: {self.normalize_count}"

        return PipelineResult(
            success=True,
            message=summary,
            stage=PipelineStage.COMPLETED,
            stats=stats,
            output_path=str(lang_dir)
        )

    def _make_source_translatable(self, game_dir: str) -> int:
        """
        Kaynak .rpy dosyalarındaki UI metinlerini çevrilebilir hale getirir.
        textbutton "Text" -> textbutton _("Text")
        textbutton 'Text' -> textbutton _('Text')
        Bu işlem Ren'Py'ın translate komutunun bu metinleri yakalamasını sağlar.
        
        Returns: Değiştirilen dosya sayısı
        """
        # Çevrilebilir yapılması gereken pattern'ler
        # Her pattern: (regex_pattern, replacement)
        # 
        # Önemli Ren'Py UI Elemanları:
        # - textbutton: Tıklanabilir metin butonu
        # - text: Ekranda gösterilen metin
        # - tooltip: Fare üzerine gelince gösterilen ipucu
        # - label: Metin etiketi (nadiren çeviri gerektirir)
        # - notify: Bildirim mesajları (renpy.notify)
        # - action Notify: Action olarak bildirim
        # - title: Pencere başlığı
        # - message: Onay/hata mesajları
        #
        # NOT: Her pattern hem tek tırnak (') hem de çift tırnak (") destekler
        # ['\"] = tek veya çift tırnak eşleşir, \\1 ile aynı tırnak kullanılır
        #
        patterns = [
            # textbutton "text" veya textbutton 'text' -> textbutton _("text")
            # Ör: textbutton "Nap": veya textbutton 'Start' action Start()
            (r"(textbutton\s+)(['\"])([^'\"]+)\2(\s*:|\s+action|\s+style|\s+xalign|\s+yalign|\s+at\s)", 
             r'\1_(\2\3\2)\4'),
            
            # text "..." veya text '...' size/color/xpos/ypos/xalign/yalign/outlines/at ile devam eden
            # Ör: text "LOCKED" color "#FF6666" size 50
            # Ör: text 'Quit':
            # NOT: text "[variable]" gibi değişken içerenleri atla (skip_patterns ile)
            (r"(\btext\s+)(['\"])([^'\"\[\]{}]+)\2(\s*:|\s+size|\s+color|\s+xpos|\s+ypos|\s+xalign|\s+yalign|\s+outlines|\s+at\s|\s+font|\s+style)", 
             r'\1_(\2\3\2)\4'),
            
            # tooltip "text" veya tooltip 'text' -> tooltip _("text")
            # Ör: tooltip "Dev Console (Toggle)"
            (r"(tooltip\s+)(['\"])([^'\"]+)\2", 
             r'\1_(\2\3\2)'),
            
            # renpy.notify("text") veya renpy.notify('text') -> renpy.notify(_("text"))
            # Ör: renpy.notify("Item added to inventory")
            (r"(renpy\.notify\s*\(\s*)(['\"])([^'\"]+)\2(\s*\))", 
             r'\1_(\2\3\2)\4'),
            
            # action Notify("text") veya Notify('text') -> action Notify(_("text"))
            # Ör: action Notify("Game saved!")
            (r"(Notify\s*\(\s*)(['\"])([^'\"]+)\2(\s*\))", 
             r'\1_(\2\3\2)\4'),
            
            # title="text" veya title='text' (screen title vb.)
            # Ör: title="Settings" veya frame title 'Options':
            (r"(title\s*=\s*)(['\"])([^'\"]+)\2", 
             r'\1_(\2\3\2)'),
            
            # message="text" veya message='text' (confirm screen vb.)
            # Ör: message="Are you sure you want to quit?"
            (r"(message\s*=\s*)(['\"])([^'\"]+)\2", 
             r'\1_(\2\3\2)'),
            
            # yes="text" (confirm)
            # Ör: yes="Yes" 
            (r"(\byes\s*=\s*)(['\"])([^'\"]+)\2", 
             r'\1_(\2\3\2)'),
            
            # no="text" (confirm)  
            # Ör: no="No"
            (r"(\bno\s*=\s*)(['\"])([^'\"]+)\2", 
             r'\1_(\2\3\2)'),
            
            # alt="text" (image alt text)
            # Ör: add "image.png" alt="A beautiful sunset"
            (r"(\balt\s*=\s*)(['\"])([^'\"]+)\2", 
             r'\1_(\2\3\2)'),
        ]
        
        # Atlanacak pattern'ler (zaten çevrilebilir veya değişken)
        # Hem tek (') hem çift (") tırnak desteklenir
        skip_patterns = [
            r'_\s*\(\s*[\'"]',    # Zaten çevrilebilir: _("text") veya _('text')
            r'[\'\"]\s*\+\s*[\'"]',    # String concatenation: "text" + "more"
            r'^\s*#',             # Yorum satırı
            r'^\s*$',             # Boş satır
            r'define\s+',         # define satırları
            r'default\s+',        # default satırları
            r'=\s*[\'"][^\'"]*[\'"]\s*$',  # Sadece atama: variable = "value"
            r'[\'"][^\'"]*\[[^\]]+\][^\'"]*[\'"]',  # Değişken içeren: "[player]"
            r'[\'"][^\'"]*\{[^\}]+\}[^\'"]*[\'"]',  # Tag içeren: "{b}text{/b}"
        ]
        
        modified_count = 0
        rpy_dir = os.path.join(game_dir, 'rpy')
        
        if not os.path.isdir(rpy_dir):
            # rpy alt klasörü yoksa direkt game klasörünü tara
            rpy_dir = game_dir
        
        try:
            for root, dirs, files in os.walk(rpy_dir):
                # tl klasörünü atla
                if 'tl' in dirs:
                    dirs.remove('tl')
                
                for filename in files:
                    if not filename.endswith('.rpy'):
                        continue

                    filepath = os.path.join(root, filename)

                    # GÜVENLİK: 'renpy/' klasörü altındaki dosyaları ASLA değiştirme!
                    if os.path.sep + 'renpy' + os.path.sep in filepath or filepath.endswith(os.path.sep + 'renpy'):
                        self.log_message.emit("debug", self.config.get_log_text('engine_file_skipped', filename=filename))
                        continue
                    
                    try:
                        # Her dosya için yedek oluştur
                        # GÜVENLİK YAMASI: Yedekleme
                        backup_path = filepath + ".bak"
                        if not os.path.exists(backup_path):
                            try:
                                shutil.copy2(filepath, backup_path)
                            except Exception as e:
                                self.log_message.emit("warning", self.config.get_log_text('backup_failed_skipped', filename=filename))
                                continue  # Dosya işlenmeden atlanıyor
                        

                        content = read_text_safely(Path(filepath))
                        if content is None:
                            self.log_message.emit('warning', f"{filename} dosyası okunamadı (encoding)")
                            continue
                        
                        original_content = content
                        
                        # Her pattern için değiştir
                        for pattern, replacement in patterns:
                            # Satır satır işle
                            lines = content.split('\n')
                            new_lines = []
                            
                            for line in lines:
                                # Atlanacak satırları kontrol et
                                should_skip = False
                                for skip in skip_patterns:
                                    if re.search(skip, line):
                                        should_skip = True
                                        break
                                
                                if not should_skip:
                                    line = re.sub(pattern, replacement, line)
                                
                                new_lines.append(line)
                            
                            content = '\n'.join(new_lines)
                        
                        # Değişiklik olduysa kaydet
                        if content != original_content:
                            with open(filepath, 'w', encoding='utf-8-sig', newline='\n') as f:
                                f.write(content)
                            modified_count += 1
                        self.log_message.emit("debug", self.config.get_log_text('file_made_translatable', filename=filename))
                    
                    except Exception as e:
                        msg = f"Dosya işlenemedi {filename}: {e}"
                        self.log_message.emit("warning", msg)
                        self._log_error(msg)
                        continue
            
            if modified_count > 0:
                self.log_message.emit("info", self.config.get_log_text('source_files_made_translatable', count=modified_count))
            
        except Exception as e:
            self.log_message.emit("warning", self.config.get_log_text('source_files_error', error=str(e)))
        
        return modified_count
    
    def _run_unren(self, project_path: str) -> bool:
        """UnRen çalıştır"""
        try:
            self.log_message.emit("info", self.config.get_log_text('unren_starting'))
            
            # UnRen'i indir (gerekirse)
            if not self.unren_manager.is_available():
                self.log_message.emit("info", self.config.get_log_text('unren_downloading'))
                try:
                    self.unren_manager.ensure_available()
                except Exception as e:
                    self.log_message.emit("error", self.config.get_log_text('unren_download_error', error=str(e)))
                    return False
            
            # UnRen çalıştır
            from pathlib import Path
            project_path_obj = Path(project_path)
            
            # Sanity check - ensure script exists and warn if not
            root = self.unren_manager.get_unren_root()
            if root:
                script_candidates = list(root.glob('*.bat')) + list(root.glob('**/*.bat'))
                if not script_candidates:
                    self.log_message.emit("error", self.config.get_log_text('unren_scripts_not_found', path=str(root)))
                    return False
            
            # Ren'Py versiyonuna göre otomatik seçim scripti oluştur
            # UnRen-forall menüsü:
            #   2 = UnRen-current (Ren'Py 8+)
            # UnRen-current menüsü:
            #   5 = Unpack and decompile (RPA and RPYC) - SADECE BU!
            # Ardından gelen sorular:
            #   n = RPA silme (hayır)
            #   a = Tüm RPA'ları aç
            #   n = RPY üzerine yazma (hayır)
            #   x = Çıkış
            # NOT: Eski script "12acefg" varsayılanını kullanıyordu ve ekstra mod dosyaları ekliyordu
            #      (unren-console.rpy, unren-qmenu.rpy vb.) - bunlar bazı oyunlarla uyumsuz!
            automation_script = "2\n5\nn\na\nn\nx\n"
            
            try:
                self.log_message.emit("info", self.config.get_log_text('unren_auto_mode'))
                # Preflight diagnostic
                verify = self.unren_manager.verify_installation()
                if verify.get('scripts'):
                    self.log_message.emit("debug", f"UnRen preflight scripts: {verify.get('scripts')}")
                
                # Capture UnRen logs to detect common failure modes
                captured_logs = []
                collected_errors = []

                def _log_and_collect(msg: str) -> None:
                    captured_logs.append(msg)
                    self.log_message.emit("info", msg)
                    if 'Cannot locate game' in msg or 'Cannot locate game, lib or renpy' in msg:
                        collected_errors.append('cannot_locate_game')

                process = self.unren_manager.run_unren(
                    project_path_obj,
                    variant='auto',
                    wait=True,
                    log_callback=_log_and_collect,
                    automation_script=automation_script,
                    timeout=600  # 10 dakika timeout
                )
                
                # Process tamamlandıysa başarılı
                # If UnRen reports a specific inability to locate project folders,
                # show a helpful popup and abort the pipeline early.
                if collected_errors:
                    self.log_message.emit("warning", self.config.get_log_text('unren_game_not_found'))
                    warning_title = self.config.get_ui_text('unren_log_cannot_locate_game_title') if self.config else 'UnRen hata'
                    warning_message = self.config.get_ui_text('unren_log_cannot_locate_game') if self.config else 'UnRen could not locate game, lib or renpy folders.'
                    self.show_warning.emit(warning_title, warning_message)
                    return False

                # UnRen başarısını kontrol et
                game_dir = os.path.join(project_path, 'game')
                
                # Process None olabilir (bazı durumlarda) - .rpy dosyalarını kontrol et
                if process is None:
                    self.log_message.emit("warning", self.config.get_log_text('unren_process_null_checking'))
                    if self._has_rpy_files(game_dir):
                        self.log_message.emit("info", self.config.get_log_text('unren_rpy_created_success'))
                        self._cleanup_unren_mod_files(game_dir)
                        return True
                    else:
                        self.log_message.emit("error", self.config.get_log_text('unren_rpy_not_found_fail'))
                        return False
                
                if process.returncode == 0:
                    self.log_message.emit("info", self.config.get_log_text('unren_completed'))
                    self._cleanup_unren_mod_files(game_dir)
                    return True
                else:
                    self.log_message.emit("warning", self.config.get_log_text('unren_completed_code', code=process.returncode))
                    # Bazı durumlarda non-zero dönse bile başarılı olabilir
                    # .rpy dosyaları oluşturulduysa başarılı say
                    if self._has_rpy_files(game_dir):
                        self.log_message.emit("info", self.config.get_log_text('unren_rpy_created_continue'))
                        self._cleanup_unren_mod_files(game_dir)
                        return True
                    return False
                    
            except Exception as e:
                self.log_message.emit("error", self.config.get_log_text('unren_error', error=str(e)))
                # Son şans - .rpy dosyaları oluşturulmuş olabilir
                game_dir = os.path.join(project_path, 'game')
                if self._has_rpy_files(game_dir):
                    self.log_message.emit("info", self.config.get_log_text('unren_error_but_rpy_found'))
                    self._cleanup_unren_mod_files(game_dir)
                    return True
                return False
            
        except Exception as e:
            self.log_message.emit("error", self.config.get_log_text('unren_general_error', error=str(e)))
            return False
    
    def _cleanup_unren_mod_files(self, game_dir: str) -> int:
        """
        UnRen'in eklediği mod dosyalarını temizle.
        Bu dosyalar bazı oyunlarla uyumsuz (örn: 'Screen quick_menu is not known' hatası).
        
        Silinen dosyalar:
        - unren-console.rpy / .rpyc
        - unren-qmenu.rpy / .rpyc
        - unren-quick.rpy / .rpyc
        - unren-rollback.rpy / .rpyc
        - unren-skip.rpy / .rpyc
        
        Returns: Silinen dosya sayısı
        """
        cleanup_patterns = [
            "unren-console.rpy", "unren-console.rpyc",
            "unren-qmenu.rpy", "unren-qmenu.rpyc",
            "unren-quick.rpy", "unren-quick.rpyc",
            "unren-rollback.rpy", "unren-rollback.rpyc",
            "unren-skip.rpy", "unren-skip.rpyc",
        ]
        
        deleted_count = 0
        for filename in cleanup_patterns:
            filepath = os.path.join(game_dir, filename)
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    self.log_message.emit("info", self.config.get_log_text('unren_mod_deleted', filename=filename))
                    deleted_count += 1
            except Exception as e:
                self.log_message.emit("warning", self.config.get_log_text('unren_mod_delete_failed', filename=filename, error=str(e)))
        
        if deleted_count > 0:
            self.log_message.emit("info", self.config.get_log_text('unren_mod_cleanup_done', count=deleted_count))
        
        return deleted_count
    
    def _run_translate_command(self, project_path: str) -> bool:
        """Kaynak dosyaları parse edip tl/ klasörüne çeviri şablonları oluştur
        
        ÖNEMLİ: Ren'Py String Translation sistemi kullanılıyor.
        Bu sistemde aynı string sadece BİR KERE tanımlanabilir (global tekil).
        Bu nedenle tüm stringler (diyalog + UI) tek bir dosyada toplanıyor.
        """
        try:
            self.log_message.emit("info", f"Çeviri dosyaları oluşturuluyor: {self.target_language}")
            
            # Dil ismini belirle (ISO kodu yerine klasör ismi)
            reverse_lang_map = {v.lower(): k for k, v in RENPY_TO_API_LANG.items()}
            renpy_lang = reverse_lang_map.get(self.target_language.lower(), self.target_language)
            
            game_dir = os.path.join(project_path, 'game')
            tl_dir = os.path.join(game_dir, 'tl', renpy_lang)
            
            # tl dizini oluştur
            os.makedirs(tl_dir, exist_ok=True)
            
            # Kaynak dosyaları parse et
            from src.core.parser import RenPyParser
            parser = RenPyParser(self.config)
            
            # 1. Parse 'game' directory
            # Parse 'game' directory and flatten results
            parse_results = parser.parse_directory(game_dir)
            source_texts = []
            for file_path, entries in parse_results.items():
                for entry in entries:
                    entry['file_path'] = str(file_path)
                    source_texts.append(entry)

            # Resolve feature flags once so they can be reused for engine/common scanning
            use_deep = getattr(self, 'include_deep_scan', False)
            use_rpyc = getattr(self, 'include_rpyc', False)
            
            if self.config and hasattr(self.config, 'translation_settings'):
                settings = self.config.translation_settings
                # If explicit override wasn't set (or False), fallback to config
                if not use_deep:
                    use_deep = getattr(settings, 'enable_deep_scan', getattr(settings, 'use_deep_scan', True))
                if not use_rpyc:
                    use_rpyc = getattr(settings, 'enable_rpyc_reader', getattr(settings, 'use_rpyc', False))

            # Remove any entries that originate from game/renpy/common — we'll re-parse them with
            # a temporary parser that forces UI scanning for engine common strings.
            renpy_common_path = os.path.normpath(os.path.abspath(os.path.join(game_dir, 'renpy', 'common')))
            if os.path.isdir(renpy_common_path):
                before_len = len(source_texts)
                def abs_path(p):
                    try:
                        return os.path.normpath(os.path.abspath(str(p)))
                    except Exception:
                        return ''
                source_texts = [e for e in source_texts if not abs_path(e.get('file_path', '')).startswith(renpy_common_path)]
                after_len = len(source_texts)
                if before_len != after_len:
                    self.log_message.emit('debug', f'Removed {before_len - after_len} entries from initial game parse that belong to renpy/common to avoid duplicates')

            # Explicitly scan 'renpy/common' if it exists in project root
            renpy_dir = os.path.join(project_path, 'renpy')
            renpy_common = os.path.join(renpy_dir, 'common')

            if os.path.isdir(renpy_common):
                self.log_message.emit("info", f"Scanning Ren'Py common directory: {renpy_common}")
                # Parse 'renpy/common' and flatten results
                # Use temporary parser with forced UI scanning so engine UI strings are included
                from src.core.parser import RenPyParser
                from src.utils.config import ConfigManager as LocalConfig
                import copy
                temp_conf = LocalConfig()
                temp_conf.translation_settings = copy.deepcopy(self.config.translation_settings)
                temp_conf.translation_settings.translate_ui = True
                temp_parser = RenPyParser(temp_conf)
                try:
                    common_results = temp_parser.parse_directory(renpy_common)
                except Exception:
                    common_results = parser.parse_directory(renpy_common)
                for file_path, entries in common_results.items():
                    for entry in entries:
                        entry['file_path'] = str(file_path)
                        entry['is_engine_common'] = True
                        source_texts.append(entry)
                # If engine/common ships only .rpyc files, optionally parse them too
                if use_rpyc:
                    try:
                        from src.core.rpyc_reader import extract_texts_from_rpyc_directory
                        rpyc_results = extract_texts_from_rpyc_directory(renpy_common)
                        for file_path, entries in rpyc_results.items():
                            for entry in entries:
                                patched = dict(entry)
                                patched['file_path'] = str(file_path)
                                patched['is_engine_common'] = True
                                if 'text_type' in patched and 'type' not in patched:
                                    patched['type'] = patched.get('text_type')
                                source_texts.append(patched)
                    except Exception as exc:
                        self.log_message.emit("warning", f"Engine common RPYC taraması başarısız: {exc}")
            # Optionally scan installed Ren'Py SDKs' renpy/common directories
            if self.config and hasattr(self.config, 'translation_settings') and getattr(self.config.translation_settings, 'include_engine_common', False):
                try:
                    sdks = find_renpy_sdks()
                    if sdks:
                            self.log_message.emit("info", f"Scanning installed Ren'Py SDK 'common' directories: {len(sdks)} SDKs found")
                            for sdk in sdks:
                                sdk_common = os.path.join(sdk.path, 'renpy', 'common')
                                if os.path.isdir(sdk_common):
                                    self.log_message.emit("info", f"Scanning SDK common: {sdk_common}")
                                    # Use a temporary parser that forces UI scanning so engine UI strings are included
                                    from src.core.parser import RenPyParser
                                    from src.utils.config import ConfigManager as LocalConfig
                                    import copy
                                    temp_conf = LocalConfig()
                                    # Use a deepcopy to avoid mutating the project's active config
                                    temp_conf.translation_settings = copy.deepcopy(self.config.translation_settings)
                                    # Force UI translation for engine SDK parsing regardless of main config
                                    temp_conf.translation_settings.translate_ui = True
                                    temp_parser = RenPyParser(temp_conf)
                                    try:
                                        sdk_results = temp_parser.parse_directory(sdk_common)
                                    except Exception:
                                        # Fallback to project parser if temp parsing fails
                                        sdk_results = parser.parse_directory(sdk_common)
                                    for file_path, entries in sdk_results.items():
                                        for entry in entries:
                                            entry['file_path'] = str(file_path)
                                            # Mark that this entry came from engine SDK common
                                            entry['is_engine_common'] = True
                                            source_texts.append(entry)
                                    if use_rpyc:
                                        try:
                                            from src.core.rpyc_reader import extract_texts_from_rpyc_directory
                                            sdk_rpyc = extract_texts_from_rpyc_directory(sdk_common)
                                            for file_path, entries in sdk_rpyc.items():
                                                for entry in entries:
                                                    patched = dict(entry)
                                                    patched['file_path'] = str(file_path)
                                                    patched['is_engine_common'] = True
                                                    if 'text_type' in patched and 'type' not in patched:
                                                        patched['type'] = patched.get('text_type')
                                                    source_texts.append(patched)
                                        except Exception as exc:
                                            self.log_message.emit("warning", f"SDK engine RPYC taraması başarısız: {exc}")
                except Exception as exc:
                    self.log_message.emit("warning", f"Failed to scan installed Ren'Py SDK common directories: {exc}")
            elif os.path.isdir(os.path.join(game_dir, 'renpy', 'common')):
                 # Handle case where renpy is inside game folder (rare but possible)
                 pass # Already handled by recursive scan of game_dir

            # --- FIX START: Initialize and Populate Results ---
            deep_results = {}
            rpyc_results = {}
            existing_texts = {e['text'] for e in source_texts} # For dedup
            deep_count = 0

            # 3. Deep Scan Execution
            # Check config (default to True if not set)
            if use_deep:
                self.log_message.emit("info", self.config.get_log_text('deep_scan_running_short'))
                deep_results = parser.extract_from_directory_with_deep_scan(game_dir)

            # 4. RPYC Execution
            if use_rpyc:
                self.log_message.emit("info", self.config.get_log_text('rpyc_scan_running'))
                # Import here to avoid circular imports if any
                try:
                    from src.core.rpyc_reader import extract_texts_from_rpyc_directory
                    rpyc_results = extract_texts_from_rpyc_directory(game_dir)
                except ImportError:
                    self.log_message.emit("warning", self.config.get_log_text('rpyc_module_not_found'))
            # --- FIX END ---
            
            # --- EKSİK OLAN BİRLEŞTİRME KODU BAŞLANGICI ---

            # Deep Scan Sonuçlarını Birleştir
            if deep_results:
                self.log_message.emit("info", self.config.get_log_text('deep_scan_merging'))
                for file_path, entries in deep_results.items():
                    for entry in entries:
                        if entry.get('is_deep_scan'):
                            entry['file_path'] = str(file_path)
                            source_texts.append(entry)

            # RPYC Sonuçlarını Birleştir
            if rpyc_results:
                self.log_message.emit("info", self.config.get_log_text('rpyc_data_merging'))
                # Mevcut metinleri kontrol et (tekrarı önlemek için)
                existing_texts = {e.get('text') for e in source_texts}

                for file_path, entries in rpyc_results.items():
                    for entry in entries:
                        text = entry.get('text', '')
                        if text and text not in existing_texts:
                            entry['file_path'] = str(file_path)
                            source_texts.append(entry)
                            existing_texts.add(text)

            # --- EKSİK OLAN BİRLEŞTİRME KODU BİTİŞİ ---
            
            if not source_texts:
                self.log_message.emit("warning", self.config.get_log_text('no_translatable_texts'))
                return False
            
            self.log_message.emit("info", self.config.get_log_text('texts_found_creating', count=len(source_texts)))
            
            # TÜM metinleri GLOBAL olarak tekil tut
            # Ren'Py String Translation'da aynı string sadece 1 kere tanımlanabilir
            # Prefers entries marked as engine_common if duplicates occur
            seen_map = {}
            for entry in source_texts:
                text = entry.get('text', '')
                if not text:
                    continue
                existing = seen_map.get(text)
                if not existing:
                    seen_map[text] = entry
                else:
                    # If the existing one is not engine_common but the new one is, prefer the new
                    if not existing.get('is_engine_common') and entry.get('is_engine_common'):
                        seen_map[text] = entry
                    # Prefer deep_scan or contextful entries over generic ones if needed
                    elif not existing.get('is_deep_scan') and entry.get('is_deep_scan'):
                        seen_map[text] = entry

            all_entries = list(seen_map.values())
            
            self.log_message.emit("info", self.config.get_log_text('unique_texts_found', count=len(all_entries)))
            
            # Tüm stringleri tek strings.rpy dosyasına yaz
            if all_entries:
                try:
                    # Pass renpy_lang to ensure correct header in strings.rpy
                    strings_content = self._generate_all_strings_file(all_entries, game_dir, lang_name=renpy_lang)
                    if strings_content:
                        strings_path = os.path.join(tl_dir, 'strings.rpy')
                        with open(strings_path, 'w', encoding='utf-8-sig', newline='\n') as f:
                            f.write(strings_content)
                        self.log_message.emit("info", self.config.get_log_text('strings_rpy_created', count=len(all_entries)))
                        return True
                except Exception as e:
                    self.log_message.emit("error", self.config.get_log_text('strings_rpy_error', error=str(e)))
                    return False
            
            return False
                
        except Exception as e:
            self.log_message.emit("error", self.config.get_log_text('translation_file_error', error=str(e)))
            return False
    
    def _generate_all_strings_file(self, entries: List[dict], game_dir: str, lang_name: str = None) -> str:
        """
        Tüm çevrilecek metinleri (diyalog + UI) tek bir strings.rpy dosyasında topla.
        
        Ren'Py String Translation formatı kullanılır:
        translate language strings:
            old "original text"
            new "translated text"
        
        Bu format ID gerektirmez ve her yerde çalışır.
        """
        formatter = RenPyOutputFormatter()
        skipped = 0
        lines = []
        lines.append("# Translation strings file")
        lines.append("# Auto-generated by RenLocalizer")
        lines.append("# Using Ren'Py String Translation format for maximum compatibility")
        lines.append("")
        
        target_lang = lang_name if lang_name else self.target_language
        lines.append(f"translate {target_lang} strings:")
        lines.append("")
        
        for entry in entries:
            text = entry.get('text', '')
            if formatter._should_skip_translation(text):
                skipped += 1
                continue
            file_path = entry.get('file_path', '')
            line_num = entry.get('line_number', 0)
            character = entry.get('character', '')
            text_type = entry.get('type', 'unknown')
            
            escaped_text = self._escape_rpy_string(text)
            rel_path = 'unknown'
            if file_path:
                try:
                    rel_path = os.path.relpath(file_path, game_dir)
                except ValueError:
                    # On Windows, relpath fails when drives differ (e.g., C: vs F:)
                    rel_path = os.path.abspath(file_path)
            
            # Kaynak bilgisi ve karakter adını yorum olarak ekle
            comment_parts = [f"{rel_path}:{line_num}"]
            if character:
                comment_parts.append(f"({character})")
            if text_type and text_type != 'dialogue':
                comment_parts.append(f"[{text_type}]")
            if entry.get('is_engine_common'):
                comment_parts.append('[engine_common]')
            
            lines.append(f"    # {' '.join(comment_parts)}")
            lines.append(f'    old "{escaped_text}"')
            lines.append(f'    new ""')
            lines.append("")
        
        if skipped:
            try:
                self.log_message.emit("debug", self.config.get_log_text('technical_entries_skipped', count=skipped))
            except Exception:
                pass

        return '\n'.join(lines)
    
    def _protect_glossary_terms(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Sözlük terimlerini placeholder ile korur ve karşılıklarını saklar."""
        if not self.config or not hasattr(self.config, 'glossary') or not self.config.glossary:
            return text, {}
            
        placeholders = {}
        counter = 0
        # En uzun terimler önce (çakışmayı önlemek için)
        sorted_terms = sorted(self.config.glossary.items(), key=lambda x: -len(x[0]))
        
        result = text
        for src, dst in sorted_terms:
            if not src or not dst: continue
            
            # Sadece tam kelime eşleşmesi (\b)
            pattern = re.compile(r'(?i)\b' + re.escape(src) + r'\b')
            
            def replace_func(match):
                nonlocal counter
                key = f"XRPYXGLO{counter}XRPYX"
                placeholders[key] = dst  # Hedef çeviriyi yer tutucu sözlüğüne koy!
                counter += 1
                return key
                
            result = pattern.sub(replace_func, result)
            
        return result, placeholders

    def _escape_rpy_string(self, text: str) -> str:
        """Ren'Py string formatı için escape et"""
        if not text:
            return text
        
        # Escape sequences
        text = text.replace('\\', '\\\\')
        text = text.replace('"', '\\"')
        text = text.replace('\n', '\\n')
        text = text.replace('\t', '\\t')
        
        return text
    
    def _translate_entries(self, entries: List[TranslationEntry]) -> Dict[str, str]:
        """Girişleri çevir (placeholder koruması zorunlu)."""
        from src.core.translator import protect_renpy_syntax, restore_renpy_syntax
        translations = {}
        formatter = RenPyOutputFormatter()

        # Teknik/yer tutucu metinleri çeviri kuyruğundan ayıkla
        filtered_entries: List[TranslationEntry] = []
        for entry in entries:
            if formatter._should_skip_translation(entry.original_text):
                continue
            filtered_entries.append(entry)

        skipped = len(entries) - len(filtered_entries)
        if skipped:
            self.log_message.emit("debug", self.config.get_log_text('placeholder_excluded', count=skipped))

        entries = filtered_entries
        total = len(entries)
        if total == 0:
            return translations

        # Batch çeviri için hazırla
        batch_size = self.config.translation_settings.max_batch_size

        # Ren'Py dil kodunu API dil koduna dönüştür
        api_target_lang = RENPY_TO_API_LANG.get(self.target_language, self.target_language)
        api_source_lang = RENPY_TO_API_LANG.get(self.source_language, self.source_language)

        self.log_message.emit("info", self.config.get_log_text('translation_lang_api', lang=self.target_language, api=api_target_lang))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Ensure translator is registered; fallback to Google/DeepL defaults
        if self.engine == TranslationEngine.GOOGLE and self.engine not in self.translation_manager.translators:
            gt = GoogleTranslator(config_manager=self.config, proxy_manager=getattr(self.translation_manager, "proxy_manager", None))
            self.translation_manager.add_translator(TranslationEngine.GOOGLE, gt)
        if self.engine == TranslationEngine.DEEPL and self.engine not in self.translation_manager.translators:
            deepl_key = getattr(getattr(self.config, "api_keys", None), "deepl_api_key", "") or ""
            dt = DeepLTranslator(api_key=deepl_key, proxy_manager=getattr(self.translation_manager, "proxy_manager", None))
            self.translation_manager.add_translator(TranslationEngine.DEEPL, dt)

        try:
            unchanged_count = 0
            failed_entries: List[str] = []
            sample_logs: List[str] = []
            for i in range(0, total, batch_size):
                if self.should_stop:
                    break

                batch = entries[i:i + batch_size]

                # Progress güncelle
                current = min(i + batch_size, total)
                if batch:
                    self.progress_updated.emit(current, total, batch[0].original_text[:50])

                # Çeviri istekleri oluştur (her zaman placeholder korumalı)
                requests = []
                batch_placeholders = []
                for entry in batch:
                    translation_id = getattr(entry, 'translation_id', '') or TLParser.make_translation_id(
                        entry.file_path,
                        entry.line_number,
                        entry.original_text,
                        getattr(entry, 'context_path', []),
                        getattr(entry, 'raw_text', None)
                    )
                    # Her metni çeviri öncesi koru (Ren'Py tagleri + Sözlük terimleri)
                    protected_text, placeholders = protect_renpy_syntax(entry.original_text)
                    
                    # Sözlük koruması uygula
                    protected_text, glossary_placeholders = self._protect_glossary_terms(protected_text)
                    placeholders.update(glossary_placeholders)
                    
                    batch_placeholders.append(placeholders)
                    req = TranslationRequest(
                        text=protected_text,  # KORUNMUŞ metin
                        source_lang=api_source_lang,
                        target_lang=api_target_lang,
                        engine=self.engine,
                        metadata={
                            'entry': entry,
                            'translation_id': translation_id,
                            'file_path': entry.file_path,
                            'line_number': entry.line_number,
                            'context_path': getattr(entry, 'context_path', []),
                            'placeholders': placeholders,
                        }
                    )
                    requests.append(req)

                # Batch çeviri
                self.translation_manager.set_proxy_enabled(self.use_proxy)
                results = loop.run_until_complete(
                    self.translation_manager.translate_batch(requests)
                )

                # Sonuçları kaydet (her zaman restore ile!)
                for idx, result in enumerate(results):
                    tid = result.metadata.get('translation_id') or result.original_text
                    placeholders = result.metadata.get('placeholders') or {}
                    
                    translated_raw = result.translated_text
                    if self.config and hasattr(self.config, 'glossary') and self.config.glossary:
                        translated_raw = formatter.apply_glossary(
                            text=translated_raw, 
                            glossary=self.config.glossary,
                            original_text=batch[idx].original_text
                        )

                    # Çeviri sonrası placeholder restore
                    restored = restore_renpy_syntax(translated_raw, placeholders) if translated_raw else ""
                    # Otomatik doğrulama: placeholder bozulduysa orijinali kullan
                    if not self.validate_placeholders(original=batch[idx].original_text, translated=restored):
                        self.log_message.emit("warning", self.config.get_log_text('placeholder_corrupted', original=batch[idx].original_text, translated=restored))
                        restored = batch[idx].original_text
                    
                    if result.success and restored:
                        translations[tid] = restored
                        translations.setdefault(batch[idx].original_text, restored)
                        
                        # Diagnostics: record translated and unchanged
                        try:
                            file_path = result.metadata.get('file_path') or batch[idx].file_path
                            if restored == batch[idx].original_text:
                                self.diagnostic_report.mark_unchanged(file_path, tid, original_text=batch[idx].original_text)
                            else:
                                self.diagnostic_report.mark_translated(file_path, tid, restored, original_text=batch[idx].original_text)
                        except Exception:
                            pass
                        
                        if restored == batch[idx].original_text:
                            unchanged_count += 1
                            if len(sample_logs) < 5:
                                sample_logs.append(f"UNCHANGED {result.metadata.get('file_path','')}:{result.metadata.get('line_number','')} -> {batch[idx].original_text[:80]}")
                    else:
                        err = result.error or "empty"
                        failed_entries.append(f"{result.metadata.get('file_path','')}:{result.metadata.get('line_number','')} ({err})")
                        # Diagnostics: mark skipped/failed
                        try:
                            file_path = result.metadata.get('file_path') or batch[idx].file_path
                            self.diagnostic_report.mark_skipped(file_path, f"translate_failed:{err}", {'text': batch[idx].original_text, 'line_number': batch[idx].line_number})
                        except Exception:
                            pass
                self.log_message.emit("info", f"Çevrildi: {current}/{total}")

            if unchanged_count:
                self.log_message.emit("warning", f"Aynı kalan çeviri sayısı: {unchanged_count} / {len(translations)}")
                for s in sample_logs:
                    self.log_message.emit("warning", s)
                self._log_error(f"UNCHANGED translations: {unchanged_count} / {len(translations)}\n" + "\n".join(sample_logs))
            if failed_entries:
                sample = "\n".join(failed_entries[:10])
                self.log_message.emit("warning", f"Çeviri başarısız sayısı: {len(failed_entries)}; ilk 10:\n{sample}")
                self._log_error(f"Translation failures ({len(failed_entries)}):\n{sample}")

        finally:
            loop.close()

        return translations

    def validate_placeholders(self, original, translated):
        """
        Çeviri sonrası değişkenlerin doğruluğunu kontrol eder.
        """
        # Orijinaldeki [köşeli parantez] bloklarını bul
        orig_vars = re.findall(r'\[[^\]]+\]', original)

        for var in orig_vars:
            if var not in translated:
                # HATA: Çeviri motoru değişkeni bozmuş!
                # Çeviriyi iptal et ve orijinal metni kullan veya değişkeni zorla ekle
                return False
        return True


class PipelineWorker(QThread):
    """Pipeline için QThread wrapper"""
    
    # Forward signals
    stage_changed = pyqtSignal(str, str)
    progress_updated = pyqtSignal(int, int, str)
    log_message = pyqtSignal(str, str)
    finished = pyqtSignal(object)
    show_warning = pyqtSignal(str, str)  # title, message - for popup warnings
    
    def __init__(self, pipeline: TranslationPipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        
        # Connect signals
        self.pipeline.stage_changed.connect(self.stage_changed)
        self.pipeline.progress_updated.connect(self.progress_updated)
        self.pipeline.log_message.connect(self.log_message)
        self.pipeline.finished.connect(self._on_finished)
        self.pipeline.show_warning.connect(self.show_warning)
    
    def _on_finished(self, result):
        self.finished.emit(result)
    
    def run(self):
        self.pipeline.run()
    
    def stop(self):
        self.pipeline.stop()
