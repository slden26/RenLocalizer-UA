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

try:
    from PyQt6.QtCore import QObject, pyqtSignal, QThread
except ImportError:
    from PySide6.QtCore import QObject, Signal as pyqtSignal, QThread

from src.utils.config import ConfigManager
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
        self.project_path = os.path.dirname(game_exe_path)
        self.target_language = target_language
        self.source_language = source_language
        self.engine = engine
        self.auto_unren = auto_unren
        self.use_proxy = use_proxy
    
    def stop(self):
        """Pipeline'ı durdur"""
        self.should_stop = True
        self.log_message.emit("warning", "Durdurma isteği alındı...")
    
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
                message="Geçersiz oyun EXE yolu",
                stage=PipelineStage.ERROR
            )
        
        project_path = self.project_path
        game_dir = os.path.join(project_path, 'game')
        
        if not os.path.isdir(game_dir):
            return PipelineResult(
                success=False,
                message="'game' klasörü bulunamadı",
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
                    message="UnRen başarısız oldu",
                    stage=PipelineStage.ERROR
                )
            
            # Tekrar kontrol
            has_rpy = self._has_rpy_files(game_dir)
        
        if not has_rpy:
            return PipelineResult(
                success=False,
                message=".rpy dosyası bulunamadı. Decompile gerekli.",
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
                    message="Translate komutu başarısız",
                    stage=PipelineStage.ERROR
                )
        else:
            self.log_message.emit("info", f"tl/{self.target_language} zaten mevcut, oluşturma atlanıyor")
        
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
                message="Tüm metinler zaten çevrilmiş!",
                stage=PipelineStage.COMPLETED,
                stats=stats,
                output_path=tl_dir
            )
        
        self.log_message.emit("info", f"{len(all_entries)} metin çevrilecek")
        
        if self.should_stop:
            return self._stopped_result()
        
        # 5. Çeviri
        self._set_stage(PipelineStage.TRANSLATING, "Metinler çevriliyor...")
        
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
            
            self.log_message.emit("info", f"Dil başlatma dosyası kontrol ediliyor: {init_file}")
            
            # Zaten varsa sil ve yeniden oluştur (güncellemek için)
            if os.path.exists(init_file):
                os.remove(init_file)
                self.log_message.emit("info", "Mevcut dil dosyası güncelleniyor...")
            
            # Ren'Py için kapsamlı dil ayarı
            content = f'''# RenLocalizer tarafından oluşturuldu
# Bu dosya oyunun {self.target_language} dilinde başlamasını sağlar

init python:
    config.language = "{self.target_language}"
    config.default_language = "{self.target_language}"
'''
            
            with open(init_file, 'w', encoding='utf-8-sig', newline='\n') as f:
                f.write(content)
            
            self.log_message.emit("info", f"Dil başlatma dosyası oluşturuldu: {init_file}")
            
        except Exception as e:
            self.log_message.emit("warning", f"Dil başlatma dosyası oluşturulamadı: {e}")
    
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
        # NOT: Her pattern hem tek tırnak (') hem çift tırnak (") destekler
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
                    
                    try:
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
            
            # Ren'Py versiyonuna göre otomatik seçim scripti oluştur
            # 2 = UnRen-current (Ren'Py 8+)
            # 1 = UnRen-legacy (Ren'Py 7 ve altı)
            # x = çıkış
            # Önce decompile seçimi, sonra çıkış
            automation_script = "2\nx\n"  # Current seçip çık
            
            try:
                self.log_message.emit("info", "UnRen otomatik mod ile çalıştırılıyor...")
                
                process = self.unren_manager.run_unren(
                    project_path_obj,
                    variant='auto',
                    wait=True,
                    log_callback=lambda msg: self.log_message.emit("info", msg),
                    automation_script=automation_script,
                    timeout=600  # 10 dakika timeout
                )
                
                # Process tamamlandıysa başarılı
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
            
            source_texts = parser.parse_directory(game_dir)
            
            if not source_texts:
                self.log_message.emit("warning", "Kaynak dosyalarda çevrilecek metin bulunamadı")
                return False
            
            self.log_message.emit("info", f"{len(source_texts)} metin bulundu, çeviri dosyaları oluşturuluyor...")
            
            # TÜM metinleri GLOBAL olarak tekil tut
            # Ren'Py String Translation'da aynı string sadece 1 kere tanımlanabilir
            all_entries = []
            seen_texts = set()
            
            for entry in source_texts:
                text = entry.get('text', '')
                if not text or text in seen_texts:
                    continue
                seen_texts.add(text)
                all_entries.append(entry)
            
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


class PipelineWorker(QThread):
    """Pipeline için QThread wrapper"""
    
    # Forward signals
    stage_changed = pyqtSignal(str, str)
    progress_updated = pyqtSignal(int, int, str)
    log_message = pyqtSignal(str, str)
    finished = pyqtSignal(object)
    
    def __init__(self, pipeline: TranslationPipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        
        # Connect signals
        self.pipeline.stage_changed.connect(self.stage_changed)
        self.pipeline.progress_updated.connect(self.progress_updated)
        self.pipeline.log_message.connect(self.log_message)
        self.pipeline.finished.connect(self._on_finished)
    
    def _on_finished(self, result):
        self.finished.emit(result)
    
    def run(self):
        self.pipeline.run()
    
    def stop(self):
        self.pipeline.stop()
