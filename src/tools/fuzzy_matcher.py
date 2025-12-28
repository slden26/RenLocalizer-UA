# -*- coding: utf-8 -*-
"""
RenLocalizer Fuzzy Matching Module
==================================

Smart Update feature that recovers translations when source text changes slightly.
Uses fuzzy string matching to find similar strings and suggest reusing old translations.

This helps when:
1. Source script has minor edits (typo fixes, rewording)
2. Translation IDs shift due to context changes
3. New versions of a game release with small changes
"""

import logging
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path


@dataclass
class FuzzyMatch:
    """Represents a fuzzy match between old and new strings."""
    new_id: str
    new_original: str
    old_id: str
    old_original: str
    old_translation: str
    similarity: float  # 0.0 to 1.0
    
    @property
    def similarity_percent(self) -> int:
        return int(self.similarity * 100)
    
    def is_confident(self, threshold: float = 0.9) -> bool:
        """Check if match is confident enough to auto-apply."""
        return self.similarity >= threshold
    
    def __str__(self) -> str:
        return (
            f"Match ({self.similarity_percent}%): "
            f"\"{self.new_original[:40]}...\" ← \"{self.old_translation[:40]}...\""
        )


@dataclass
class FuzzyMatchReport:
    """Report of fuzzy matching results."""
    matches: List[FuzzyMatch] = field(default_factory=list)
    unmatched_new: List[Tuple[str, str]] = field(default_factory=list)  # (id, text)
    unmatched_old: List[Tuple[str, str, str]] = field(default_factory=list)  # (id, orig, trans)
    
    @property
    def auto_apply_count(self) -> int:
        """Number of matches confident enough to auto-apply."""
        return sum(1 for m in self.matches if m.is_confident())
    
    @property
    def review_count(self) -> int:
        """Number of matches that need human review."""
        return sum(1 for m in self.matches if not m.is_confident())
    
    def get_suggestions(self, auto_threshold: float = 0.9) -> Dict[str, str]:
        """
        Get translation suggestions as a dict.
        
        Returns:
            Dict mapping new_original -> suggested_translation
        """
        return {
            m.new_original: m.old_translation
            for m in self.matches
            if m.similarity >= auto_threshold
        }
    
    def summary(self) -> str:
        return (
            f"Fuzzy Match Results:\n"
            f"  Auto-apply (≥90%): {self.auto_apply_count}\n"
            f"  Needs review (<90%): {self.review_count}\n"
            f"  Unmatched new strings: {len(self.unmatched_new)}\n"
            f"  Orphaned old translations: {len(self.unmatched_old)}"
        )


class FuzzyMatcher:
    """
    Fuzzy string matcher for recovering translations.
    
    Uses SequenceMatcher (similar to diff algorithm) to find similar strings
    and map old translations to new source strings.
    """
    
    def __init__(
        self,
        auto_threshold: float = 0.90,
        min_threshold: float = 0.70,
        ignore_case: bool = False,
        ignore_whitespace: bool = True
    ):
        """
        Initialize fuzzy matcher.
        
        Args:
            auto_threshold: Similarity >= this is auto-applied
            min_threshold: Similarity below this is ignored
            ignore_case: Case-insensitive matching
            ignore_whitespace: Normalize whitespace before matching
        """
        self.auto_threshold = auto_threshold
        self.min_threshold = min_threshold
        self.ignore_case = ignore_case
        self.ignore_whitespace = ignore_whitespace
        self.logger = logging.getLogger(__name__)
    
    def _normalize(self, text: str) -> str:
        """Normalize text for comparison."""
        result = text
        if self.ignore_case:
            result = result.lower()
        if self.ignore_whitespace:
            result = ' '.join(result.split())
        return result
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity ratio between two strings.
        
        Returns:
            Float between 0.0 (completely different) and 1.0 (identical)
        """
        norm1 = self._normalize(text1)
        norm2 = self._normalize(text2)
        
        if norm1 == norm2:
            return 1.0
        
        # Use SequenceMatcher for efficient similarity calculation
        matcher = SequenceMatcher(None, norm1, norm2)
        return matcher.ratio()
    
    def find_best_match(
        self,
        target: str,
        candidates: Dict[str, Tuple[str, str]]  # id -> (original, translation)
    ) -> Optional[FuzzyMatch]:
        """
        Find the best matching candidate for a target string.
        
        Args:
            target: The new string to find a match for
            candidates: Dict of old_id -> (old_original, old_translation)
        
        Returns:
            Best FuzzyMatch or None if no match above threshold
        """
        best_match = None
        best_similarity = 0.0
        
        for old_id, (old_original, old_translation) in candidates.items():
            similarity = self.calculate_similarity(target, old_original)
            
            if similarity > best_similarity and similarity >= self.min_threshold:
                best_similarity = similarity
                best_match = (old_id, old_original, old_translation)
        
        if best_match:
            old_id, old_original, old_translation = best_match
            return FuzzyMatch(
                new_id="",  # Will be set by caller
                new_original=target,
                old_id=old_id,
                old_original=old_original,
                old_translation=old_translation,
                similarity=best_similarity
            )
        
        return None
    
    def match_translations(
        self,
        new_entries: Dict[str, str],  # new_id -> new_original
        old_entries: Dict[str, Tuple[str, str]]  # old_id -> (old_original, old_translation)
    ) -> FuzzyMatchReport:
        """
        Match new entries to old translations using fuzzy matching.
        
        Args:
            new_entries: Dict of new translation IDs to their original text
            old_entries: Dict of old translation IDs to (original, translation)
        
        Returns:
            FuzzyMatchReport with all matches and unmatched items
        """
        report = FuzzyMatchReport()
        
        # Track which old entries have been matched
        matched_old_ids: Set[str] = set()
        
        # Try to find matches for each new entry
        for new_id, new_original in new_entries.items():
            # Check for exact match first (same original text)
            exact_match = None
            for old_id, (old_original, old_translation) in old_entries.items():
                if old_original == new_original and old_id not in matched_old_ids:
                    exact_match = FuzzyMatch(
                        new_id=new_id,
                        new_original=new_original,
                        old_id=old_id,
                        old_original=old_original,
                        old_translation=old_translation,
                        similarity=1.0
                    )
                    matched_old_ids.add(old_id)
                    break
            
            if exact_match:
                report.matches.append(exact_match)
                continue
            
            # No exact match, try fuzzy matching
            # Only consider unmatched old entries
            available_candidates = {
                k: v for k, v in old_entries.items()
                if k not in matched_old_ids
            }
            
            match = self.find_best_match(new_original, available_candidates)
            
            if match:
                match.new_id = new_id
                matched_old_ids.add(match.old_id)
                report.matches.append(match)
            else:
                report.unmatched_new.append((new_id, new_original))
        
        # Find orphaned old translations
        for old_id, (old_original, old_translation) in old_entries.items():
            if old_id not in matched_old_ids:
                report.unmatched_old.append((old_id, old_original, old_translation))
        
        # Sort matches by similarity (highest first)
        report.matches.sort(key=lambda m: m.similarity, reverse=True)
        
        return report
    
    def suggest_translations(
        self,
        new_entries: Dict[str, str],
        old_entries: Dict[str, Tuple[str, str]],
        auto_only: bool = True
    ) -> Dict[str, str]:
        """
        Get translation suggestions for new entries.
        
        Args:
            new_entries: Dict of new IDs to original text
            old_entries: Dict of old IDs to (original, translation)
            auto_only: Only return confident matches (>= auto_threshold)
        
        Returns:
            Dict mapping new_original -> suggested_translation
        """
        report = self.match_translations(new_entries, old_entries)
        
        threshold = self.auto_threshold if auto_only else self.min_threshold
        
        return {
            m.new_original: m.old_translation
            for m in report.matches
            if m.similarity >= threshold
        }


class TranslationMemory:
    """
    Translation Memory (TM) for storing and retrieving past translations.
    
    Can be used to:
    1. Speed up translation by reusing past work
    2. Ensure consistency across projects
    3. Provide fuzzy suggestions when exact matches don't exist
    """
    
    def __init__(self, matcher: Optional[FuzzyMatcher] = None):
        self.matcher = matcher or FuzzyMatcher()
        self.memory: Dict[str, Dict[str, Tuple[str, str]]] = {}  # lang -> {id: (original, translation)}
        self.logger = logging.getLogger(__name__)
    
    def add(self, language: str, original: str, translation: str, entry_id: str = ""):
        """Add a translation to memory."""
        if language not in self.memory:
            self.memory[language] = {}
        
        # Use original text as ID if not provided
        key = entry_id or original
        self.memory[language][key] = (original, translation)
    
    def get_exact(self, language: str, original: str) -> Optional[str]:
        """Get exact match from memory."""
        if language not in self.memory:
            return None
        
        for key, (orig, trans) in self.memory[language].items():
            if orig == original:
                return trans
        
        return None
    
    def get_fuzzy(self, language: str, original: str, min_similarity: float = 0.8) -> Optional[Tuple[str, float]]:
        """
        Get fuzzy match from memory.
        
        Returns:
            Tuple of (translation, similarity) or None
        """
        if language not in self.memory:
            return None
        
        best_trans = None
        best_sim = 0.0
        
        for key, (orig, trans) in self.memory[language].items():
            sim = self.matcher.calculate_similarity(original, orig)
            if sim > best_sim and sim >= min_similarity:
                best_sim = sim
                best_trans = trans
        
        if best_trans:
            return (best_trans, best_sim)
        
        return None
    
    def get_or_suggest(self, language: str, original: str) -> Tuple[Optional[str], float, str]:
        """
        Get translation or suggestion from memory.
        
        Returns:
            Tuple of (translation, confidence, source)
            source is 'exact', 'fuzzy', or 'none'
        """
        # Try exact match first
        exact = self.get_exact(language, original)
        if exact:
            return (exact, 1.0, 'exact')
        
        # Try fuzzy match
        fuzzy = self.get_fuzzy(language, original)
        if fuzzy:
            trans, sim = fuzzy
            return (trans, sim, 'fuzzy')
        
        return (None, 0.0, 'none')
    
    def size(self, language: Optional[str] = None) -> int:
        """Get number of entries in memory."""
        if language:
            return len(self.memory.get(language, {}))
        return sum(len(entries) for entries in self.memory.values())
    
    def languages(self) -> List[str]:
        """Get list of languages in memory."""
        return list(self.memory.keys())
    
    def export_to_dict(self) -> Dict[str, Dict[str, str]]:
        """Export memory as simple dict for JSON serialization."""
        result = {}
        for lang, entries in self.memory.items():
            result[lang] = {orig: trans for key, (orig, trans) in entries.items()}
        return result
    
    def import_from_dict(self, data: Dict[str, Dict[str, str]]):
        """Import memory from dict (e.g., loaded from JSON)."""
        for lang, translations in data.items():
            for original, translation in translations.items():
                self.add(lang, original, translation)


# Common translations that should always be consistent
COMMON_UI_STRINGS = {
    "tr": {
        "Save": "Kaydet",
        "Load": "Yükle",
        "Settings": "Ayarlar",
        "Options": "Seçenekler",
        "Preferences": "Tercihler",
        "Main Menu": "Ana Menü",
        "Quit": "Çıkış",
        "Exit": "Çıkış",
        "Back": "Geri",
        "Return": "Geri Dön",
        "Yes": "Evet",
        "No": "Hayır",
        "OK": "Tamam",
        "Cancel": "İptal",
        "Continue": "Devam Et",
        "Start": "Başla",
        "New Game": "Yeni Oyun",
        "History": "Geçmiş",
        "Skip": "Atla",
        "Auto": "Otomatik",
        "Help": "Yardım",
        "About": "Hakkında",
        "Credits": "Katkıda Bulunanlar",
        "Language": "Dil",
        "Volume": "Ses",
        "Music": "Müzik",
        "Sound": "Ses Efekti",
        "Voice": "Seslendirme",
        "Text Speed": "Metin Hızı",
        "Fullscreen": "Tam Ekran",
        "Window": "Pencere",
        "Display": "Görüntü",
    },
    "en": {
        # English to English (for normalization)
        "Kaydet": "Save",
        "Yükle": "Load",
        # ... etc
    },
    "es": {
        "Save": "Guardar",
        "Load": "Cargar",
        "Settings": "Configuración",
        "Options": "Opciones",
        "Main Menu": "Menú Principal",
        "Quit": "Salir",
        "Back": "Atrás",
        "Yes": "Sí",
        "No": "No",
        "Continue": "Continuar",
        "Start": "Iniciar",
        "New Game": "Nuevo Juego",
    },
    "de": {
        "Save": "Speichern",
        "Load": "Laden",
        "Settings": "Einstellungen",
        "Options": "Optionen",
        "Main Menu": "Hauptmenü",
        "Quit": "Beenden",
        "Back": "Zurück",
        "Yes": "Ja",
        "No": "Nein",
        "Continue": "Fortfahren",
        "Start": "Starten",
        "New Game": "Neues Spiel",
    },
    "fr": {
        "Save": "Sauvegarder",
        "Load": "Charger",
        "Settings": "Paramètres",
        "Options": "Options",
        "Main Menu": "Menu Principal",
        "Quit": "Quitter",
        "Back": "Retour",
        "Yes": "Oui",
        "No": "Non",
        "Continue": "Continuer",
        "Start": "Démarrer",
        "New Game": "Nouvelle Partie",
    },
    "ru": {
        "Save": "Сохранить",
        "Load": "Загрузить",
        "Settings": "Настройки",
        "Options": "Опции",
        "Main Menu": "Главное меню",
        "Quit": "Выход",
        "Back": "Назад",
        "Yes": "Да",
        "No": "Нет",
        "Continue": "Продолжить",
        "Start": "Начать",
        "New Game": "Новая игра",
    },
    "ja": {
        "Save": "セーブ",
        "Load": "ロード",
        "Settings": "設定",
        "Options": "オプション",
        "Main Menu": "メインメニュー",
        "Quit": "終了",
        "Back": "戻る",
        "Yes": "はい",
        "No": "いいえ",
        "Continue": "続ける",
        "Start": "スタート",
        "New Game": "ニューゲーム",
    },
    "ko": {
        "Save": "저장",
        "Load": "불러오기",
        "Settings": "설정",
        "Options": "옵션",
        "Main Menu": "메인 메뉴",
        "Quit": "종료",
        "Back": "뒤로",
        "Yes": "예",
        "No": "아니오",
        "Continue": "계속",
        "Start": "시작",
        "New Game": "새 게임",
    },
    "zh": {
        "Save": "保存",
        "Load": "读取",
        "Settings": "设置",
        "Options": "选项",
        "Main Menu": "主菜单",
        "Quit": "退出",
        "Back": "返回",
        "Yes": "是",
        "No": "否",
        "Continue": "继续",
        "Start": "开始",
        "New Game": "新游戏",
    },
}


def create_common_memory() -> TranslationMemory:
    """Create a TranslationMemory pre-populated with common UI strings."""
    memory = TranslationMemory()
    memory.import_from_dict(COMMON_UI_STRINGS)
    return memory
