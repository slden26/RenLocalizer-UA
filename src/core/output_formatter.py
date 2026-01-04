"""
Output Formatter
===============

Formats translation results into Ren'Py translate block format.
"""

import logging
import hashlib
from typing import List, Dict, Set, TYPE_CHECKING, Optional
from pathlib import Path
import re

if TYPE_CHECKING:
    from src.core.translator import TranslationResult


def _preserve_case(src: str, dst: str) -> str:
    # Kaynak kelimenin büyük/küçük harfini hedefe uygula
    if src.isupper():
        return dst.upper()
    if src[0].isupper():
        return dst.capitalize()
    return dst


class RenPyOutputFormatter:
    def apply_glossary(self, text: str, glossary: dict, original_text: str = None) -> str:
        """
        Glossary'deki terimleri öncelik sırasına göre (uzun terim önce) metin içinde değiştirir.
        
        Args:
            text: Çevrilmiş metin
            glossary: {kaynak: hedef} sözlüğü
            original_text: Orijinal kaynak metin (opsiyonel, tam eşleşme kontrolü için)
        """
        if not glossary or not text:
            return text
            
        # 1. Adım: Tam eşleşme kontrolü (En etkili yöntem)
        # Eğer orijinal metin sözlükteki bir anahtarla (büyük/küçük harf duyarsız) tam eşleşiyorsa
        # doğrudan sözlükteki karşılığını döndür.
        if original_text:
            orig_stripped = original_text.strip()
            for src, dst in glossary.items():
                if src.lower() == orig_stripped.lower():
                    return dst

        # 2. Adım: Metin içinde arama ve değiştirme
        # En uzun terimler önce, çakışma riskini azaltır
        sorted_terms = sorted(glossary.items(), key=lambda x: -len(x[0]))
        result = text
        for src, dst in sorted_terms:
            # Sadece tam kelime eşleşmesi için word boundary kullan
            pattern = re.compile(r'(?i)\b' + re.escape(src) + r'\b')
            
            # Eğer kaynak kelime çevrilmiş metinde HALA DURUYORSA (çevrilmemişse) değiştir
            if pattern.search(result):
                result = pattern.sub(lambda m: _preserve_case(m.group(0), dst), result)
            
            # TODO: Gelecekte makine çevirisinin yaptığı yaygın hataları da 
            # (örn: Load -> Yük) burada yakalamak için eşleme tablosu eklenebilir.
            
        return result
    
    # File extensions that should never be translated
    SKIP_FILE_EXTENSIONS = (
        '.otf', '.ttf', '.woff', '.woff2',  # Fonts
        '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.ico',  # Images
        '.mp3', '.ogg', '.wav', '.flac', '.aac', '.m4a',  # Audio
        '.mp4', '.webm', '.avi', '.mkv', '.mov',  # Video
        '.rpy', '.rpyc', '.rpa',  # Ren'Py files
        '.py',  # Only Python source should be skipped
    )
    
    # Ren'Py technical terms that should never be translated
    # NOTE: Only lowercase terms here - Title Case like "History" are valid UI labels
    RENPY_TECHNICAL_TERMS = {
        # Screen elements & style identifiers (always lowercase in code)
        'say', 'window', 'namebox', 'choice', 'quick', 'navigation',
        'return_button', 'page_label', 'page_label_text', 'slot',
        'slot_time_text', 'slot_name_text', 'save_delete', 'pref',
        'radio', 'check', 'slider', 'tooltip_icon', 'tooltip_frame',
        'dismiss', 'history_name', 'color',  # Note: removed 'history', 'help' - valid UI labels
        'confirm_prompt', 'notify',
        'nvl_window', 'nvl_button', 'medium', 'touch', 'small',
        'replay_locked',
        # Style & layout properties
        'show', 'hide', 'unicode', 'left', 'right', 'center',
        'top', 'bottom', 'true', 'false', 'none', 'null', 'auto',
        # Common screen/action identifiers
        'add_post', 'card', 'money_get', 'money_pay', 'mp',
        'pass_time', 'rel_down', 'rel_up',
        # Input/output
        'input', 'output', 'default', 'value',
        # Common config/variable names
        'id', 'name', 'type', 'style', 'action', 'hovered', 'unhovered',
        'selected', 'insensitive', 'activate', 'alternate',
        # Common technical single words
        'idle', 'hover', 'focus', 'insensitive', 'selected_idle',
        'selected_hover', 'selected_focus', 'selected_insensitive',
    }
    
    # Pre-compiled regex patterns for performance (class-level caching)
    _FORMAT_PLACEHOLDER_RE = re.compile(r'\{[^}]*\}')
    _VARIABLE_RE = re.compile(r'\[[^\[\]]+\]')
    _DISAMBIGUATION_RE = re.compile(r'\{#[^}]+\}')
    _TAG_RE = re.compile(r'\{[^{}]*\}')
    _URL_RE = re.compile(r'^(https?://|ftp://|mailto:|www\.)')
    _HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{3,8}$')
    _NUMBER_RE = re.compile(r'^-?\d+\.?\d*$')
    _FUNC_CALL_RE = re.compile(r'^[A-Za-z_]\w*\s*\(.*\)$')
    _MODULE_ATTR_RE = re.compile(r'^[A-Za-z_]\w*\.[A-Za-z_]\w*$')
    _KEYVAL_RE = re.compile(r'^[A-Za-z0-9_\-]+\s*:\s*[A-Za-z0-9_\-]+$')
    _SNAKE_CASE_RE = re.compile(r'^[a-z][a-z0-9]*(_[a-z0-9]+)+$')
    _SCREAMING_SNAKE_RE = re.compile(r'^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$')
    _GAME_SAVE_ID_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*-\d+$')
    _VERSION_RE = re.compile(r'^v?\d+\.\d+(\.\d+)?([a-z])?$')
    _FILE_PATH_SLASH_RE = re.compile(r'^[a-zA-Z0-9_/.\-]+$')
    _FILE_PATH_BACKSLASH_RE = re.compile(r'^[a-zA-Z0-9_\\\.\-]+$')
    _ANGLE_PLACEHOLDER_RE = re.compile(r'[\u27e6\u27e7]')  # ⟦placeholder⟧ gibi
    _QMARK_PLACEHOLDER_RE = re.compile(r'\?[A-Za-z]\d{3}\?')  # ?V000? ?T000? vb.
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def _should_skip_translation(self, text: str) -> bool:
        """
        Check if a text should be skipped from translation output.
        Returns True if the text is a technical term, file path, or identifier.
        This is a SAFETY NET - parser should have already filtered most of these.
        Uses pre-compiled regex patterns for performance.
        """
        text_strip = text.strip()
        text_lower = text_strip.lower()
        
        # Skip empty text
        if not text_strip:
            return True
        
        # Skip Python format strings like {:,}, {:3d}, {}, {}Attitude:{} {}
        # These are used for number/string formatting and should not be translated
        if '{' in text_strip:
            # Count format placeholders using cached regex
            format_count = len(self._FORMAT_PLACEHOLDER_RE.findall(text_strip))
            if format_count >= 1:
                # Remove format placeholders and check remaining content
                remaining = self._FORMAT_PLACEHOLDER_RE.sub('', text_strip).strip()
                # If remaining has no meaningful letters, skip
                if not re.search(r'[a-zA-ZçğıöşüÇĞIİÖŞÜа-яА-Яа-яА-Я]{3,}', remaining):
                    return True
                # If format placeholders dominate the string, skip
                if format_count >= 2 and len(remaining) < 10:
                    return True
        
        # Skip file names/paths (fonts, images, audio, etc.)
        if any(text_lower.endswith(ext) for ext in self.SKIP_FILE_EXTENSIONS):
            return True
        
        # Skip paths starting with common folder names
        if text_strip.startswith(('fonts/', 'images/', 'audio/', 'music/', 'sounds/', 
                                   'gui/', 'screens/', 'script/', 'game/', 'tl/')):
            return True
        
        # Skip paths with slashes (file paths like "fonts/something.otf")
        if '/' in text_strip and ' ' not in text_strip:
            if self._FILE_PATH_SLASH_RE.match(text_strip):
                return True
        
        # Skip backslash paths (Windows style)
        if '\\' in text_strip and ' ' not in text_strip:
            if self._FILE_PATH_BACKSLASH_RE.match(text_strip):
                return True
        
        # Skip URLs (using cached pattern)
        if self._URL_RE.match(text_lower):
            return True
        
        # Skip hex color codes (using cached pattern)
        if self._HEX_COLOR_RE.match(text_strip):
            return True
        
        # Skip pure numbers (using cached pattern)
        if self._NUMBER_RE.match(text_strip):
            return True
        
        # Skip Ren'Py technical terms - ONLY exact lowercase match
        # "history" -> skip, "History" -> translate (UI label)
        if text_strip in self.RENPY_TECHNICAL_TERMS:
            return True

        # Skip likely function calls or code-like literals
        if self._FUNC_CALL_RE.match(text_strip):
            return True
        # Skip module.attribute references
        if self._MODULE_ATTR_RE.match(text_strip):
            return True
        # Skip key:value like config entries
        if self._KEYVAL_RE.match(text_strip):
            return True

        # Skip angled placeholder markers like ⟦V000⟧
        if self._ANGLE_PLACEHOLDER_RE.search(text_strip):
            return True

        # Skip question-mark placeholders like ?V000? ?T000?
        if self._QMARK_PLACEHOLDER_RE.search(text_strip):
            return True

        # Skip obvious config/version placeholders that should remain untouched
        if "config.version" in text_strip or "[config." in text_strip:
            return True

        # Skip snake_case identifiers (using cached pattern)
        if self._SNAKE_CASE_RE.match(text_strip):
            return True
        
        # Skip SCREAMING_SNAKE_CASE constants (using cached pattern)
        if self._SCREAMING_SNAKE_RE.match(text_strip):
            return True
        
        # Skip save identifiers like "GameName-1234567890" (using cached pattern)
        if self._GAME_SAVE_ID_RE.match(text_strip):
            return True
        
        # Skip version strings (using cached pattern)
        if self._VERSION_RE.match(text_lower):
            return True
        
        # Skip if it's just Ren'Py tags/variables with no actual text
        stripped_of_tags = self._TAG_RE.sub('', text_strip)
        stripped_of_vars = self._VARIABLE_RE.sub('', stripped_of_tags)
        if not stripped_of_vars.strip():
            return True
        
        return False
    
    def sanitize_translation_id(self, text: str) -> str:
        """Create a valid Ren'Py translation ID from text (sanitized, short)."""
        text = re.sub(r'[^a-zA-Z0-9_]', '_', text)
        text = re.sub(r'_+', '_', text).strip('_')
        if text and text[0].isdigit():
            text = '_' + text
        return (text or 'translated_text')[:50]

    def make_hash_id(self, original_text: str, context_path: Optional[List[str]] = None,
                     file_path: str = "", line_number: int = 0) -> str:
        """Hash-based primary ID; context-aware to avoid collisions."""
        base = f"{file_path}:{line_number}:{'|'.join(context_path or [])}:{original_text}"
        digest = hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()[:16]
        return f"id_{digest}"
    
    def escape_renpy_string(self, text: str) -> str:
        """Escape special characters for Ren'Py strings.
        
        Handles:
        - Backslashes, quotes, newlines, tabs, carriage returns
        - Protects Ren'Py variables [var], [var!t] and tags {tag}
        - Protects disambiguation tags {#identifier}
        - Handles double brackets [[ and {{
        """
        if not text:
            return text
            
        import re
        
        # Find all Ren'Py variables [variable] and expressions (including !t flag)
        variable_pattern = re.compile(r'\[[^\[\]]+\]')
        variables = variable_pattern.findall(text)
        
        # CRITICAL: Find disambiguation tags {#...} FIRST - these must be preserved exactly
        disambiguation_pattern = re.compile(r'\{#[^}]+\}')
        disambiguation_tags = disambiguation_pattern.findall(text)
        
        # Find all Ren'Py tags like {i}, {b}, {color=#ff0000}, {/i}, etc.
        tag_pattern = re.compile(r'\{[^{}]*\}')
        tags = tag_pattern.findall(text)
        
        # Replace variables and tags with placeholders temporarily
        temp_text = text
        protection_map = {}
        counter = 0
        
        # Protect disambiguation tags FIRST (highest priority)
        for dtag in disambiguation_tags:
            placeholder = f"⟦DIS{counter:03d}⟧"
            protection_map[placeholder] = dtag
            temp_text = temp_text.replace(dtag, placeholder, 1)
            counter += 1
        
        # Protect variables
        for var in variables:
            placeholder = f"⟦VAR{counter:03d}⟧"
            protection_map[placeholder] = var
            temp_text = temp_text.replace(var, placeholder, 1)
            counter += 1
        
        # Protect tags (excluding disambiguation which are already protected)
        for tag in tags:
            if tag.startswith('{#'):  # Skip disambiguation tags
                continue
            placeholder = f"⟦TAG{counter:03d}⟧"
            protection_map[placeholder] = tag
            temp_text = temp_text.replace(tag, placeholder, 1)
            counter += 1
        
        # Handle literal double brackets BEFORE escaping
        # [[ should become \[\[ in Ren'Py to show literal [
        temp_text = temp_text.replace('[[', '\\[\\[')
        temp_text = temp_text.replace('{{', '\\{\\{')
        
        # Now escape the rest
        temp_text = temp_text.replace('\\', '\\\\')  # Escape backslashes first
        temp_text = temp_text.replace('"', '\\"')     # Escape double quotes
        temp_text = temp_text.replace('\r', '')       # Remove carriage returns
        temp_text = temp_text.replace('\n', '\\n')    # Escape newlines
        temp_text = temp_text.replace('\t', '\\t')    # Escape tabs
        
        # Restore variables and tags
        for placeholder, original_content in protection_map.items():
            temp_text = temp_text.replace(placeholder, original_content)
        
        return temp_text
    
    def generate_translation_block(self, 
                                 original_text: str, 
                                 translated_text: str, 
                                 language_code: str,
                                 translation_id: str = None,
                                 context: str = None,
                                 mode: str = "simple") -> str:
        """Generate a single translation block."""
        
        if not translation_id:
            # Create string-based translation that matches any label
            # This is more compatible with existing Ren'Py games
            import hashlib
            text_hash = hashlib.md5(original_text.encode('utf-8')).hexdigest()[:8]
            translation_id = f"strings_{text_hash}"
        
        escaped_original = self.escape_renpy_string(original_text)
        escaped_translated = self.escape_renpy_string(translated_text)
        
        if mode == "old_new":
            # Old/new format - INDIVIDUAL ENTRY (for building larger block)
            block = (
                f"    old \"{escaped_original}\"\n"
                f"    new \"{escaped_translated}\"\n\n"
            )
        else:
            # Simple format - original text in comment, direct translation line
            comment_original = escaped_original.replace('\n', '\\n')
            block = (
                f"    # \"{comment_original}\"\n"
                f"    \"{escaped_translated}\"\n\n"
            )
        
        return block
    
    def generate_character_translation(self,
                                     character_name: str,
                                     original_text: str,
                                     translated_text: str,
                                     language_code: str,
                                     translation_id: str = None,
                                     mode: str = "simple") -> str:
        """Generate a character dialogue translation block."""
        
        escaped_original = self.escape_renpy_string(original_text)
        escaped_translated = self.escape_renpy_string(translated_text)
        
        if mode == "old_new":
            # String-based format - INDIVIDUAL ENTRY (for building larger block)
            block = (
                f"    old {character_name} \"{escaped_original}\"\n"
                f"    new {character_name} \"{escaped_translated}\"\n\n"
            )
        else:
            # Simple format - original text in comment, direct translation line
            comment_original = escaped_original.replace('\n', '\\n')
            block = (
                f"    # {character_name} \"{comment_original}\"\n"
                f"    {character_name} \"{escaped_translated}\"\n\n"
            )
        
        return block
    
    def generate_menu_translation(self,
                                menu_options: List[Dict],
                                language_code: str,
                                menu_id: str = None) -> str:
        """Generate menu translation block - DEPRECATED. 
        
        Menu translations should use translate strings format instead.
        This method is kept for compatibility but menu items should be 
        included in the main strings block.
        """
        
        # Menu choices should be in translate strings block, not separate menu blocks
        # According to RenPy documentation: menu choices use "translate strings" format
        
        block = f"# NOTE: Menu choices should be in 'translate {language_code} strings:' block\n"
        block += f"# This is the old format and may not work properly in RenPy\n\n"
        
        if not menu_id:
            menu_id = f"menu_{self.sanitize_translation_id('_'.join([opt['original'] for opt in menu_options[:3]]))}"
        
        block += f"translate {language_code} {menu_id}:\n\n"
        
        for i, option in enumerate(menu_options):
            original = self.escape_renpy_string(option['original'])
            translated = self.escape_renpy_string(option['translated'])
            # Add each choice with real newlines
            block += f'    # "{original}"\n'
            block += f'    "{translated}"\n'
        
        block += "\n"
        return block
    
    def format_translation_file(self,
                              translation_results: List,
                              language_code: str,
                              source_file: Path = None,
                              include_header: bool = True,
                              output_format: str = "old_new",
                              glossary: dict = None) -> str:
        """Format complete translation file with SEPARATE blocks for each translation."""
        
        output_lines = []
        
        if include_header:
            header = self.generate_file_header(language_code, source_file)
            output_lines.append(header)
        
        # CRITICAL FIX: Create ONE translate strings block for ALL translations
        # This is the CORRECT Ren'Py format
        
        seen_translations = set()
        string_translations = []
        
        # Add the opening translate strings block
        string_translations.append(f"translate {language_code} strings:")
        string_translations.append("")
        
        for result in translation_results:
            if not result.success or not result.translated_text:
                continue

            original_text = result.original_text
            translated_text = result.translated_text
            metadata = getattr(result, 'metadata', {}) or {}
            ctx_path = metadata.get('context_path') or []
            if isinstance(ctx_path, str):
                ctx_path = [ctx_path]
            file_path = metadata.get('file_path', '')
            line_number = metadata.get('line_number', 0)
            translation_id = metadata.get('translation_id') or getattr(result, 'translation_id', None)
            if not translation_id:
                translation_id = self.make_hash_id(original_text, ctx_path, file_path, line_number)

            # GLOSSARY uygula (sadece çeviri metnine)
            if glossary:
                translated_text = self.apply_glossary(translated_text, glossary, original_text=original_text)

            # CRITICAL: Skip technical content that should not be translated
            if self._should_skip_translation(original_text):
                self.logger.debug(f"Skipping technical content: {original_text[:50]}...")
                continue

            # Avoid duplicates - use translation_id primarily, fallback to text pair
            key = translation_id or f"{original_text}_{translated_text}"
            if key in seen_translations:
                continue
            seen_translations.add(key)

            text_type = getattr(result, 'text_type', None)
            
            # Add source file/line comment for translator reference (if available)
            source_info = ""
            if hasattr(result, 'metadata') and result.metadata:
                file_path = result.metadata.get('file_path', '')
                line_number = result.metadata.get('line_number', '')
                if file_path and line_number:
                    # Extract just filename for cleaner output
                    import os
                    filename = os.path.basename(file_path)
                    source_info = f"    # {filename}:{line_number}\n"
            
            # Check if this is a paragraph text (_p() function)
            is_paragraph = (
                text_type == 'paragraph' or 
                '\n\n' in original_text or  # Contains paragraph breaks
                len(original_text) > 200  # Long text likely from _p()
            )
            
            if is_paragraph:
                # Use _p() format for paragraph text
                escaped_original = self._escape_for_old_string(original_text)
                formatted_translated = self._format_p_function_output(translated_text)
                
                if output_format == "old_new":
                    if source_info:
                        string_translations.append(source_info.rstrip())
                    string_translations.append(f"    # id: {translation_id}")
                    string_translations.append(f'    old "{escaped_original}"')
                    string_translations.append(f'    new {formatted_translated}')
                    string_translations.append("")
                else:
                    # Simple format - just old/new without meta-comments
                    string_translations.append(f'    old "{escaped_original}"')
                    string_translations.append(f'    new {formatted_translated}')
                    string_translations.append("")
            else:
                # Standard string format
                escaped_original = self.escape_renpy_string(original_text)
                escaped_translated = self.escape_renpy_string(translated_text)
                
                if output_format == "old_new":
                    if source_info:
                        string_translations.append(source_info.rstrip())
                    string_translations.append(f"    # id: {translation_id}")
                    string_translations.append(f'    old "{escaped_original}"')
                    string_translations.append(f'    new "{escaped_translated}"')
                    string_translations.append("")
                else:
                    # Simple format - just old/new without meta-comments
                    string_translations.append(f'    old "{escaped_original}"')
                    string_translations.append(f'    new "{escaped_translated}"')
                    string_translations.append("")
        
        # Combine header and strings
        output_lines.extend(string_translations)
        
        # Join sections with real newlines
        return "\n".join(output_lines)
    
    def _escape_for_old_string(self, text: str) -> str:
        """
        Escape text for use in 'old' string.
        Ren'Py expects paragraph breaks as literal \\n\\n in old strings.
        """
        # Protect Ren'Py variables and tags first
        variable_pattern = re.compile(r'\[[^\[\]]+\]')
        tag_pattern = re.compile(r'\{[^{}]*\}')
        
        variables = variable_pattern.findall(text)
        tags = tag_pattern.findall(text)
        
        temp_text = text
        protection_map = {}
        
        for i, var in enumerate(variables):
            placeholder = f"__VAR_{i}__"
            protection_map[placeholder] = var
            temp_text = temp_text.replace(var, placeholder, 1)
        
        for i, tag in enumerate(tags):
            placeholder = f"__TAG_{i}__"
            protection_map[placeholder] = tag
            temp_text = temp_text.replace(tag, placeholder, 1)
        
        # Escape quotes and backslashes
        temp_text = temp_text.replace('\\', '\\\\')
        temp_text = temp_text.replace('"', '\\"')
        
        # Convert newlines to escaped form for old string
        temp_text = temp_text.replace('\n', '\\n')
        
        # Restore protected content
        for placeholder, original_content in protection_map.items():
            temp_text = temp_text.replace(placeholder, original_content)
        
        return temp_text
    
    def _format_p_function_output(self, text: str) -> str:
        """
        Format translated text as _p() function for Ren'Py.
        Example output:
        _p(\"\"\"
            First paragraph line one
            first paragraph line two.

            Second paragraph.
            \"\"\")
        """
        # Split by paragraph breaks
        paragraphs = text.split('\n\n')
        
        # Format with proper indentation for _p() 
        lines = ['_p("""']
        
        for i, para in enumerate(paragraphs):
            # Each paragraph on its own line with indentation
            para_lines = para.split('\n')
            for line in para_lines:
                lines.append(f"    {line.strip()}")
            
            # Add blank line between paragraphs (except after last)
            if i < len(paragraphs) - 1:
                lines.append("")
        
        lines.append('    """)')
        
        return '\n'.join(lines)
    
    def generate_file_header(self, language_code: str, source_file: Path = None) -> str:
        """Generate file header with metadata."""
        from datetime import datetime
        from src.version import VERSION
        
        header = f"""# Ren'Py Translation File
# Language: {language_code}
# Generated by: RenLocalizer v{VERSION}
# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        if source_file:
            header += f"# Source file: {source_file}\\n"
        
        header += """
# This file contains automatic translations.
# Please review and edit as needed.

"""
        return header
    
    def save_translation_file(self,
                            translation_results: List,
                            output_path: Path,
                            language_code: str,
                            source_file: Path = None,
                            output_format: str = "simple") -> bool:
        """Save translations to file."""
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate content
            content = self.format_translation_file(
                translation_results,
                language_code,
                source_file,
                output_format=output_format
            )
            
            # Write file with UTF-8 encoding (with BOM for Windows compatibility)
            # Using utf-8-sig ensures Ren'Py correctly reads the file on all systems
            with open(output_path, 'w', encoding='utf-8-sig', newline='\n') as f:
                f.write(content)
            
            self.logger.info(f"Saved translation file: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving translation file {output_path}: {e}")
            return False
    
    def organize_output_files(self,
                            translation_results: List,
                            output_base_dir: Path,
                            language_code: str,
                            source_files: List[Path] = None,
                            output_format: str = "old_new",
                            create_renpy_structure: bool = True) -> List[Path]:
        """Organize translations into language-specific directories."""
        
        output_files = []
        
        # Determine if this is a Ren'Py project and create proper structure
        if create_renpy_structure:
            # Check if we're in a Ren'Py project (has game folder)
            game_dir = self._find_game_directory(output_base_dir)
            if game_dir:
                # Create Ren'Py translation structure: game/tl/[language]/
                lang_dir = game_dir / "tl" / language_code
                self.logger.info(f"Creating Ren'Py translation structure: {lang_dir}")
                
                # Create language initialization file for Ren'Py - do it immediately
                self._create_language_init_file(game_dir, language_code)
            else:
                # Not a Ren'Py project, create standard structure
                lang_dir = output_base_dir / language_code
                self.logger.info(f"Creating standard translation structure: {lang_dir}")
        else:
            # Create language directory
            lang_dir = output_base_dir / language_code
        
        lang_dir.mkdir(parents=True, exist_ok=True)
        
        # CRITICAL FIX: Create ONE translation file for all strings
        # This prevents duplicate string errors in Ren'Py
        
        # Global deduplication - remove EXACT duplicates only
        # NOTE: Case-sensitive! "Cafeteria" and "cafeteria" are DIFFERENT strings in Ren'Py
        seen_strings = set()
        unique_results = []
        
        for result in translation_results:
            # Case-sensitive key - Ren'Py treats "Cafeteria" and "cafeteria" as different strings
            string_key = result.original_text.strip()
            if string_key not in seen_strings:
                seen_strings.add(string_key)
                unique_results.append(result)
            else:
                self.logger.debug(f"Skipping duplicate string: {result.original_text[:50]}...")
        
        # Create single master translation file
        # Use 'strings.rpy' for Ren'Py compatibility (same as _run_translate_command)
        output_filename = f"strings.rpy"
        output_path = lang_dir / output_filename
        
        if self.save_translation_file(
            unique_results, 
            output_path, 
            language_code, 
            None,  # No specific source file
            output_format=output_format
        ):
            output_files.append(output_path)
            self.logger.info(f"Created master translation file: {output_path} with {len(unique_results)} unique strings")
        
        return output_files
    
    def _find_game_directory(self, base_path: Path) -> Path:
        """Find the game directory in a Ren'Py project."""
        # Check current directory and parent directories for 'game' folder
        current = Path(base_path).resolve()
        
        # Check if current path contains 'game' folder
        if (current / "game").exists() and (current / "game").is_dir():
            return current / "game"
        
        # Check parent directories
        for parent in current.parents:
            game_dir = parent / "game"
            if game_dir.exists() and game_dir.is_dir():
                # Verify it's a Ren'Py game directory by checking for common files
                if any((game_dir / file).exists() for file in ["options.rpy", "script.rpy", "gui.rpy"]):
                    return game_dir
        
        # Check if current directory itself is the game directory
        if any((current / file).exists() for file in ["options.rpy", "script.rpy", "gui.rpy"]):
            return current
        
        return None
    
    def _create_language_init_file(self, game_dir: Path, language_code: str):
        """RenPy dökümantasyonuna tam uyumlu, sade başlatıcı dosya üretimi."""
        try:
            init_file_path = game_dir / f"a0_{language_code}_language.rpy"
            init_content = f'define config.language = "{language_code}"\n'
            with open(init_file_path, 'w', encoding='utf-8-sig', newline='\n') as f:
                f.write(init_content)
            self.logger.info(f"Created minimal language file: {init_file_path}")
        except Exception as e:
            self.logger.error(f"Error creating language init file: {e}")
