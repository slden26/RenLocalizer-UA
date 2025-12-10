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

try:
    from PyQt6.QtCore import QObject, pyqtSignal, QThread
except ImportError:
    from PySide6.QtCore import QObject, Signal as pyqtSignal, QThread

from src.utils.config import ConfigManager
from src.utils.sdk_finder import find_renpy_sdks
from src.utils.unren_manager import UnRenManager
from src.core.tl_parser import TLParser, TranslationFile, TranslationEntry, get_translation_stats
from src.core.translator import TranslationManager, TranslationRequest, TranslationEngine


# Ren'Py dil kodları -> API dil kodları dönüşümü
# Arayüzde desteklenen 36+ dil için eksiksiz eşleşme
RENPY_TO_API_LANG = {
    # Temel diller
    "turkish": "tr",
    "english": "en",
    "german": "de",
    "french": "fr",
    "spanish": "es",
    "italian": "it",
    "portuguese": "pt",
    "russian": "ru",
    "polish": "pl",
    "dutch": "nl",
    # Asya dilleri
    "japanese": "ja",
    "korean": "ko",
    "chinese": "zh",
    "chinese_s": "zh-CN",  # Simplified Chinese
    "chinese_t": "zh-TW",  # Traditional Chinese
    "thai": "th",
    "vietnamese": "vi",
    "indonesian": "id",
    "malay": "ms",
    "hindi": "hi",
    # Avrupa dilleri
    "arabic": "ar",
    "czech": "cs",
    "danish": "da",
    "finnish": "fi",
    "greek": "el",
    "hebrew": "he",
    "hungarian": "hu",
    "norwegian": "no",
    "romanian": "ro",
    "swedish": "sv",
    "ukrainian": "uk",
    "bulgarian": "bg",
    "catalan": "ca",
    "croatian": "hr",
    "slovak": "sk",
    "slovenian": "sl",
    "serbian": "sr",
}


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
        
        # State
        self.current_stage = PipelineStage.IDLE
        self.should_stop = False
        self.is_running = False
        
        # Settings
        self.game_exe_path: Optional[str] = None
        self.project_path: Optional[str] = None
        self.target_language: str = "turkish"
        self.source_language: str = "en"
        self.engine: TranslationEngine = TranslationEngine.GOOGLE
        self.auto_unren: bool = True
        self.use_proxy: bool = False
    
    def configure(
        self,
        game_exe_path: str,
        target_language: str,
        source_language: str = "en",
        engine: TranslationEngine = TranslationEngine.GOOGLE,
        auto_unren: bool = True,
        use_proxy: bool = False
    ):
        """Pipeline ayarlarını yapılandır"""
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
        
        if self.should_stop:
            return self._stopped_result()
        
        # 2. UnRen (gerekirse)
        if not has_rpy and has_rpyc and self.auto_unren:
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
        
        tl_path = os.path.join(game_dir, 'tl')
        tl_files = self.tl_parser.parse_directory(tl_path, self.target_language)
        
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
        
        if not all_entries:
            stats = get_translation_stats(tl_files)
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
                original = entry.original_text
                if original in translations:
                    file_translations[original] = translations[original]
            
            if file_translations:
                success = self.tl_parser.save_translations(tl_file, file_translations)
                if success:
                    saved_count += 1
        
        # 7. Dil başlatma kodu oluştur (game/ klasörüne)
        self._create_language_init_file(game_dir)
        
        # Final istatistikler
        # Dosyaları yeniden parse et
        tl_files_updated = self.tl_parser.parse_directory(tl_path, self.target_language)
        stats = get_translation_stats(tl_files_updated)
        
        self._set_stage(PipelineStage.COMPLETED, self.config.get_ui_text("stage_completed"))
        
        return PipelineResult(
            success=True,
            message=self.config.get_ui_text("pipeline_completed_summary").replace("{translated}", str(len(translations))).replace("{saved}", str(saved_count)),
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
    
    def _create_language_init_file(self, game_dir: str):
        """
        Dil başlatma dosyası oluşturur.
        game/ klasörüne yazılır, böylece oyun başlarken varsayılan dil ayarlanır.
        """
        try:
            # game/ klasörüne yaz - dosya adı: zzz_language_init.rpy
            # zzz prefix'i dosyanın en son yüklenmesini sağlar (diğer init'lerden sonra)
            init_file = os.path.join(game_dir, f'zzz_{self.target_language}_language.rpy')
            
            self.log_message.emit("info", self.config.get_ui_text("pipeline_lang_init_check").replace("{path}", init_file))
            
            # Zaten varsa sil ve yeniden oluştur (güncellemek için)
            if os.path.exists(init_file):
                os.remove(init_file)
                self.log_message.emit("info", self.config.get_ui_text("pipeline_lang_init_update"))
            
            # Ren'Py için kapsamlı dil ayarı
            content = f'''# RenLocalizer tarafından oluşturuldu
# Bu dosya oyunun {self.target_language} dilinde başlamasını sağlar

init python:
    # Eğer kullanıcı daha önce bir dil seçmediyse Türkçe yap
    if not persistent._language:
        config.language = "turkish"
    config.language = "{self.target_language}"
    config.default_language = "{self.target_language}"
'''
            
            with open(init_file, 'w', encoding='utf-8-sig', newline='\n') as f:
                f.write(content)
            
            self.log_message.emit("info", self.config.get_ui_text("pipeline_lang_init_created").replace("{path}", init_file))
            
        except Exception as e:
            self.log_message.emit("warning", self.config.get_ui_text("pipeline_lang_init_failed").format(error=e))
    
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
                        self.log_message.emit("debug", f"Motor dosyası atlanıyor (Write Protection): {filename}")
                        continue
                    
                    try:
                        # Her dosya için yedek oluştur
                        # GÜVENLİK YAMASI: Yedekleme
                        backup_path = filepath + ".bak"
                        if not os.path.exists(backup_path):
                            try:
                                shutil.copy2(filepath, backup_path)
                            except Exception as e:
                                self.log_message.emit("warning", f"Yedek alınamadı, işlem atlanıyor: {filename}")
                                continue  # Dosya işlenmeden atlanıyor
                        
                        with open(filepath, 'r', encoding='utf-8-sig') as f:
                            content = f.read()
                        
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
                            self.log_message.emit("debug", f"Çevrilebilir yapıldı: {filename}")
                    
                    except Exception as e:
                        self.log_message.emit("warning", f"Dosya işlenemedi {filename}: {e}")
                        continue
            
            if modified_count > 0:
                self.log_message.emit("info", f"{modified_count} kaynak dosya çevrilebilir hale getirildi")
            
        except Exception as e:
            self.log_message.emit("warning", f"Kaynak dosyalar işlenirken hata: {e}")
        
        return modified_count
    
    def _run_unren(self, project_path: str) -> bool:
        """UnRen çalıştır"""
        try:
            self.log_message.emit("info", "UnRen başlatılıyor...")
            
            # UnRen'i indir (gerekirse)
            if not self.unren_manager.is_available():
                self.log_message.emit("info", "UnRen indiriliyor...")
                try:
                    self.unren_manager.ensure_available()
                except Exception as e:
                    self.log_message.emit("error", f"UnRen indirilemedi: {e}")
                    return False
            
            # UnRen çalıştır
            from pathlib import Path
            project_path_obj = Path(project_path)
            
            # Sanity check - ensure script exists and warn if not
            root = self.unren_manager.get_unren_root()
            if root:
                script_candidates = list(root.glob('*.bat')) + list(root.glob('**/*.bat'))
                if not script_candidates:
                    self.log_message.emit("error", f"UnRen scriptleri bulunamadı: {root}")
                    return False
            
            # Ren'Py versiyonuna göre otomatik seçim scripti oluştur
            # 2 = UnRen-current (Ren'Py 8+)
            # 1 = UnRen-legacy (Ren'Py 7 ve altı)
            # x = çıkış
            # Önce decompile seçimi, sonra çıkış
            automation_script = "2\nx\n"  # Current seçip çık
            
            try:
                self.log_message.emit("info", "UnRen otomatik mod ile çalıştırılıyor...")
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
                    self.log_message.emit("warning", "UnRen çalıştırıldı ama oyun dizini bulunamadı (UnRen). Canceling translation.")
                    warning_title = self.config.get_ui_text('unren_log_cannot_locate_game_title') if self.config else 'UnRen hata'
                    warning_message = self.config.get_ui_text('unren_log_cannot_locate_game') if self.config else 'UnRen could not locate game, lib or renpy folders.'
                    self.show_warning.emit(warning_title, warning_message)
                    return False

                if process.returncode == 0:
                    self.log_message.emit("info", "UnRen tamamlandı")
                    return True
                else:
                    self.log_message.emit("warning", f"UnRen tamamlandı (kod: {process.returncode})")
                    # Bazı durumlarda non-zero dönse bile başarılı olabilir
                    # .rpy dosyaları oluşturulduysa başarılı say
                    game_dir = os.path.join(project_path, 'game')
                    if self._has_rpy_files(game_dir):
                        self.log_message.emit("info", ".rpy dosyaları oluşturuldu, devam ediliyor")
                        return True
                    return False
                    
            except Exception as e:
                self.log_message.emit("error", f"UnRen çalıştırma hatası: {e}")
                return False
            
        except Exception as e:
            self.log_message.emit("error", f"UnRen hatası: {e}")
            return False
    
    def _run_translate_command(self, project_path: str) -> bool:
        """Kaynak dosyaları parse edip tl/ klasörüne çeviri şablonları oluştur
        
        ÖNEMLİ: Ren'Py String Translation sistemi kullanılıyor.
        Bu sistemde aynı string sadece BİR KERE tanımlanabilir (global tekil).
        Bu nedenle tüm stringler (diyalog + UI) tek bir dosyada toplanıyor.
        """
        try:
            self.log_message.emit("info", f"Çeviri dosyaları oluşturuluyor: {self.target_language}")
            
            game_dir = os.path.join(project_path, 'game')
            tl_dir = os.path.join(game_dir, 'tl', self.target_language)
            
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
            use_deep = True
            use_rpyc = False
            if self.config and hasattr(self.config, 'translation_settings'):
                settings = self.config.translation_settings
                use_deep = getattr(settings, 'enable_deep_scan', getattr(settings, 'use_deep_scan', True))
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
                self.log_message.emit("info", "Deep Scan çalıştırılıyor...")
                deep_results = parser.extract_from_directory_with_deep_scan(game_dir)

            # 4. RPYC Execution
            if use_rpyc:
                self.log_message.emit("info", "RPYC taraması yapılıyor...")
                # Import here to avoid circular imports if any
                try:
                    from src.core.rpyc_reader import extract_texts_from_rpyc_directory
                    rpyc_results = extract_texts_from_rpyc_directory(game_dir)
                except ImportError:
                    self.log_message.emit("warning", "RPYC modülü bulunamadı, atlanıyor.")
            # --- FIX END ---
            
            # --- EKSİK OLAN BİRLEŞTİRME KODU BAŞLANGICI ---

            # Deep Scan Sonuçlarını Birleştir
            if deep_results:
                self.log_message.emit("info", f"Deep Scan verileri birleştiriliyor...")
                for file_path, entries in deep_results.items():
                    for entry in entries:
                        if entry.get('is_deep_scan'):
                            entry['file_path'] = str(file_path)
                            source_texts.append(entry)

            # RPYC Sonuçlarını Birleştir
            if rpyc_results:
                self.log_message.emit("info", f"RPYC verileri birleştiriliyor...")
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
                self.log_message.emit("warning", "Kaynak dosyalarda çevrilecek metin bulunamadı")
                return False
            
            self.log_message.emit("info", f"{len(source_texts)} metin bulundu, çeviri dosyaları oluşturuluyor...")
            
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
            
            self.log_message.emit("info", f"{len(all_entries)} benzersiz metin bulundu")
            
            # Tüm stringleri tek strings.rpy dosyasına yaz
            if all_entries:
                try:
                    strings_content = self._generate_all_strings_file(all_entries, game_dir)
                    if strings_content:
                        strings_path = os.path.join(tl_dir, 'strings.rpy')
                        with open(strings_path, 'w', encoding='utf-8-sig', newline='\n') as f:
                            f.write(strings_content)
                        self.log_message.emit("info", f"strings.rpy oluşturuldu: {len(all_entries)} string")
                        return True
                except Exception as e:
                    self.log_message.emit("error", f"strings.rpy oluşturulamadı: {e}")
                    return False
            
            return False
                
        except Exception as e:
            self.log_message.emit("error", f"Çeviri dosyası oluşturma hatası: {e}")
            return False
    
    def _generate_all_strings_file(self, entries: List[dict], game_dir: str) -> str:
        """
        Tüm çevrilecek metinleri (diyalog + UI) tek bir strings.rpy dosyasında topla.
        
        Ren'Py String Translation formatı kullanılır:
        translate language strings:
            old "original text"
            new "translated text"
        
        Bu format ID gerektirmez ve her yerde çalışır.
        """
        lines = []
        lines.append("# Translation strings file")
        lines.append("# Auto-generated by RenLocalizer")
        lines.append("# Using Ren'Py String Translation format for maximum compatibility")
        lines.append("")
        lines.append(f"translate {self.target_language} strings:")
        lines.append("")
        
        for entry in entries:
            text = entry.get('text', '')
            file_path = entry.get('file_path', '')
            line_num = entry.get('line_number', 0)
            character = entry.get('character', '')
            text_type = entry.get('type', 'unknown')
            
            escaped_text = self._escape_rpy_string(text)
            rel_path = os.path.relpath(file_path, game_dir) if file_path else 'unknown'
            
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
        
        return '\n'.join(lines)
    
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
        """Girişleri çevir"""
        translations = {}
        total = len(entries)
        
        # Batch çeviri için hazırla
        batch_size = self.config.translation_settings.max_batch_size
        
        # Ren'Py dil kodunu API dil koduna dönüştür
        api_target_lang = RENPY_TO_API_LANG.get(self.target_language, self.target_language)
        api_source_lang = RENPY_TO_API_LANG.get(self.source_language, self.source_language)
        
        self.log_message.emit("info", f"Dil: {self.target_language} -> API: {api_target_lang}")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            for i in range(0, total, batch_size):
                if self.should_stop:
                    break
                
                batch = entries[i:i + batch_size]
                
                # Progress güncelle
                current = min(i + batch_size, total)
                if batch:
                    self.progress_updated.emit(current, total, batch[0].original_text[:50])
                
                # Çeviri istekleri oluştur
                requests = []
                for entry in batch:
                    req = TranslationRequest(
                        text=entry.original_text,  # original_text kullan
                        source_lang=api_source_lang,
                        target_lang=api_target_lang,  # API dil kodu kullan
                        engine=self.engine,
                        metadata={'entry': entry}
                    )
                    requests.append(req)
                
                # Batch çeviri
                self.translation_manager.set_proxy_enabled(self.use_proxy)
                results = loop.run_until_complete(
                    self.translation_manager.translate_batch(requests)
                )
                
                # Sonuçları kaydet
                for result in results:
                    if result.success and result.translated_text:
                        translations[result.original_text] = result.translated_text
                
                self.log_message.emit("info", f"Çevrildi: {current}/{total}")
        
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
