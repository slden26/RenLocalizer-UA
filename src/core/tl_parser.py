# -*- coding: utf-8 -*-
"""
Translation File Parser
=======================

Ren'Py translate dosyalarını (tl/<dil>/*.rpy) parse eder ve çevirir.

İki format desteklenir:
1. Strings format: old "..." / new "..."
2. Dialogue format: # character "orijinal" ve character "" satırları
"""

import os
import re
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TranslationEntry:
    """Tek bir çeviri girişi"""
    original_text: str      # Orijinal metin
    translated_text: str    # Çevrilmiş metin (boş olabilir)
    file_path: str
    line_number: int
    entry_type: str         # 'string' veya 'dialogue'
    character: Optional[str] = None  # Karakter adı (dialogue için)
    source_comment: Optional[str] = None  # # game/dosya.rpy:123 gibi
    block_id: Optional[str] = None  # translate block id
    
    def needs_translation(self) -> bool:
        """Çeviri gerekiyor mu?"""
        return not self.translated_text or self.translated_text.strip() == ""
    
    # Geriye uyumluluk için
    @property
    def old_text(self) -> str:
        return self.original_text
    
    @property
    def new_text(self) -> str:
        return self.translated_text


@dataclass  
class TranslationFile:
    """Bir çeviri dosyasının içeriği"""
    file_path: str
    language: str
    entries: List[TranslationEntry] = field(default_factory=list)
    file_type: str = "mixed"  # 'strings', 'dialogue', 'mixed'
    
    def get_untranslated(self) -> List[TranslationEntry]:
        """Çevrilmemiş girişleri döndürür"""
        return [e for e in self.entries if e.needs_translation()]
    
    def get_translated_count(self) -> int:
        """Çevrilmiş giriş sayısı"""
        return len([e for e in self.entries if not e.needs_translation()])


class TLParser:
    """
    Ren'Py translate dosyalarını parse eder.
    
    İki format desteklenir:
    
    1. Strings format (common.rpy):
        translate turkish strings:
            old "Start"
            new ""
    
    2. Dialogue format (script dosyaları):
        translate turkish label_id:
            # gg "Hello world"
            gg ""
    
    3. Narrator format (karaktersiz):
        translate turkish label_id:
            # "Narrator text here"
            ""
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Regex patterns
        # translate turkish strings: VEYA translate turkish some_label_12ab34cd:
        self._translate_block_re = re.compile(
            r'^translate\s+(\w+)\s+(\w+)\s*:\s*$',
            re.IGNORECASE
        )
        
        # old "..." / new "..." for strings format
        self._old_re = re.compile(r'^\s*old\s+"(.*)"\s*$')
        self._new_re = re.compile(r'^\s*new\s+"(.*)"\s*$')
        
        # # character "text" - dialogue orijinal yorum satırı (karakterli)
        self._dialogue_comment_re = re.compile(r'^\s*#\s*(\w+)\s+"(.*)"\s*$')
        
        # # "text" - narrator orijinal yorum satırı (karaktersiz)
        self._narrator_comment_re = re.compile(r'^\s*#\s*"(.*)"\s*$')
        
        # character "" veya character "text" - dialogue çeviri satırı
        self._dialogue_line_re = re.compile(r'^\s*(\w+)\s+"(.*)"\s*$')
        
        # "" veya "text" - narrator çeviri satırı (karaktersiz)
        self._narrator_line_re = re.compile(r'^\s*"(.*)"\s*$')
        
        # Sadece # path.rpy:123 veya # game/path.rpy:123 formatı - kaynak yorum
        self._source_comment_re = re.compile(r'^\s*#\s*([^:]+:\d+)\s*$')
    
    def should_skip_text(self, text: str) -> bool:
        """Boş veya anlamsız metin mi kontrol et"""
        if not text or not text.strip():
            return True
        
        text = text.strip()
        
        # Çok kısa metinleri atla (tek karakter)
        if len(text) <= 1:
            return True
        
        # Sadece sayı olanları atla
        if text.replace('.', '').replace(',', '').isdigit():
            return True
        
        return False
    
    def parse_file(self, file_path: str) -> Optional[TranslationFile]:
        """
        Tek bir çeviri dosyasını parse eder.
        """
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                self.logger.error(f"Dosya okunamadı: {file_path}: {e}")
                return None
        except Exception as e:
            self.logger.error(f"Dosya okunamadı: {file_path}: {e}")
            return None
        
        lines = content.split('\n')
        
        # Dil kodunu bul
        language = None
        for line in lines:
            match = self._translate_block_re.match(line.strip())
            if match:
                language = match.group(1)
                break
        
        if not language:
            # translate bloğu olmayan dosyaları atla
            return None
        
        tl_file = TranslationFile(
            file_path=file_path,
            language=language
        )
        
        # Parse entries
        entries = self._parse_all_entries(lines, file_path)
        tl_file.entries = entries
        
        # Dosya tipini belirle
        string_count = sum(1 for e in entries if e.entry_type == 'string')
        dialogue_count = sum(1 for e in entries if e.entry_type == 'dialogue')
        
        if string_count > 0 and dialogue_count == 0:
            tl_file.file_type = 'strings'
        elif dialogue_count > 0 and string_count == 0:
            tl_file.file_type = 'dialogue'
        else:
            tl_file.file_type = 'mixed'
        
        self.logger.info(f"Parse edildi: {file_path} - {len(entries)} giriş ({tl_file.file_type})")
        
        return tl_file
    
    def _parse_all_entries(self, lines: List[str], file_path: str) -> List[TranslationEntry]:
        """Tüm çeviri girişlerini parse et - her iki formatı da destekler"""
        entries = []
        
        i = 0
        current_block_id = None
        current_source_comment = None
        in_translate_block = False
        block_type = None  # 'strings' veya 'dialogue'
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Boş satırları atla
            if not stripped:
                i += 1
                continue
            
            # translate block başlangıcı
            block_match = self._translate_block_re.match(stripped)
            if block_match:
                current_block_id = block_match.group(2)
                in_translate_block = True
                
                if current_block_id == 'strings':
                    block_type = 'strings'
                else:
                    block_type = 'dialogue'
                
                i += 1
                continue
            
            # Source comment (# game/path.rpy:123)
            source_match = self._source_comment_re.match(stripped)
            if source_match:
                current_source_comment = source_match.group(1)
                i += 1
                continue
            
            # STRINGS FORMAT: old "..." / new "..."
            old_match = self._old_re.match(stripped)
            if old_match:
                old_text = self._unescape_string(old_match.group(1))
                new_text = ""
                
                # Sonraki satır new "..." olmalı
                if i + 1 < len(lines):
                    next_stripped = lines[i + 1].strip()
                    new_match = self._new_re.match(next_stripped)
                    if new_match:
                        new_text = self._unescape_string(new_match.group(1))
                        i += 1
                
                if not self.should_skip_text(old_text):
                    entry = TranslationEntry(
                        original_text=old_text,
                        translated_text=new_text,
                        file_path=file_path,
                        line_number=i + 1,
                        entry_type='string',
                        source_comment=current_source_comment,
                        block_id=current_block_id
                    )
                    entries.append(entry)
                
                current_source_comment = None
                i += 1
                continue
            
            # DIALOGUE FORMAT: # character "text" yorumu ve karakter "" satırı
            if in_translate_block and block_type == 'dialogue':
                # Önce karakterli diyalog kontrol et (# gg "Hello")
                comment_match = self._dialogue_comment_re.match(stripped)
                if comment_match:
                    character = comment_match.group(1)
                    original_text = self._unescape_string(comment_match.group(2))
                    
                    # Sonraki satırda karakter "" olmalı
                    if i + 1 < len(lines):
                        next_stripped = lines[i + 1].strip()
                        dialogue_match = self._dialogue_line_re.match(next_stripped)
                        
                        if dialogue_match:
                            char_name = dialogue_match.group(1)
                            translated_text = self._unescape_string(dialogue_match.group(2))
                            
                            if not self.should_skip_text(original_text):
                                entry = TranslationEntry(
                                    original_text=original_text,
                                    translated_text=translated_text,
                                    file_path=file_path,
                                    line_number=i + 2,  # dialogue satırının numarası
                                    entry_type='dialogue',
                                    character=char_name,
                                    source_comment=current_source_comment,
                                    block_id=current_block_id
                                )
                                entries.append(entry)
                            
                            i += 2
                            current_source_comment = None
                            continue
                
                # Narrator formatı kontrol et (# "Hello" - karaktersiz)
                narrator_match = self._narrator_comment_re.match(stripped)
                if narrator_match:
                    original_text = self._unescape_string(narrator_match.group(1))
                    
                    # Sonraki satırda "" olmalı
                    if i + 1 < len(lines):
                        next_stripped = lines[i + 1].strip()
                        narrator_line_match = self._narrator_line_re.match(next_stripped)
                        
                        if narrator_line_match:
                            translated_text = self._unescape_string(narrator_line_match.group(1))
                            
                            if not self.should_skip_text(original_text):
                                entry = TranslationEntry(
                                    original_text=original_text,
                                    translated_text=translated_text,
                                    file_path=file_path,
                                    line_number=i + 2,
                                    entry_type='narrator',
                                    character=None,
                                    source_comment=current_source_comment,
                                    block_id=current_block_id
                                )
                                entries.append(entry)
                            
                            i += 2
                            current_source_comment = None
                            continue
                
                i += 1
                continue
            
            # Block dışına çıkış kontrolü (indent azalması)
            if in_translate_block and stripped and not stripped.startswith('#'):
                if not line.startswith('    ') and not line.startswith('\t'):
                    if not self._translate_block_re.match(stripped):
                        in_translate_block = False
                        block_type = None
                        current_block_id = None
            
            i += 1
        
        return entries
    
    def _unescape_string(self, text: str) -> str:
        """Ren'Py string escape'lerini geri çevir"""
        if not text:
            return text
        
        # Escape sequences
        text = text.replace('\\n', '\n')
        text = text.replace('\\t', '\t')
        text = text.replace('\\"', '"')
        text = text.replace('\\\\', '\\')
        
        return text
    
    def _escape_string(self, text: str) -> str:
        """Ren'Py için string escape et"""
        if not text:
            return text
        
        # Sıralama önemli - önce backslash
        text = text.replace('\\', '\\\\')
        text = text.replace('"', '\\"')
        text = text.replace('\n', '\\n')
        text = text.replace('\t', '\\t')
        
        return text
    
    def parse_directory(self, tl_dir: str, language: str) -> List[TranslationFile]:
        """
        tl/<dil>/ klasöründeki tüm .rpy dosyalarını parse eder.
        
        Args:
            tl_dir: tl klasörü yolu (game/tl)
            language: Dil kodu (turkish, spanish, vs.)
            
        Returns:
            TranslationFile listesi
        """
        lang_dir = os.path.join(tl_dir, language)
        
        if not os.path.isdir(lang_dir):
            self.logger.warning(f"Dil klasörü bulunamadı: {lang_dir}")
            return []
        
        files = []
        
        for root, dirs, filenames in os.walk(lang_dir):
            for filename in filenames:
                if filename.endswith('.rpy'):
                    file_path = os.path.join(root, filename)
                    tl_file = self.parse_file(file_path)
                    if tl_file:
                        files.append(tl_file)
        
        self.logger.info(f"Toplam {len(files)} dosya parse edildi: {lang_dir}")
        
        return files
    
    def update_translations(
        self,
        tl_file: TranslationFile,
        translations: Dict[str, str]
    ) -> str:
        """
        Çevirileri dosya içeriğine uygular ve yeni içeriği döndürür.
        Her iki formatı da destekler: strings (old/new) ve dialogue (# comment / character "")
        """
        try:
            with open(tl_file.file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
        except Exception:
            with open(tl_file.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        
        lines = content.split('\n')
        new_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # STRINGS FORMAT: old "..." / new "..."
            old_match = self._old_re.match(stripped)
            if old_match:
                old_text = self._unescape_string(old_match.group(1))
                new_lines.append(line)  # old satırını ekle
                
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_stripped = next_line.strip()
                    new_match = self._new_re.match(next_stripped)
                    
                    if new_match:
                        if old_text in translations:
                            translated = translations[old_text]
                            escaped = self._escape_string(translated)
                            indent = len(next_line) - len(next_line.lstrip())
                            new_lines.append(' ' * indent + f'new "{escaped}"')
                        else:
                            new_lines.append(next_line)
                        
                        i += 2
                        continue
                
                i += 1
                continue
            
            # DIALOGUE FORMAT: # character "text" ve karakter ""
            comment_match = self._dialogue_comment_re.match(stripped)
            if comment_match:
                original_text = self._unescape_string(comment_match.group(2))
                new_lines.append(line)  # yorum satırını ekle
                
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_stripped = next_line.strip()
                    dialogue_match = self._dialogue_line_re.match(next_stripped)
                    
                    if dialogue_match:
                        char_name = dialogue_match.group(1)
                        
                        if original_text in translations:
                            translated = translations[original_text]
                            escaped = self._escape_string(translated)
                            indent = len(next_line) - len(next_line.lstrip())
                            new_lines.append(' ' * indent + f'{char_name} "{escaped}"')
                        else:
                            new_lines.append(next_line)
                        
                        i += 2
                        continue
                
                i += 1
                continue
            
            # NARRATOR FORMAT: # "text" ve ""
            narrator_match = self._narrator_comment_re.match(stripped)
            if narrator_match:
                original_text = self._unescape_string(narrator_match.group(1))
                new_lines.append(line)  # yorum satırını ekle
                
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_stripped = next_line.strip()
                    narrator_line_match = self._narrator_line_re.match(next_stripped)
                    
                    if narrator_line_match:
                        if original_text in translations:
                            translated = translations[original_text]
                            escaped = self._escape_string(translated)
                            indent = len(next_line) - len(next_line.lstrip())
                            new_lines.append(' ' * indent + f'"{escaped}"')
                        else:
                            new_lines.append(next_line)
                        
                        i += 2
                        continue
                
                i += 1
                continue
            
            new_lines.append(line)
            i += 1
        
        return '\n'.join(new_lines)
    
    def save_translations(
        self,
        tl_file: TranslationFile,
        translations: Dict[str, str],
        output_path: Optional[str] = None
    ) -> bool:
        """
        Çevirileri dosyaya kaydeder.
        """
        try:
            updated_content = self.update_translations(tl_file, translations)
            
            save_path = output_path or tl_file.file_path
            
            with open(save_path, 'w', encoding='utf-8-sig', newline='\n') as f:
                f.write(updated_content)
            
            self.logger.info(f"Kaydedildi: {save_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Kaydetme hatası: {e}")
            return False


def get_translation_stats(tl_files: List[TranslationFile]) -> Dict:
    """Çeviri istatistikleri"""
    total_entries = 0
    translated_entries = 0
    untranslated_entries = 0
    
    for tl_file in tl_files:
        for entry in tl_file.entries:
            total_entries += 1
            if entry.needs_translation():
                untranslated_entries += 1
            else:
                translated_entries += 1
    
    return {
        'total': total_entries,
        'translated': translated_entries,
        'untranslated': untranslated_entries,
        'progress': (translated_entries / total_entries * 100) if total_entries > 0 else 0
    }
