"""
Ren'Py-aware parser used by RenLocalizer.

The parser keeps track of indentation-based blocks so it can better decide
which strings should be translated and which ones belong to technical code.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import chardet
from src.utils.encoding import read_text_safely
import configparser
import yaml

# Module-level defaults for datasets / whitelist for rpyc reader import
DATA_KEY_BLACKLIST = {
    'id', 'code', 'name_id', 'image', 'img', 'icon', 'sfx', 'sound', 'audio',
    'voice', 'file', 'path', 'url', 'link', 'type', 'ref', 'var', 'value_id', 'texture'
}

DATA_KEY_WHITELIST = {
    'name', 'title', 'description', 'desc', 'text', 'content', 'caption',
    'label', 'prompt', 'help', 'header', 'footer', 'message', 'dialogue',
    'summary', 'quest', 'objective', 'char', 'character',
    'tips', 'hints', 'help', 'notes', 'log', 'history', 'inventory', 'items', 'objectives', 'goals', 'achievements', 'gallery'
}


@dataclass
class ContextNode:
    indent: int
    kind: str
    name: str = ""


class RenPyParser:
    def __init__(self, config_manager=None):
        self.logger = logging.getLogger(__name__)
        self.config = config_manager

        # Blacklist/whitelist for data keys
        self.DATA_KEY_BLACKLIST = {
            'id', 'code', 'name_id', 'image', 'img', 'icon', 'sfx', 'sound', 'audio',
            'voice', 'file', 'path', 'url', 'link', 'type', 'ref', 'var', 'value_id', 'texture'
        }
        self.DATA_KEY_WHITELIST = {
            'name', 'title', 'description', 'desc', 'text', 'content', 'caption',
            'label', 'prompt', 'help', 'header', 'footer', 'message', 'dialogue',
            'summary', 'quest', 'objective', 'char', 'character',
            'tips', 'hints', 'help', 'notes', 'log', 'history', 'inventory', 'items', 'objectives', 'goals', 'achievements', 'gallery'
        }

        # Technical terms for filtering
        self.renpy_technical_terms = {
            'left', 'right', 'center', 'top', 'bottom', 'gui', 'config',
            'true', 'false', 'none', 'auto', 'png', 'jpg', 'mp3', 'ogg'
        }

        # Edge-case: Ren'Py screen language - ignore technical screen elements
        self.technical_screen_elements = {
            'vbox', 'hbox', 'frame', 'window', 'viewport', 'scrollbar', 'bar', 'slider',
            'imagebutton', 'hotspot', 'hotbar', 'side', 'input', 'button', 'confirm', 'notify',
            'layout', 'store', 'style', 'action', 'caption', 'title', 'textbutton', 'label', 'tooltip'
        }

        # Edge-case: Ignore lines with only technical terms or variable assignments
        self.technical_line_re = re.compile(r'^(?:define|init|style|config|gui|store|layout)\b.*=\s*[^"\']+$')

        # Edge-case: Ignore lines with only numbers, file paths, or color codes
        self.numeric_or_path_re = re.compile(r'^(?:[0-9]+|[a-zA-Z0-9_/\\.-]+\.(?:png|jpg|ogg|mp3|rpy|rpyc)|#[0-9a-fA-F]{3,8})$')

        # Edge-case: Ignore lines with only Ren'Py variables or tags
        self.renpy_var_or_tag_re = re.compile(r'^(\{[^}]+\}|\[[^\]]+\])$')

        # Edge-case: Ignore lines with only whitespace or comments
        self.comment_or_empty_re = re.compile(r'^(\s*#.*|\s*)$')

        # Edge-case: Menu/choice with technical condition (if, else, jump, call)
        self.menu_technical_condition_re = re.compile(r'^\s*(?:if|else|jump|call)\b.*:')

        # Edge-case: AST node type filtering (for future AST integration)
        self.ast_technical_types = {
            'Store', 'Config', 'Style', 'Layout', 'ImageButton', 'Hotspot', 'Hotbar', 'Slider', 'Viewport', 'ScrollBar', 'Action', 'Confirm', 'Notify', 'Input', 'Frame', 'Window', 'Vbox', 'Hbox', 'Side', 'Caption', 'Title', 'Label', 'Tooltip', 'TextButton'
        }
        # --- Core regex patterns and registries (ensure attributes exist for tests) ---
        # Common quoted-string pattern (handles optional prefixes like r, u, b, f)
        self._quoted_string = r'(?:[rRuUbBfF]{,2})?(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'

        self.char_dialog_re = re.compile(
            r'^(?P<indent>\s*)(?P<char>[A-Za-z_]\w*)\s+'
            r'(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        self.narrator_re = re.compile(
            r'^(?P<indent>\s*)(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*(?:#.*)?$'
        )

        self.char_multiline_re = re.compile(
            r'^(?P<indent>\s*)(?P<char>[A-Za-z_]\w*)\s+(?P<delim>"""|\'\'\')(?P<body>.*)$'
        )
        self.narrator_multiline_re = re.compile(
            r'^(?P<indent>\s*)(?P<delim>"""|\'\'\')(?P<body>(?![\s]*\)).*)$'
        )
        self.extend_multiline_re = re.compile(
            r'^(?P<indent>\s*)extend\s+(?P<delim>"""|\'\'\')(?P<body>(?![\s]*\)).*)$'
        )

        self.menu_choice_re = re.compile(
            r'^\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*(?:if\s+[^:]+)?\s*:\s*'
        )
        self.menu_choice_multiline_re = re.compile(
            r'^\s*(?P<delim>"""|\'\'\')(?P<body>(?![\s]*\)).*)\s*(?:if\s+[^:]+)?\s*:\s*$'
        )
        self.menu_title_re = re.compile(
            r'^\s*menu\s*(?:[rRuUbBfF]{,2})?(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')?:'
        )

        self.screen_text_re = re.compile(
            r'\s*(?:text|label|tooltip|vbar|slider|frame|window)\s+(?:_\s*\(\s*)?(?:[rRuUbBfF]{,2})?(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')(?:\s*\))?'
        )
        self.textbutton_re = re.compile(
            r'^\s*textbutton\s+(?:_\s*\(\s*)?(?:[rRuUbBfF]{,2})?(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')(?:\s*\))?'
        )
        self.textbutton_translatable_re = re.compile(
            r"^\s*textbutton\s+_\s*\(\s*(?:[rRuUbBfF]{,2})?(?P<quote>\"(?:[^\"\\]|\\.)*\"|'(?:[^\\']|\\.)*')\s*\)"
        )
        self.screen_text_translatable_re = re.compile(
            r"^\s*(?:text|label|tooltip)\s+_\s*\(\s*(?:[rRuUbBfF]{,2})?(?P<quote>\"(?:[^\"\\]|\\.)*\"|'(?:[^\\']|\\.)*')\s*\)"
        )
        self.screen_multiline_re = re.compile(
            r'^\s*(?:text|label|tooltip|textbutton)\s+(?:_\s*\(\s*)?(?P<delim>"""|\'\'\')(?P<body>.*)$'
        )

        self.config_string_re = re.compile(
            r"^\s*config\.(?:name|version|about|menu_|window_title|save_name)\s*=\s*(?:[rRuUbBfF]{,2})?(?P<quote>\"(?:[^\"\\]|\\.)*\"|'(?:[^\\']|\\.)*')"
        )
        self.gui_text_re = re.compile(
            r"^\s*gui\.(?:text|button|label|title|heading|caption|tooltip|confirm)(?:_[a-z_]*)?(?:\[[^\]]*\])?\s*=\s*(?P<quote>\"(?:[^\"\\]|\\.)*\"|'(?:[^\\']|\\.)*')"
        )
        self.style_property_re = re.compile(
            r"^\s*style\s*\.\s*[a-zA-Z_]\w*\s*=\s*(?P<quote>\"(?:[^\"\\]|\\.)*\"|'(?:[^\\']|\\.)*')"
        )

        # Simplified patterns to avoid complex nested quoting issues
        self._p_single_re = re.compile(r'^\s*(?:define\s+)?(?:gui|config)\.[a-zA-Z_]\w*\s*=\s*_p\s*\(')
        self._p_multiline_re = re.compile(r'^\s*(?:define\s+)?(?:gui|config)\.[a-zA-Z_]\w*\s*=\s*_p\s*\(\s*"""')
        self._underscore_re = re.compile(r'^\s*(?:define\s+)?[a-zA-Z_]\w*\s*=\s*(?:Character\s*\()?_\s*\(')
        self.define_string_re = re.compile(r'^\s*define\s+(?:gui|config)\.[a-zA-Z_]\w*\s*=\s*')

        self.alt_text_re = re.compile(r'\balt\b')
        self.input_text_re = re.compile(r'\b(default|prefix|suffix)\b')

        self.gui_variable_re = re.compile(r'^\s*gui\.')

        # Use the shared quoted-string pattern for these common cases to avoid
        # duplicated complex literals and accidental unbalanced escapes.
        self.renpy_show_re = re.compile(r'^\s*(?:\$\s+)?renpy\.show\s*\(\s*' + self._quoted_string)

        self.layout_text_re = re.compile(r'^\s*layout\.[a-zA-Z0-9_]+\s*=\s*' + self._quoted_string)
        self.store_text_re = re.compile(r'^\s*store\.[a-zA-Z0-9_]+\s*=\s*' + self._quoted_string)
        self.general_define_re = re.compile(r'^\s*define\s+[a-zA-Z0-9_.]+\s*=\s*' + self._quoted_string)

        # pattern registry placeholder (populated later in code)
        self.pattern_registry = []
        self.multiline_registry = []
        self.menu_def_re = re.compile(r'^menu\s*(?:"([^\"]*)"|\'([^\']*)\')?:')
        self.screen_def_re = re.compile(r'^screen\s+([A-Za-z_]\w*)')
        self.python_block_re = re.compile(r'^(?:init(?:\s+[-+]?\d+)?\s+)?python\b.*:')
        # Label definition (ensure present for tests)
        self.label_def_re = re.compile(r'^label\s+([A-Za-z_][\w\.]*)\s*(?!hide):')
        # -------------------------------------------------------------------------
        
        # Initialize v2.4.1 patterns
        self._init_new_patterns()
        
    # ========== NEW PATTERNS FOR BETTER EXTRACTION (v2.4.1) ==========
    # These are initialized in __init__ but need class-level declarations
    nvl_narrator_re = None
    default_translatable_re = None
    show_screen_re = None
    translate_block_re = None

    def _init_new_patterns(self):
        """Initialize v2.4.1 patterns (called from __init__)."""
        import re
        
        # NVL narrator pattern - triple-quoted dialogues
        self.nvl_narrator_re = re.compile(
            r'^\s*nvl\s+clear\s+(?P<delim>"""|\'\'\')(?P<body>.*)$'
        )
        
        # Default translatable variables: default myvar = _("text")
        self.default_translatable_re = re.compile(
            r'^\s*default\s+[a-zA-Z_]\w*\s*=\s*_\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*\)'
        )
        
        # Show screen with string parameters
        self.show_screen_re = re.compile(
            r'^\s*show\s+screen\s+[a-zA-Z_]\w*\s*\((?:[^,)]*,\s*)*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # Translate block detection (to skip already translated content)
        self.translate_block_re = re.compile(
            r'^\s*translate\s+([a-zA-Z_]\w*)\s+([a-zA-Z_]\w*)\s*:'
        )

    # ========== END NEW PATTERNS ==========

    def _register_patterns(self):
        self.pattern_registry = [
            {'regex': self.layout_text_re, 'type': 'layout'},
            {'regex': self.store_text_re, 'type': 'store'},
            {'regex': self.general_define_re, 'type': 'define'},
            # Most specific patterns first
            # Combined patterns for better maintainability
            {'regex': self.alt_text_re, 'type': 'alt_text'},
            {'regex': self.input_text_re, 'type': 'input'},
            {'regex': self.notify_re, 'type': 'notify'},
            {'regex': self.confirm_re, 'type': 'confirm'},
            {'regex': self.renpy_input_re, 'type': 'input'},
            # _() marked screen elements - ALWAYS translatable (check BEFORE general patterns)
            {'regex': self.textbutton_translatable_re, 'type': 'translatable_string'},
            {'regex': self.screen_text_translatable_re, 'type': 'translatable_string'},
            # NEW: Enhanced patterns for better coverage
            {'regex': self.atl_text_re, 'type': 'ui'},           # ATL text blocks
            {'regex': self.renpy_say_re, 'type': 'dialogue'},    # renpy.say() calls
            {'regex': self.action_text_re, 'type': 'translatable_string'},  # action _(\"text\")
            {'regex': self.caption_re, 'type': 'ui'},            # caption attributes
            {'regex': self.frame_title_re, 'type': 'ui'},        # frame/window titles
            {'regex': self.generic_translatable_re, 'type': 'translatable_string'},  # generic _()
            # _p() and _() function patterns
            {'regex': self._p_single_re, 'type': 'paragraph'},
            {'regex': self._underscore_re, 'type': 'translatable_string'},
            {'regex': self.define_string_re, 'type': 'define'},
            # Config/GUI patterns
            {'regex': self.config_string_re, 'type': 'config'},
            {'regex': self.gui_text_re, 'type': 'gui'},
            {'regex': self.style_property_re, 'type': 'style'},
            # Screen UI patterns (textbutton before general text)
            {'regex': self.textbutton_re, 'type': 'button'},
            {'regex': self.screen_text_re, 'type': 'ui'},
            {'regex': self.side_text_re, 'type': 'ui'},
            # Menu patterns
            {'regex': self.menu_choice_re, 'type': 'menu'},
            {'regex': self.menu_title_re, 'type': 'menu'},
            # Python/renpy functions
            {'regex': self.python_renpy_re, 'type': 'renpy_func'},
            {'regex': self.renpy_function_re, 'type': 'renpy_func'},
            # Dialogue patterns (most general - last)
            {'regex': self.char_dialog_re, 'type': 'dialogue', 'character_group': 'char'},
            {'regex': self.extend_re, 'type': 'dialogue'},
            {'regex': self.narrator_re, 'type': 'dialogue'},
            {'regex': self.gui_variable_re, 'type': 'gui'},
            {'regex': self.renpy_show_re, 'type': 'ui'},
            # NEW v2.4.1 patterns
            {'regex': self.default_translatable_re, 'type': 'translatable_string'},
            {'regex': self.show_screen_re, 'type': 'ui'},
        ]

        self.multiline_registry = [
            {'regex': self.char_multiline_re, 'type': 'dialogue', 'character_group': 'char'},
            {'regex': self.extend_multiline_re, 'type': 'dialogue'},
            {'regex': self.narrator_multiline_re, 'type': 'dialogue'},
            {'regex': self.screen_multiline_re, 'type': 'ui'},
            # _p() multi-line patterns - check FIRST as it's most specific
            {'regex': self._p_multiline_re, 'type': 'paragraph'},
            # NEW v2.4.1 patterns
            {'regex': self.nvl_narrator_re, 'type': 'dialogue'},
        ]

        self.renpy_technical_terms = {
            'left', 'right', 'center', 'top', 'bottom', 'gui', 'config',
            'true', 'false', 'none', 'auto', 'png', 'jpg', 'mp3', 'ogg'
        }

        # Blacklist for technical keys in data files
        self.DATA_KEY_BLACKLIST = set(DATA_KEY_BLACKLIST)
        # Whitelist for keys that usually contain user-facing text
        self.DATA_KEY_WHITELIST = set(DATA_KEY_WHITELIST)

    def extract_from_csv(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract translatable text from CSV files."""
        entries = []
        try:
            import csv
            # Ren'Py devs often use UTF-8, but sometimes Excel saves as CP1252. We try UTF-8 first.
            try:
                content = self._read_file_lines(file_path)
            except Exception:
                # Fallback to reading as generic text if helper fails
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.readlines()
            # Re-join to parse with CSV module
            full_text = '\n'.join(content)
            from io import StringIO
            f_io = StringIO(full_text)
            # Detect dialect (separator , or ;)
            try:
                dialect = csv.Sniffer().sniff(full_text[:1024])
            except csv.Error:
                dialect = None
            reader = csv.reader(f_io, dialect) if dialect else csv.reader(f_io)
            for row_idx, row in enumerate(reader):
                for col_idx, cell in enumerate(row):
                    # Use existing smart filter
                    # If row 0, it might be a header, but we translate it anyway if it looks like text
                    # Additional sanity: remove placeholders/tags and require at least
                    # two letters to be considered translatable; attach a raw_text
                    # field (escaped and quoted) for deterministic ID generation.
                    import re
                    cleaned = re.sub(r'(\[[^\]]+\]|\{[^}]+\})', '', cell or '').strip()
                    # Language-independent: require at least two Unicode letters
                    if sum(1 for ch in cleaned if ch.isalpha()) < 2:
                        continue
                    raw_text = '"' + (cell.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')) + '"'
                    entries.append({
                        'text': cell,
                        'raw_text': raw_text,
                        'line_number': row_idx + 1,
                        'context_line': f"csv:row{row_idx}_col{col_idx}",
                        'text_type': 'string',
                        'file_path': str(file_path)
                    })
        except Exception as e:
            self.logger.error(f"CSV parsing error {file_path}: {e}")
        return entries

    def extract_from_txt(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract translatable text from TXT files (one line = one entry)."""
        entries = []
        try:
            lines = self._read_file_lines(file_path)
            for idx, line in enumerate(lines):
                line = line.strip()
                # Tighten TXT filters: require two Unicode letters after removing placeholders/tags
                import re
                cleaned = re.sub(r'(\[[^\]]+\]|\{[^}]+\})', '', line or '').strip()
                if sum(1 for ch in cleaned if ch.isalpha()) < 2:
                    continue
                raw_text = '"' + (line.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')) + '"'
                entries.append({
                    'text': line,
                    'raw_text': raw_text,
                    'line_number': idx + 1,
                    'context_line': f"txt:line{idx+1}",
                    'text_type': 'string',
                    'file_path': str(file_path)
                })
        except Exception as e:
            self.logger.error(f"TXT parsing error {file_path}: {e}")
        return entries

    def extract_translatable_text(self, file_path: Union[str, Path]) -> Set[str]:
        entries = self.extract_text_entries(file_path)
        return {entry['text'] for entry in entries}

    async def extract_translatable_text_async(self, file_path: Union[str, Path]) -> Set[str]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.extract_translatable_text, file_path)

    def extract_text_entries(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Gelişmiş extraction: Pyparsing grammar + context-aware regex ile UI/screen bloklarını ve Python _() fonksiyonlarını tam kapsar.
        Her entry'ye context_path ve text_type ekler, loglamayı artırır.
        """
        try:
            lines = self._read_file_lines(file_path)
        except Exception as exc:
            self.logger.error("Error reading %s: %s", file_path, exc)
            return []

        entries: List[Dict[str, Any]] = []
        seen_texts = set()
        # Prepare full content for token/lexer or pyparsing passes
        content = '\n'.join(lines)

        # 1. Pyparsing grammar ile ana extraction (tüm dosya)
        try:
            from src.core.pyparse_grammar import extract_with_pyparsing
            py_entries = extract_with_pyparsing(content, file_path=str(file_path))
            for entry in py_entries:
                ctx = entry.get('context_path') or []
                if isinstance(ctx, str):
                    ctx = [ctx]
                text_value = entry.get('text', '')
                # Filter out low-confidence or translation-block fragments
                if not self.is_meaningful_text(text_value):
                    continue
                # Use raw_text when available for canonical deduplication,
                # and normalize escape/newline variants so different extraction
                # passes don't produce duplicate IDs for the same literal.
                canonical = entry.get('raw_text') or text_value
                try:
                    canonical = canonical.replace('\r\n', '\n').replace('\r', '\n')
                    canonical = bytes(canonical, 'utf-8').decode('unicode_escape')
                except Exception:
                    pass
                key = (canonical, entry.get('line_number', 0), tuple(ctx))
                if key not in seen_texts:
                    # context_path ve text_type zorunlu olsun
                    entry.setdefault('context_path', ctx)
                    entry.setdefault('text_type', 'unknown')
                    entries.append(entry)
                    seen_texts.add(key)
        except Exception as e:
            self.logger.warning(f"Pyparsing ana extraction başarısız: {e}")

        # 1b. Lightweight lexer-based extraction (TokenStream iterator)
        try:
            from src.core.renpy_lexer import TokenStream
            stream = TokenStream(content, file_path=str(file_path))
            for token in stream:
                if token.type not in ("STRING", "TRIPLE_STRING"):
                    continue
                ctx = token.context_path or []
                if isinstance(ctx, str):
                    ctx = [ctx]
                text_value = token.text or ''
                if not self.is_meaningful_text(text_value):
                    continue
                canonical = token.raw_text or text_value
                try:
                    canonical = canonical.replace('\r\n', '\n').replace('\r', '\n')
                    canonical = bytes(canonical, 'utf-8').decode('unicode_escape')
                except Exception:
                    pass
                key = (canonical, token.line_number or 0, tuple(ctx))
                if key not in seen_texts:
                    entry = self._record_entry(
                        text=token.text,
                        raw_text=token.raw_text,
                        line_number=token.line_number or 0,
                        context_line=token.context_line,
                        text_type=token.text_type,
                        context_path=list(ctx),
                        file_path=str(file_path),
                    )
                    if entry:
                        entries.append(entry)
                        seen_texts.add(key)
        except Exception as e:
            self.logger.debug(f"TokenStream extraction unavailable or failed: {e}")

        # 2. Regex ile context-aware extraction (UI, screen, python _() fonksiyonları)
        current_context = []
        for idx, raw_line in enumerate(lines):
            stripped_line = raw_line.strip()
            # Context stack güncelle (screen, label, python, vb.)
            if stripped_line.startswith('screen '):
                screen_name = stripped_line.split()[1].split(':')[0]
                current_context.append(f'screen:{screen_name}')
            elif stripped_line.startswith('label '):
                label_name = stripped_line.split()[1].split(':')[0]
                current_context.append(f'label:{label_name}')
            elif stripped_line.startswith('menu'):
                current_context.append('menu')
            elif stripped_line.startswith('python') or stripped_line.startswith('init python'):
                current_context.append('python')
            elif stripped_line.endswith(':') and not (stripped_line.startswith('menu') or stripped_line.startswith('if') or stripped_line.startswith('else')):
                # Diğer bloklar (ör. window, frame, vbox, hbox)
                block_name = stripped_line.split()[0]
                current_context.append(block_name)
            # Blok sonu (indentation ile daha iyi yapılabilir)
            if not stripped_line and current_context:
                current_context.pop()
            if not stripped_line or stripped_line.startswith('#'):
                continue
            for descriptor in self.pattern_registry:
                match = descriptor['regex'].match(raw_line)
                if not match:
                    continue
                quotes = [
                    match.group(name)
                    for name in match.groupdict()
                    if name.startswith('quote') and match.group(name)
                ]
                if not quotes and 'quote' in match.groupdict():
                    quote_value = match.groupdict().get('quote')
                    if quote_value:
                        quotes = [quote_value]
                if not quotes:
                    continue
                character = ""
                char_group = descriptor.get('character_group')
                if char_group and match.groupdict().get(char_group):
                    character = match.group(char_group)
                for quote in quotes:
                    # preserve both raw and unescaped variants for exact matching and ID generation
                    # idx is current line index (idx)
                    raw, text = self._extract_string_raw_and_unescaped(quote, start_line=idx, lines=lines)
                    key = (text, idx + 1, tuple(current_context))
                    if key in seen_texts:
                        continue
                    text_type = descriptor.get('type') or self.determine_text_type(
                        text, stripped_line, current_context
                    )
                    entry = self._record_entry(
                        text=text,
                        raw_text=raw,
                        line_number=idx + 1,
                        context_line=stripped_line,
                        text_type=text_type,
                        context_path=list(current_context),
                        character=character,
                        file_path=str(file_path),
                    )
                    if entry:
                        entries.append(entry)
                        seen_texts.add(key)
                        # Log: UI/screen extraction
                        log_line = f"{file_path}:{idx+1} [{text_type}] ctx={current_context} text={text}"
                        self.logger.info(f"[ENTRY] {log_line}")
                break
        return entries

    def extract_from_json(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Extract translatable strings from a JSON file.
        """
        entries = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            def recurse(obj, path, current_key):
                if isinstance(obj, str):
                    # Tighten JSON filters and include raw_text for ID stability
                    import re
                    cleaned = re.sub(r'(\[[^\]]+\]|\{[^}]+\})', '', obj or '').strip()
                    if sum(1 for ch in cleaned if ch.isalpha()) < 2:
                        return
                    raw_text = '"' + (obj.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')) + '"'
                    entries.append({
                        'text': obj,
                        'raw_text': raw_text,
                        'line_number': 0,
                        'context_line': f"json:{path}",
                        'text_type': 'string',
                        'file_path': str(file_path)
                    })
                elif isinstance(obj, dict):
                    for k, v in obj.items():
                        recurse(v, f"{path}.{k}" if path else k, k)
                elif isinstance(obj, list):
                    for i, v in enumerate(obj):
                        recurse(v, f"{path}[{i}]", current_key)

            recurse(data, "", None)
        except Exception as e:
            self.logger.error(f"JSON parsing error {file_path}: {e}")
        return entries

    def extract_from_yaml(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Extract translatable strings from a YAML file.
        """
        entries = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            def recurse(obj, path, current_key):
                if isinstance(obj, str):
                    if self._is_meaningful_data_value(obj, current_key):
                        entries.append({
                            'text': obj,
                            'line_number': 0,
                            'context_line': f"yaml:{path}",
                            'text_type': 'string',
                            'file_path': str(file_path)
                        })
                elif isinstance(obj, dict):
                    for k, v in obj.items():
                        recurse(v, f"{path}.{k}" if path else k, k)
                elif isinstance(obj, list):
                    for i, v in enumerate(obj):
                        recurse(v, f"{path}[{i}]", current_key)

            recurse(data, "", None)
        except Exception as e:
            self.logger.error(f"YAML parsing error {file_path}: {e}")
        return entries

    def extract_from_ini(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Extract translatable strings from an INI file.
        """
        entries = []
        try:
            config = configparser.ConfigParser()
            config.read(file_path, encoding='utf-8')

            for section in config.sections():
                for key, value in config.items(section):
                    if self._is_meaningful_data_value(value, key):
                        entries.append({
                            'text': value,
                            'line_number': 0,
                            'context_line': f"ini:[{section}]{key}",
                            'text_type': 'string',
                            'file_path': str(file_path)
                        })
        except Exception as e:
            self.logger.error(f"INI parsing error {file_path}: {e}")
        return entries

    def extract_from_xml(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Extract translatable strings from an XML file.
        """
        entries = []
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            def recurse_xml(node, path):
                # Check text content inside the tag
                if node.text and self._is_meaningful_data_value(node.text, node.tag):
                    entries.append({
                        'text': node.text,
                        'line_number': 0,
                        'context_line': f"xml:{path}",
                        'text_type': 'string',
                        'file_path': str(file_path)
                    })

                # Check tail text (text after the tag but before the next tag)
                if node.tail and self._is_meaningful_data_value(node.tail, node.tag):
                    entries.append({
                        'text': node.tail,
                        'line_number': 0,
                        'context_line': f"xml:{path}_tail",
                        'text_type': 'string',
                        'file_path': str(file_path)
                    })

                for child in node:
                    recurse_xml(child, f"{path}/{child.tag}")

            recurse_xml(root, root.tag)
        except Exception as e:
            self.logger.error(f"XML parsing error {file_path}: {e}")
        return entries

    def parse_directory(self, directory: Union[str, Path], include_deep_scan: bool = True, recursive: bool = True) -> Dict[Path, List[Dict[str, Any]]]:
        """
        Parse a directory for translatable strings, including .rpy, .json, .yaml, .xml, and .ini files.
        """
        directory = Path(directory)
        search_root = self._resolve_search_root(directory)
        results: Dict[Path, List[Dict[str, Any]]] = {}

        def _in_tl_folder(path: Path) -> bool:
            try:
                rel = path.relative_to(search_root)
                return str(rel).replace('\\', '/').lower().startswith('tl/')
            except Exception:
                return False

        # Existing logic for .rpy and .rpym files (skip tl/)
        rpy_files = list(search_root.glob("**/*.rpy")) + list(search_root.glob("**/*.rpym"))
        for file_path in rpy_files:
            if not _in_tl_folder(file_path):
                results[file_path] = self.extract_text_entries(file_path)

        # Logic for .json files
        json_files = [f for f in search_root.glob("**/*.json") if not _in_tl_folder(f)]
        for file_path in json_files:
            results[file_path] = self.extract_from_json(file_path)

        # Logic for .csv files
        csv_files = [f for f in search_root.glob("**/*.csv") if not _in_tl_folder(f)]
        for file_path in csv_files:
            results[file_path] = self.extract_from_csv(file_path)

        # Logic for .txt files
        txt_files = [f for f in search_root.glob("**/*.txt") if not _in_tl_folder(f)]
        for file_path in txt_files:
            results[file_path] = self.extract_from_txt(file_path)

        # Logic for .yaml files
        try:
            yaml_files = [f for f in search_root.glob("**/*.yaml") if not _in_tl_folder(f)]
            for file_path in yaml_files:
                results[file_path] = self.extract_from_yaml(file_path)
        except ImportError:
            self.logger.warning("PyYAML not available. Skipping .yaml files.")

        # Logic for .xml files
        xml_files = [f for f in search_root.glob("**/*.xml") if not _in_tl_folder(f)]
        for file_path in xml_files:
            results[file_path] = self.extract_from_xml(file_path)

        # Logic for .ini files
        ini_files = [f for f in search_root.glob("**/*.ini") if not _in_tl_folder(f)]
        for file_path in ini_files:
            results[file_path] = self.extract_from_ini(file_path)

        return results

    async def extract_from_directory_async(
        self,
        directory: Union[str, Path],
        recursive: bool = True,
        max_workers: int = 4,
    ) -> Dict[Path, Set[str]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.extract_from_directory_parallel(
                directory,
                recursive=recursive,
                max_workers=max_workers,
            ),
        )

    def extract_from_directory_parallel(
        self,
        directory: Union[str, Path],
        recursive: bool = True,
        max_workers: int = 4,
    ):
        directory = Path(directory)
        search_root = self._resolve_search_root(directory)
        results: Dict[Path, Set[str]] = {}
        if recursive:
            iterator = search_root.glob("**/*.rpy")
        else:
            iterator = search_root.glob("*.rpy")
        rpy_files = [f for f in iterator if not self._is_excluded_rpy(f, search_root)]

        self.logger.info(
            "Found %s .rpy files for parallel processing (excluding Ren'Py engine & tl folders)",
            len(rpy_files),
        )

        for rpy_file in rpy_files:
            try:
                results[rpy_file] = self.extract_translatable_text(rpy_file)
            except Exception as exc:
                self.logger.error("Error processing file %s: %s", rpy_file, exc)
                results[rpy_file] = set()

        total_texts = sum(len(texts) for texts in results.values())
        self.logger.info(
            "Parallel processing completed: %s files, %s total texts",
            len(results),
            total_texts,
        )
        return results

    def extract_from_directory(self, directory: Union[str, Path], recursive: bool = True) -> Dict[Path, Set[str]]:
        """
        Sequential directory extraction for backwards compatibility with tests.
        """
        directory = Path(directory)
        search_root = self._resolve_search_root(directory)
        results: Dict[Path, Set[str]] = {}
        if recursive:
            iterator = search_root.glob("**/*.rpy")
        else:
            iterator = search_root.glob("*.rpy")
        rpy_files = [f for f in iterator if not self._is_excluded_rpy(f, search_root)]

        for rpy_file in rpy_files:
            try:
                results[rpy_file] = self.extract_translatable_text(rpy_file)
            except Exception as exc:
                self.logger.error("Error processing file %s: %s", rpy_file, exc)
                results[rpy_file] = set()

        return results

    def _resolve_search_root(self, directory: Path) -> Path:
        """
        DEĞİŞİKLİK: Kullanıcı bir klasör seçtiyse, Ren'Py standartlarına uymasa bile
        o klasördeki TÜM dosyaları taramalıyız. 'game' klasörüne zorlamak,
        standart dışı paketlenmiş oyunlarda veri kaybına neden oluyor.
        """
        # Eski mantığı devre dışı bırakıyoruz veya sadece 'game' klasörü 
        # seçilen dizinin içindeyse ve kullanıcı KÖK dizini seçtiyse uyarı veriyoruz.
        
        # Güvenli yaklaşım: Olduğu gibi bırak, recursive tarama zaten game'i de bulur.
        return directory

    def _is_excluded_rpy(self, file_path: Path, search_root: Path) -> bool:
        """
        Determines if an .rpy file should be excluded from processing.

        Args:
            file_path: The path of the file to check.
            search_root: The root directory of the search.

        Returns:
            True if the file should be excluded, False otherwise.
        """
        # Normalize path to lowercase with forward slashes
        relative_path = str(file_path.relative_to(search_root)).replace('\\', '/').lower()

        # CRITICAL: Always allow renpy/common (00layout.rpy, etc.)
        if 'renpy/common' in relative_path:
            return False

        # Exclude engine-level renpy only when it's at the root of the search
        # but allow project-copied renpy modules under subfolders like src/renpy/
        if relative_path.startswith('renpy/'):
            return True

        return False

    def _read_file_lines(self, file_path: Union[str, Path]) -> List[str]:
        text = read_text_safely(Path(file_path))
        if text is None:
            raise IOError(f"Cannot read file: {file_path}")
        return text.splitlines()

    def _calculate_indent(self, line: str) -> int:
        expanded = line.replace('\t', '    ')
        return len(expanded) - len(expanded.lstrip(' '))

    def _pop_contexts(self, stack: List[ContextNode], current_indent: int) -> None:
        while stack and current_indent <= stack[-1].indent:
            stack.pop()

    def _detect_new_context(self, stripped_line: str, indent: int) -> Optional[ContextNode]:
        # Check for hidden labels first - these should be skipped for translation
        if self.hidden_label_re.match(stripped_line):
            return ContextNode(indent=indent, kind='hidden_label', name='hidden')
        
        label_match = self.label_def_re.match(stripped_line)
        if label_match:
            return ContextNode(indent=indent, kind='label', name=label_match.group(1))

        menu_match = self.menu_def_re.match(stripped_line)
        if menu_match:
            # ... (menu context logic, if any) ...
            pass

        screen_match = self.screen_def_re.match(stripped_line)
        if screen_match:
            return ContextNode(indent=indent, kind='screen', name=screen_match.group(1))
        if self.python_block_re.match(stripped_line):
            return ContextNode(indent=indent, kind='python')

        return None

    def _context_label(self, node: ContextNode) -> str:
        return f"{node.kind}:{node.name}" if node.name else node.kind

    def _build_context_path(
        self, stack: List[ContextNode], pending: Optional[ContextNode] = None
    ) -> List[str]:
        path = [self._context_label(node) for node in stack]
        if pending:
            path.append(self._context_label(pending))
        return path

    def _handle_multiline_start(
        self,
        lines: List[str],
        index: int,
        raw_line: str,
        stripped_line: str,
        context_path: List[str],
        file_path: str = '',
    ) -> Tuple[Optional[Dict[str, Any]], int]:
        for descriptor in self.multiline_registry:
            match = descriptor['regex'].match(raw_line)
            if not match:
                continue

            delimiter = match.group('delim')
            body = match.groupdict().get('body') or ''
            
            # Special handling for _p() - need to consume until closing ) 
            is_p_function = descriptor.get('type') == 'paragraph'
            text, end_index = self._consume_multiline(
                lines, index, delimiter, body, 
                is_p_function=is_p_function
            )

            character = ''
            char_group = descriptor.get('character_group')
            if char_group and match.groupdict().get(char_group):
                character = match.group(char_group)

            entry = self._record_entry(
                text=text,
                line_number=index + 1,
                context_line=stripped_line,
                text_type=descriptor.get('type', 'dialogue'),
                context_path=context_path,
                character=character,
                file_path=file_path,
                raw_text='\n'.join(lines[index:end_index+1]) if end_index >= index else None,
            )
            return entry, end_index

        return None, index

    def _consume_multiline(
        self,
        lines: List[str],
        start_index: int,
        delimiter: str,
        initial_body: str,
        is_p_function: bool = False,
    ) -> Tuple[str, int]:
        buffer: List[str] = []
        remainder = initial_body or ''
        closing_inline = remainder.find(delimiter)
        if closing_inline != -1:
            content = remainder[:closing_inline]
            if is_p_function:
                # For _p(), process the text to normalize whitespace
                content = self._process_p_function_text(content)
            buffer.append(content)
            return "\n".join(buffer).strip('\n'), start_index

        if remainder:
            buffer.append(remainder)

        index = start_index + 1
        while index < len(lines):
            current = lines[index]
            closing_pos = current.find(delimiter)
            if closing_pos != -1:
                buffer.append(current[:closing_pos])
                # Don't include tail for _p() function text
                if not is_p_function:
                    tail = current[closing_pos + len(delimiter) :].strip()
                    # Remove trailing ) for _p() functions  
                    if tail and not tail.startswith(')'):
                        buffer.append(tail)
                
                result_text = "\n".join(buffer).strip('\n')
                if is_p_function:
                    result_text = self._process_p_function_text(result_text)
                return result_text, index

            buffer.append(current)
            index += 1

        result_text = "\n".join(buffer).strip('\n')
        if is_p_function:
            result_text = self._process_p_function_text(result_text)
        return result_text, len(lines) - 1
    
    def _process_p_function_text(self, text: str) -> str:
        """
        Process _p() function text the same way Ren'Py does:
        - Remove leading/trailing whitespace from each line
        - Collapse consecutive non-blank lines into one line (with space)
        - Blank lines become paragraph separators (double newline)
        """
        if not text:
            return ""
        
        lines = text.split('\n')
        paragraphs = []
        current_paragraph = []
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                # Blank line = paragraph separator
                if current_paragraph:
                    paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []
            else:
                current_paragraph.append(stripped)
        
        # Don't forget the last paragraph
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))
        
        # Join paragraphs with double newline (Ren'Py format)
        return '\n\n'.join(paragraphs)

    def _record_entry(
        self,
        text: str,
        line_number: int,
        context_line: str,
        text_type: str,
        context_path: List[str],
        character: str = '',
        file_path: str = '',
        raw_text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        if not self.is_meaningful_text(text):
            return None
        
        # Skip text inside hidden labels (label xxx hide:)
        if self._is_hidden_context(context_path):
            return None

        processed_text, placeholder_map = self.preserve_placeholders(text)

        resolved_type = text_type or self.determine_text_type(
            text,
            context_line,
            context_path,
        )
        if self._is_python_context(context_path):
            resolved_type = 'renpy_func'

        # Apply user-configurable type filters (e.g. translate_ui)
        if not self._should_translate_text(text, resolved_type):
            return None

        # context_tag is handled by callers (e.g., deep scan) via context_path
        return {
            'text': text,
            'raw_text': raw_text if raw_text is not None else None,
            'line_number': line_number,
            'context_line': context_line,
            'character': character,
            'text_type': resolved_type,
            'context_path': list(context_path),
            'processed_text': processed_text,
            'placeholder_map': placeholder_map,
            'file_path': file_path,
        }

    def _is_python_context(self, context_path: List[str]) -> bool:
        for ctx in context_path or []:
            ctx_lower = (ctx or '').lower()
            if ctx_lower.startswith('python'):
                return True
        return False
    
    def _is_hidden_context(self, context_path: List[str]) -> bool:
        """Check if we're inside a hidden label (should not be translated)"""
        for ctx in context_path or []:
            ctx_lower = (ctx or '').lower()
            if ctx_lower.startswith('hidden_label'):
                return True
        return False

    def _extract_string_content(self, quoted_string: str) -> str:
        if not quoted_string:
            return ''
        import re
        # Match optional prefixes (r, u, b, f, fr, rf, etc.) and quoted content
        m = re.match(r"^(?P<prefix>[rRuUbBfF]{,2})?(?P<quoted>\"\"\"[\s\S]*?\"\"\"|\'\'\'[\s\S]*?\'\'\'|\"(?:[^\"\\]|\\.)*\"|\'(?:[^'\\]|\\.)*\')$", quoted_string, flags=re.S)
        if m:
            content_raw = m.group('quoted')
            # Remove quotes
            if content_raw.startswith('"""') and content_raw.endswith('"""'):
                content = content_raw[3:-3]
            elif content_raw.startswith("'''") and content_raw.endswith("'''"):
                content = content_raw[3:-3]
            elif content_raw.startswith('"') and content_raw.endswith('"'):
                content = content_raw[1:-1]
            elif content_raw.startswith("'") and content_raw.endswith("'"):
                content = content_raw[1:-1]
            else:
                content = content_raw
        else:
            content = quoted_string
        content = content.replace('\\"', '"').replace("\\'", "'")
        content = content.replace('\\n', '\n').replace('\\t', '\t')
        return content

    def _extract_string_raw_and_unescaped(self, quoted_string: str, start_line: int = None, lines: List[str] = None) -> Tuple[str, str]:
        """
        Return both the raw literal (as in source, preserving escape sequences and quoting)
        and the unescaped content (normalized) used for IDs and matching.

        If `lines` and `start_line` are provided and the quoted string spans multiple
        lines (triple-quoted), this will capture the exact original lines slice for raw.
        """
        raw = quoted_string or ''
        # Attempt to capture multi-line raw from source lines if provided
        if lines is not None and start_line is not None:
            try:
                # start_line is 0-based index
                # Find the line that contains the opening quote
                for i in range(start_line, min(start_line + 1, len(lines))):
                    if quoted_string.strip().startswith(('"""', "'''")):
                        # For triple-quoted, try to find end by scanning forward
                        delim = quoted_string.strip()[:3]
                        # naive approach: join until we find closing delim
                        j = i
                        buf = []
                        while j < len(lines):
                            buf.append(lines[j])
                            if delim in lines[j] and j != i:
                                break
                            j += 1
                        raw = '\n'.join(buf)
                        break
            except Exception:
                raw = quoted_string

        # Use existing extractor to get unescaped
        unescaped = self._extract_string_content(quoted_string)
        return raw, unescaped

    def is_meaningful_text(self, text: str) -> bool:
        if not text or len(text.strip()) < 2:
            return False

        text_lower = text.lower().strip()
        text_strip = text.strip()
        # Skip generated translation/TL snippets or fragments from .tl/.rpy translation blocks
        # e.g. lines starting with 'translate <lang>' or containing 'old'/'new' markers
        if '\n' in text:
            first_line = text.strip().splitlines()[0].lower()
            if first_line.startswith('translate '):
                return False
            tl_lower = text.lower()
            if 'translate ' in tl_lower or 'generated by renlocalizer' in tl_lower:
                return False
            if re.search(r'(^|\n)\s*(old|new)\b', tl_lower):
                return False
        # Skip very short fragments that are only 'old'/'new' markers
        if re.fullmatch(r"\s*(old|new)\s*", text_lower):
            return False
        
        if text_lower in self.renpy_technical_terms:
            return False

        if re.fullmatch(r"\s*(\[[^\]]+\]|\{[^}]+\}|%s|%\([^)]+\)[sdif])\s*", text):
            return False
        
        # Skip Python format strings like {:,}, {:3d}, {}, {}Attitude:{} {}, etc.
        # These are used for number/string formatting and should not be translated
        if '{' in text_strip:
            # Count format placeholders
            format_count = len(re.findall(r'\{[^}]*\}', text_strip))
            if format_count >= 1:
                # Remove format placeholders and check remaining content
                remaining = re.sub(r'\{[^}]*\}', '', text_strip).strip()
                # If remaining has no meaningful words (at least 3 consecutive letters), skip
                if not any(ch.isalpha() for ch in remaining) or not re.search(r'.{3,}', remaining):
                    return False
                # If format placeholders dominate the string (2+ placeholders with short remaining), skip
                if format_count >= 2 and len(remaining) < 10:
                    return False

        technical_patterns = [
            r'^#[0-9a-fA-F]+$',
            r'\.ttf$',
            r'^%s[%\s]*$',
            r'fps|renderer|ms$',
            r'^[0-9.]+$',
            r'game_menu|sync|input|overlay',
            r'vertical|horizontal|linear',
            r'touch_keyboard|subtitle|empty',
        ]
        for pattern in technical_patterns:
            if re.search(pattern, text_lower):
                return False

        if any(ext in text_lower for ext in ['.png', '.jpg', '.mp3', '.ogg']):
            return False

        if re.match(r'^[-+]?\d+$', text.strip()):
            return False
        if re.match(r'^\d+(?:\.\d+)+$', text.strip()):
            return True

        # Büyük harfle başlayan ve boşluk içeren metinleri kontrol et
        if text[0].isupper() and ' ' in text:
            return True  # %99 metindir

        # Küçük harf ve boşluksuz metinleri düşük güven olarak işaretle
        if text.islower() and ' ' not in text:
            return False

        # FIX: Reject strings that are actually code wrappers captured by mistake
        # e.g. '_("Text")' or "_('Text')"
        if (text.startswith('_("') and text.endswith('")')) or \
           (text.startswith("_('") and text.endswith("')")):
            return False

        # Reject obvious function calls or code-like literals captured as strings
        # e.g. some_func(arg), module.attr, key: value
        if re.match(r'^[A-Za-z_]\w*\s*\(.*\)$', text_strip):
            return False
        if re.match(r'^[A-Za-z_]\w*\.[A-Za-z_]\w*$', text_strip):
            return False
        if re.match(r'^[A-Za-z0-9_\-]+\s*:\s*[A-Za-z0-9_\-]+$', text_strip):
            return False

        # Remove placeholders/tags like [who.name] or {color=...} and check remaining content
        try:
            cleaned = re.sub(r'(\[[^\]]+\]|\{[^}]+\})', '', text_strip).strip()
            alpha_count = sum(1 for ch in cleaned if ch.isalpha())
            if alpha_count < 2:
                return False
        except Exception:
            pass

        return any(ch.isalpha() for ch in text) and len(text.strip()) >= 2

    def determine_text_type(
        self,
        text: str,
        context_line: str = '',
        context_path: Optional[List[str]] = None,
    ) -> str:
        if context_path:
            lowered = [ctx.lower() for ctx in context_path]
            if any(ctx.startswith('menu') for ctx in lowered):
                return 'menu'
            if any(ctx.startswith('screen') for ctx in lowered):
                return 'ui'
            if any(ctx.startswith('python') for ctx in lowered):
                return 'renpy_func'
            if any(ctx.startswith('label') for ctx in lowered):
                return 'dialogue'

        if context_line:
            lowered_line = context_line.lower()
            # Check for _p() function first (paragraph text)
            if '_p(' in lowered_line:
                return 'paragraph'
            # NEW: Check for action/function patterns
            if 'notify(' in lowered_line:
                return 'notify'
            if 'confirm(' in lowered_line:
                return 'confirm'
            if 'alt ' in lowered_line or 'alt=' in lowered_line:
                return 'alt_text'
            if 'input' in lowered_line and ('default' in lowered_line or 'prefix' in lowered_line or 'suffix' in lowered_line):
                return 'input'
            if 'textbutton' in lowered_line:
                return 'button'
            if 'menu' in lowered_line:
                return 'menu'
            if 'screen' in lowered_line:
                return 'ui'
            if 'config.' in lowered_line:
                return 'config'
            if 'gui.' in lowered_line:
                return 'gui'
            if 'style.' in lowered_line:
                return 'style'
            if 'renpy.' in lowered_line or ' notify(' in lowered_line or ' input(' in lowered_line:
                return 'renpy_func'
            # NVL mode check - nvl character prefix
            if 'nvl' in lowered_line:
                return 'dialogue'  # NVL dialogue is still dialogue

        return 'dialogue'

    def classify_text_type(self, line: str) -> str:
        """
        Satırın menü, ekran, karakter, teknik veya genel metin olup olmadığını hassas şekilde belirler.
        """
        if self.menu_def_re.match(line) or self.menu_choice_re.match(line) or self.menu_title_re.match(line):
            return "menu"
        if self.screen_def_re.match(line) or self.screen_text_re.match(line) or self.screen_multiline_re.match(line):
            return "screen"
        if self.char_dialog_re.match(line) or self.char_multiline_re.match(line):
            return "character"
        if self.technical_line_re.match(line) or self.numeric_or_path_re.match(line):
            return "technical"
        return "general"

    def quality_check(self, text: str) -> Dict[str, bool]:
        """
        Basit kalite kontrolü: anlamlılık, basit dilbilgisi işareti ve teknik uygunluk.
        """
        res = {'is_meaningful': False, 'has_grammar_error': False, 'is_technically_valid': True}
        if text and len(text.strip()) > 2 and not self.technical_line_re.match(text) and not self.numeric_or_path_re.match(text):
            res['is_meaningful'] = True
        # Basit grammar: ilk harf büyük ve noktalama içeriyorsa kabul et
        if text and (text[0].isupper() and any(p in text for p in ('.', '!', '?'))):
            res['has_grammar_error'] = False
        else:
            res['has_grammar_error'] = True
        if self.technical_line_re.match(text) or self.numeric_or_path_re.match(text):
            res['is_technically_valid'] = False
        return res

    def _should_translate_text(self, text: str, text_type: str) -> bool:
        if self.config is None:
            return True
        
        text_strip = text.strip()
        text_lower = text_strip.lower()
        
        # =================================================================
        # CRITICAL: Skip technical content that should NEVER be translated
        # These checks run BEFORE user settings to prevent breaking games
        # =================================================================
        
        # Skip empty or whitespace-only text
        if not text_strip:
            return False
        
        # Skip file paths and file names (fonts, images, audio, etc.)
        file_extensions = (
            '.otf', '.ttf', '.woff', '.woff2', '.eot',  # Fonts
            '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.ico', '.svg',  # Images
            '.mp3', '.ogg', '.wav', '.flac', '.aac', '.m4a', '.opus',  # Audio
            '.mp4', '.webm', '.avi', '.mkv', '.mov', '.ogv',  # Video
            '.rpy', '.rpyc', '.rpa', '.rpym', '.rpymc',  # Ren'Py files
            '.py', '.pyc', '.pyo',  # Python files
            '.json', '.txt', '.xml', '.csv', '.yaml', '.yml',  # Data files
            '.zip', '.rar', '.7z', '.tar', '.gz',  # Archives
        )
        if any(text_lower.endswith(ext) for ext in file_extensions):
            return False
        
        # Skip if text starts with common file path patterns
        if text_strip.startswith(('fonts/', 'images/', 'audio/', 'music/', 'sounds/', 
                                   'gui/', 'screens/', 'script/', 'game/', 'tl/')):
            return False
        
        # Skip paths with slashes that look like file paths (no spaces)
        if '/' in text_strip and ' ' not in text_strip:
            if re.match(r'^[a-zA-Z0-9_/.\-]+$', text_strip):
                return False
        
        # Skip backslash paths (Windows style)
        if '\\' in text_strip and ' ' not in text_strip:
            if re.match(r'^[a-zA-Z0-9_\\\.\-]+$', text_strip):
                return False
        
        # Skip URLs and URIs
        if re.match(r'^(https?://|ftp://|mailto:|file://|www\.)', text_lower):
            return False
        
        # Skip hex color codes
        if re.match(r'^#[0-9a-fA-F]{3,8}$', text_strip):
            return False
        
        # Skip pure numbers (including floats and negative)
        if re.match(r'^-?\d+\.?\d*$', text_strip):
            return False
        
        # Skip CSS/style-like values
        if re.match(r'^\d+(\.\d+)?(px|em|rem|%|pt|vh|vw)$', text_lower):
            return False
        
        # Skip Ren'Py screen/style element names (technical identifiers)
        # IMPORTANT: Only skip lowercase versions - "history" is technical, "History" is UI text
        renpy_technical_terms_lowercase = {
            # Screen elements & style identifiers (always lowercase in code)
            'say', 'window', 'namebox', 'choice', 'quick', 'navigation',
            'return_button', 'page_label', 'page_label_text', 'slot',
            'slot_time_text', 'slot_name_text', 'save_delete', 'pref',
            'radio', 'check', 'slider', 'tooltip_icon', 'tooltip_frame',
            'dismiss', 'history_name', 'color',  # Note: removed 'history', 'help' - these are valid UI labels
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
            # Common variable/config names (shouldn't be translated)
            'id', 'name', 'type', 'style', 'action', 'hovered', 'unhovered',
            'selected', 'insensitive', 'activate', 'alternate',
        }
        # Only skip if text is EXACTLY lowercase (technical) - not Title Case UI text
        # "history" -> skip, "History" -> translate
        if text_strip in renpy_technical_terms_lowercase:
            return False
        
        # Skip snake_case identifiers (like page_label_text, slot_time_text)
        if re.match(r'^[a-z][a-z0-9]*(_[a-z0-9]+)+$', text_strip):
            return False
        
        # Skip SCREAMING_SNAKE_CASE constants
        if re.match(r'^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$', text_strip):
            return False
        
        # Skip camelCase identifiers (likely variable names)
        if re.match(r'^[a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*$', text_strip) and ' ' not in text_strip:
            return False
        
        # Skip save/game identifiers like "GameName-1234567890"
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*-\d+$', text_strip):
            return False
        
        # Skip version strings like "v1.0.0" or "1.2.3"
        if re.match(r'^v?\d+\.\d+(\.\d+)?([a-z])?$', text_lower):
            return False
        
        # Skip single character strings (often used as separators or bullets)
        if len(text_strip) == 1 and not text_strip.isalpha():
            return False
        
        # Skip if it's just Ren'Py tags/variables with no actual text
        # e.g., "{font=something}[variable]{/font}" with no human-readable text
        stripped_of_tags = re.sub(r'\{[^}]*\}', '', text_strip)  # Remove tags
        stripped_of_vars = re.sub(r'\[[^\]]*\]', '', stripped_of_tags)  # Remove variables
        if not stripped_of_vars.strip():
            return False

        # =================================================================
        # User-configurable text type filters
        # =================================================================
        ts = self.config.translation_settings
        if text_type == 'dialogue' and not ts.translate_dialogue:
            return False
        if text_type == 'menu' and not ts.translate_menu:
            return False
        if text_type == 'ui' and not ts.translate_ui:
            return False
        if text_type == 'button' and not getattr(ts, 'translate_buttons', ts.translate_ui):
            return False
        if text_type == 'config' and not ts.translate_config_strings:
            return False
        if text_type == 'gui' and not ts.translate_gui_strings:
            return False
        if text_type == 'style' and not ts.translate_style_strings:
            return False
        if text_type == 'renpy_func' and not ts.translate_renpy_functions:
            return False
        # NEW text types
        if text_type == 'alt_text' and not getattr(ts, 'translate_alt_text', ts.translate_ui):
            return False
        if text_type == 'input' and not getattr(ts, 'translate_input_text', ts.translate_ui):
            return False
        if text_type == 'notify' and not getattr(ts, 'translate_notifications', ts.translate_dialogue):
            return False
        if text_type == 'confirm' and not getattr(ts, 'translate_confirmations', ts.translate_dialogue):
            return False
        if text_type == 'translatable_string':
            # _() marked strings should always be translated
            return True
        if text_type == 'define' and not getattr(ts, 'translate_define_strings', ts.translate_config_strings):
            return False
        # paragraph type always translatable (like dialogue)
        if text_type == 'paragraph':
            # Use same settings as dialogue
            if not ts.translate_dialogue:
                return False

        rules: Dict[str, Any] = getattr(self.config, 'never_translate_rules', {}) or {}

        try:
            for val in rules.get('exact', []) or []:
                if text_strip == val:
                    return False
            for val in rules.get('contains', []) or []:
                if val and val in text_strip:
                    return False
            for pattern in rules.get('regex', []) or []:
                try:
                    if re.search(pattern, text_strip):
                        return False
                except re.error:
                    continue
        except Exception as exc:
            self.logger.warning("never_translate rules failed: %s", exc)

        # Eğer metin 'jump', 'call', 'scene', 'show' bağlamında ise ve boşluk içermiyorsa -> ÇEVİRME
        if text_type in ('renpy_func', 'python_string'):
            context_lower = self.get_context_line().lower()  # Bağlam satırını al
            if any(keyword in context_lower for keyword in ('jump', 'call', 'scene', 'show')):
                if ' ' not in text_strip and text_strip[0].isupper():
                    # Örn: "Start", "Forest", "Date" gibi kelimeler label olabilir.
                    return False

        # Eğer metin 'font' veya 'style' bağlamında ise ve boşluk içermiyorsa -> ÇEVİRME
        if text_type in ('config', 'gui', 'style'):
            context_lower = self.get_context_line().lower()  # Bağlam satırını al
            if any(keyword in context_lower for keyword in ('font', 'style')):
                if ' ' not in text_strip:
                    # Örn: "Roboto-Regular", "GuiFont" gibi isimler çevrilmemeli.
                    return False

        return True

    def preserve_placeholders(self, text: str):
        """
        Replace Ren'Py variables, tags, and format strings with stable Unicode markers.
        Uses ⟦0000⟧ format which translation engines won't modify.
        
        Handles:
        - [variable] - Ren'Py variable interpolation
        - [var!t] - Translatable variable (special flag)
        - {tag} - Ren'Py text tags (color, bold, etc.)
        - {#identifier} - Disambiguation tags (MUST be preserved)
        - %(var)s, %s - Python format strings
        """
        if not text:
            return text, {}

        placeholder_map: Dict[str, str] = {}
        processed_text = text
        placeholder_counter = 0

        # CRITICAL: Preserve disambiguation tags {#...} FIRST
        # These are used to distinguish identical strings in different contexts
        # e.g., "New", "New{#project}", "New{#game}" are all different in Ren'Py
        disambiguation_pattern = r'\{#[^}]+\}'
        for match in re.finditer(disambiguation_pattern, text):
            placeholder_id = f"⟦D{placeholder_counter:03d}⟧"  # D for disambiguation
            placeholder_map[placeholder_id] = match.group(0)
            processed_text = processed_text.replace(match.group(0), placeholder_id, 1)
            placeholder_counter += 1

        # RenPy variable placeholders like [variable_name] or [var!t] (translatable)
        # The !t flag marks a variable as translatable - these are SPECIAL
        # [mood!t] - the value in 'mood' will be translated at display time
        # We need to preserve the whole placeholder but NOT translate the variable name
        renpy_var_pattern = r'\[([^\]]+)\]'
        for match in re.finditer(renpy_var_pattern, processed_text):
            if match.group(0).startswith('⟦'):  # Already processed
                continue
            
            var_content = match.group(1)
            
            # Check for !t flag (translatable variable)
            # The variable VALUE will be translated by Ren'Py at runtime
            if '!t' in var_content:
                # Mark as translatable variable placeholder (still preserve it)
                placeholder_id = f"⟦VT{placeholder_counter:03d}⟧"  # VT for translatable variable
            else:
                placeholder_id = f"⟦V{placeholder_counter:03d}⟧"  # V for regular variable
            
            placeholder_map[placeholder_id] = match.group(0)
            processed_text = processed_text.replace(match.group(0), placeholder_id, 1)
            placeholder_counter += 1

        # RenPy text tags like {color=#ff0000}, {/color}, {b}, {/b}, etc.
        # BUT NOT disambiguation tags (already handled above)
        renpy_tag_pattern = r'\{[^}]*\}'
        for match in re.finditer(renpy_tag_pattern, processed_text):
            tag = match.group(0)
            if tag.startswith('⟦') or tag.startswith('{#'):  # Already processed or disambiguation
                continue
            placeholder_id = f"⟦T{placeholder_counter:03d}⟧"  # T for tag
            placeholder_map[placeholder_id] = tag
            processed_text = processed_text.replace(tag, placeholder_id, 1)
            placeholder_counter += 1

        # Python-style format strings like %(variable)s, %s, %d, etc.
        python_format_pattern = r'%\([^)]+\)[sdif]|%[sdif]'
        for match in re.finditer(python_format_pattern, processed_text):
            placeholder_id = f"⟦F{placeholder_counter:03d}⟧"  # F for format
            placeholder_map[placeholder_id] = match.group(0)
            processed_text = processed_text.replace(match.group(0), placeholder_id, 1)
            placeholder_counter += 1

        return processed_text, placeholder_map

    # Restore placeholders in translated text.
    # Uses Unicode bracket markers ⟦0000⟧ which are more resistant to translation corruption.
    def restore_placeholders(self, translated_text: str, placeholder_map: dict) -> str:
        """
        Restore placeholders in translated text.
        Uses Unicode bracket markers ⟦0000⟧ which are more resistant to translation corruption.
        """
        if not translated_text or not placeholder_map:
            return translated_text
        
        restored_text = translated_text
        
        # First try exact match - this handles most cases with Unicode markers
        for placeholder_id, original_placeholder in placeholder_map.items():
            restored_text = restored_text.replace(placeholder_id, original_placeholder)
        
        # Handle potential space insertions around Unicode markers
        for placeholder_id, original_placeholder in placeholder_map.items():
            if placeholder_id.startswith('⟦') and placeholder_id.endswith('⟧'):
                # Extract number part
                number_part = placeholder_id[1:-1]  # Get "0000" part
                
                # Try with spaces around the marker
                space_patterns = [
                    f"⟦ {number_part} ⟧",  # Spaces inside brackets
                    f"⟦ {number_part}⟧",    # Space after opening
                    f"⟦{number_part} ⟧",    # Space before closing
                    f" {placeholder_id} ",   # Spaces around
                    f" {placeholder_id}",    # Space before
                    f"{placeholder_id} ",    # Space after
                ]
                
                for pattern in space_patterns:
                    if pattern in restored_text:
                        restored_text = restored_text.replace(pattern, original_placeholder)
                
                # Regex fallback for Unicode markers with potential corruption
                import re
                unicode_patterns = [
                    r'⟦\s*' + re.escape(number_part) + r'\s*⟧',  # Flexible whitespace
                    r'\[\s*' + re.escape(number_part) + r'\s*\]',  # Similar brackets
                    r'【\s*' + re.escape(number_part) + r'\s*】',  # CJK brackets
                ]
                
                for pattern in unicode_patterns:
                    restored_text = re.sub(pattern, original_placeholder, restored_text)
        
        return restored_text

    def validate_placeholders(self, text: str, placeholder_map: dict) -> bool:
        """
        Validate that placeholders in the translated text match the original placeholders.
        Ensures that variables like [player_name] are preserved.
        
        Args:
            text: The translated text to validate.
            placeholder_map: The original placeholder map from preserve_placeholders.
        
        Returns:
            True if all placeholders are valid, False otherwise.
        """
        for placeholder_id, original_placeholder in placeholder_map.items():
            if placeholder_id not in text:
                self.logger.warning(f"Missing placeholder {placeholder_id} in text: {text}")
                return False
        return True

    # ========== DEEP STRING SCANNER ==========
    # Bu modül, normal pattern'lerin yakalayamadığı gizli metinleri bulur
    # init python bloklarındaki dictionary'ler, değişken atamaları vb.
    
    # ========== NEW: AST-BASED DEEP SCAN (v2.4.1) ==========
    
    def deep_scan_strings_ast(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Python AST kullanarak derin string taraması.
        Regex'in kaçırdığı nested structure'ları yakalar.
        
        Args:
            file_path: Dosya yolu
            
        Returns:
            List of deep scan entries
        """
        import ast as python_ast
        
        try:
            lines = self._read_file_lines(file_path)
            content = '\n'.join(lines)
        except Exception as exc:
            self.logger.debug(f"AST deep scan read error: {exc}")
            return []
        
        entries: List[Dict[str, Any]] = []
        seen_texts: Set[str] = set()
        
        # Python bloklarını bul
        python_blocks = self._extract_python_blocks_for_ast(content, lines)
        
        for block_start, block_code in python_blocks:
            try:
                tree = python_ast.parse(block_code)
                
                # AST visitor ile string'leri çıkar
                def add_entry(text: str, lineno: int, text_type: str = 'deep_scan_ast'):
                    if text in seen_texts:
                        return
                    if len(text.strip()) < 3:
                        return
                    if not self.is_meaningful_text(text):
                        return
                    
                    # Filter technical strings
                    text_lower = text.lower().strip()
                    if any(ext in text_lower for ext in ['.png', '.jpg', '.mp3', '.ogg', '.rpy']):
                        return
                    if re.match(r'^[a-z_][a-z0-9_]*$', text.strip()):  # snake_case identifiers
                        return
                    if re.match(r'^#[0-9a-fA-F]{3,8}$', text.strip()):  # color codes
                        return
                    
                    processed_text, placeholder_map = self.preserve_placeholders(text)
                    
                    entries.append({
                        'text': text,
                        'line_number': block_start + lineno,
                        'context_line': lines[min(block_start + lineno - 1, len(lines) - 1)] if lines else '',
                        'text_type': text_type,
                        'context_path': ['deep_scan_ast'],
                        'processed_text': processed_text,
                        'placeholder_map': placeholder_map,
                        'is_deep_scan': True,
                        'is_ast_scan': True,
                        'file_path': str(file_path),
                    })
                    seen_texts.add(text)
                
                # Visit all nodes
                for node in python_ast.walk(tree):
                    # String constants
                    if isinstance(node, python_ast.Constant) and isinstance(node.value, str):
                        add_entry(node.value, getattr(node, 'lineno', 1))
                    
                    # f-strings (JoinedStr)
                    elif isinstance(node, python_ast.JoinedStr):
                        parts = []
                        for v in node.values:
                            if isinstance(v, python_ast.Constant) and isinstance(v.value, str):
                                parts.append(v.value)
                            elif isinstance(v, python_ast.FormattedValue):
                                # Preserve as placeholder
                                parts.append('[expr]')
                        
                        text = ''.join(str(p) for p in parts)
                        if text and '[expr]' not in text or len(text) > len('[expr]'):
                            add_entry(text, getattr(node, 'lineno', 1), 'deep_scan_fstring')
                    
                    # Call to _() or __()
                    elif isinstance(node, python_ast.Call):
                        func = node.func
                        func_name = ''
                        if isinstance(func, python_ast.Name):
                            func_name = func.id
                        elif isinstance(func, python_ast.Attribute):
                            func_name = func.attr
                        
                        if func_name in ('_', '__', 'renpy_say', 'notify'):
                            for arg in node.args:
                                if isinstance(arg, python_ast.Constant) and isinstance(arg.value, str):
                                    add_entry(arg.value, getattr(node, 'lineno', 1), 'translatable_call')
                
            except SyntaxError:
                # Invalid Python, skip this block
                pass
            except Exception as exc:
                self.logger.debug(f"AST parse error in block: {exc}")
        
        self.logger.info(f"AST deep scan found {len(entries)} strings in {file_path}")
        return entries
    
    def _extract_python_blocks_for_ast(self, content: str, lines: List[str]) -> List[Tuple[int, str]]:
        """
        Python bloklarını AST parsing için çıkar.
        
        Returns:
            List of (start_line, code_block) tuples
        """
        blocks: List[Tuple[int, str]] = []
        
        # init python ve python bloklarını bul
        python_block_re = re.compile(r'^(\s*)(?:init\s+(?:[-+]?\d+\s+)?)?python\s*(?:\w+)?:', re.MULTILINE)
        
        in_block = False
        block_start = 0
        block_indent = 0
        block_lines: List[str] = []
        
        for idx, line in enumerate(lines):
            stripped = line.lstrip()
            current_indent = len(line) - len(stripped)
            
            if not in_block:
                # Check for python block start
                if stripped.startswith('python') or 'init python' in line.lower() or stripped.startswith('$ '):
                    if stripped.startswith('$ '):
                        # Single line python
                        code = stripped[2:].strip()
                        if code:
                            blocks.append((idx, code))
                    elif ':' in stripped:
                        in_block = True
                        block_start = idx
                        block_indent = current_indent
                        block_lines = []
            else:
                # Inside python block
                if stripped and current_indent <= block_indent and not stripped.startswith('#'):
                    # Block ended
                    if block_lines:
                        code = '\n'.join(block_lines)
                        blocks.append((block_start, code))
                    in_block = False
                    block_lines = []
                elif stripped or not block_lines:  # Include empty lines inside block
                    # Remove common indentation
                    if stripped:
                        block_lines.append(line[block_indent + 4:] if len(line) > block_indent + 4 else stripped)
        
        # Handle block at end of file
        if in_block and block_lines:
            code = '\n'.join(block_lines)
            blocks.append((block_start, code))
        
        return blocks
    
    # ========== END AST-BASED DEEP SCAN ==========

    
    def deep_scan_strings(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Dosyadaki TÜM string literal'leri tarar.
        Normal pattern'lerin kaçırdığı metinleri bulmak için kullanılır.

        Özellikle şunları yakalar:
        - init python bloklarındaki dictionary value'ları
        - $ ile başlayan satırlardaki string atamaları
        - List/tuple içindeki stringler
        - Fonksiyon argümanlarındaki stringler
        - Çok satırlı triple-quoted stringler

        Returns:
            List of entries with text, line_number, context info
        """
        try:
            lines = self._read_file_lines(file_path)
        except Exception as exc:
            self.logger.error("Deep scan error reading %s: %s", file_path, exc)
            return []
        
        entries: List[Dict[str, Any]] = []
        already_found: Set[Tuple[str,str]] = set()
        
        # Normal pattern'lerle bulunanları al (bunları atlamak için)
        normal_entries = self.extract_text_entries(file_path)
        for entry in normal_entries:
            normalized = entry.get('processed_text') or entry.get('text')
            ctx = (entry.get('context_path') or ['deep_scan'])[0]
            already_found.add((normalized, ctx))
        
        # Tüm dosya içeriği (çok satırlı stringler için)
        full_content = '\n'.join(lines)
        
        # Tüm string literal'leri yakalayan regex
        # Hem tek tırnak hem çift tırnak, escape karakterlerle
        # Support optional string prefixes (r, u, b, f, fr, rf, etc.)
        string_literal_re = re.compile(
            r'''(?P<quote>(?:[rRuUbBfF]{,2})?(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'))'''
        )

        # Triple-quoted stringler için ayrı regex (çok satırlı - tüm dosyada ara)
        # Triple-quoted strings with optional prefixes
        triple_quote_re = re.compile(
            r'''(?P<triple>(?:[rRuUbBfF]{,2})?(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'))'''
        )

        # Key-value eşleştirmesi için regex
        key_capture_re = re.compile(r'(?:["\']?(\w+)["\']?\s*[:=]\s*)$')
        # Assignment detection (var = value)
        assignment_context_re = re.compile(r'([a-zA-Z_]\w*)\s*=\s*')
        # join call detection ("delimiter".join([...]) )
        join_call_re = re.compile(r'(?P<delim>"[^"]*"|\'[^\']*\')\s*\.\s*join\s*\(')

        # Önce çok satırlı triple-quoted stringleri tüm dosyada ara
        # Bu sayede birden fazla satıra yayılan stringler de yakalanır
        for match in triple_quote_re.finditer(full_content):
            # Ensure match.group exists before accessing
            if match and match.group('triple'):
                text = self._extract_triple_string_content(match.group('triple'))

            context_tag = 'deep_scan'
            # triple quoted content: try to capture key in same line
            line_number = full_content[:match.start()].count('\n') + 1
            context_line = ''
            if 0 <= line_number - 1 < len(lines):
                context_line = lines[line_number - 1].strip()
            # Key capture from context_line
            key_match = key_capture_re.search(context_line[:match.start()])
            found_key = key_match.group(1) if key_match else None
            context_tag = f'variable:{found_key}' if found_key else 'deep_scan'
            if text and (text, context_tag) not in already_found:
                # Calculate in_python status
                line_number = full_content[:match.start()].count('\n') + 1
                in_python = self._is_position_in_python_block(lines, line_number)

                # FIX: Define context_line safely
                context_line = ""
                if 0 <= line_number - 1 < len(lines):
                    context_line = lines[line_number - 1].strip()

                # Key-value eşleştirmesi yap
                key_match = key_capture_re.search(context_line[:match.start()])
                found_key = key_match.group(1) if key_match else None

                # Now pass the defined variable
                if self._is_meaningful_data_value(text, found_key):
                    # Python bloğu içinde mi kontrol et
                    in_python = self._is_position_in_python_block(lines, line_number)
                    entry = self._create_deep_scan_entry(
                        text=text,
                        line_number=line_number,
                        context_line=context_line,
                        in_python=in_python,
                        file_path=str(file_path),
                        found_key=found_key
                    )
                    if entry:
                        entries.append(entry)
                        already_found.add((text, entry.get('context_path', ['deep_scan'])[0]))
        
        # Python/init python bloğu içinde miyiz?
        in_python_block = False
        python_block_indent = 0
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Yorum satırlarını atla
            if stripped.startswith('#'):
                continue
            
            indent = self._calculate_indent(line)
            
            # Python bloğu başlangıcı
            if self.python_block_re.match(stripped):
                in_python_block = True
                python_block_indent = indent
                continue
            
            # Python bloğundan çıkış
            if in_python_block and indent <= python_block_indent and stripped:
                if not stripped.startswith('#'):
                    in_python_block = False
            
            # Normal stringler (tek satırlık)
            found_key = None
            for match in string_literal_re.finditer(line):
                text = self._extract_string_content(match.group('quote'))
                context_tag = 'deep_scan'
                # 1. Try finding context in the current line
                found_key = None
                list_context_re = re.compile(r'([a-zA-Z_]\w*)\s*(?:=\s*[\[\(\{]|\+=\s*[\[\(]|\.(?:append|extend|insert)\s*\()')
                list_match = list_context_re.search(line[:match.start()])

                # 2. Look back at previous lines if not found
                if not list_match and line_num > 1:
                    start_idx = max(0, line_num - 10)
                    prev_context = "\n".join(lines[start_idx:line_num-1]) + "\n" + line[:match.start()]
                    matches = list(list_context_re.finditer(prev_context))
                    if matches:
                        list_match = matches[-1]  # Take the closest one

                if list_match:
                    found_key = list_match.group(1)
                else:
                    # Try assignment var detection (same-line or lookback)
                    assign_match = assignment_context_re.search(line[:match.start()])
                    if not assign_match and line_num > 1:
                        prev_context = "\n".join(lines[max(0, line_num - 10):line_num-1]) + "\n" + line[:match.start()]
                        assign_matches = list(assignment_context_re.finditer(prev_context))
                        if assign_matches:
                                assign_match = assign_matches[-1]
                        if assign_match:
                            found_key = assign_match.group(1)

                    # If not found key, check for join call around the literal
                    if not found_key:
                        # Check immediate lookback for "x".join(...)
                        sb = line[:match.start()]
                        join_m = join_call_re.search(sb)
                        if join_m:
                            found_key = 'join_delim'

                    # Pass found_key to validator
                    # handle implicit string concatenation across lines: collect contiguous string literals
                    # e.g., "Hello "\n   "World" -> Hello World
                    concat_text = text
                    # look ahead for immediate next string literal contiguous with this one
                    next_pos = match.end()
                    rest = line[next_pos:]
                    # Simple detection: if a backslash at end, within parentheses, or trailing + operator then next line may continue the expression
                    rest_r = rest.rstrip()
                    continuation = rest_r.endswith('\\') or (line.strip().endswith('(') or line.strip().endswith('+')) or ('(' in line and ')' not in line)
                    if continuation:
                        # scan following lines for string literal
                        j = line_num + 1
                        while j <= len(lines):
                            next_line = lines[j-1]
                            next_match = string_literal_re.search(next_line)
                            # ensure the next line's string literal isn't part of a new assignment
                            if next_line.strip().startswith('#'):
                                break
                            if '=' in next_line.split('\n')[0] and not next_line.strip().startswith(('"', "'")):
                                break
                            if next_match:
                                next_text = self._extract_string_content(next_match.group('quote'))
                                concat_text += next_text
                                # mark with context if found
                                key_ctx = found_key or 'deep_scan'
                                already_found.add((next_text, key_ctx))
                                j += 1
                            else:
                                break

                    if self._is_meaningful_data_value(concat_text, found_key):
                        # in_python her durumda atanmalı, aksi halde UnboundLocalError oluşur
                        in_python = in_python_block
                        entry = self._create_deep_scan_entry(
                            text=concat_text,
                            line_number=line_num,
                            context_line=stripped,
                            in_python=in_python,
                            file_path=str(file_path),
                            found_key=found_key
                        )
                        if entry:
                            entries.append(entry)
                            already_found.add((text, entry.get('context_path', ['deep_scan'])[0]))
        
        self.logger.info(f"Deep scan found {len(entries)} additional strings in {file_path}")
        return entries
    
    def _is_position_in_python_block(self, lines: List[str], target_line: int) -> bool:
        """Belirtilen satırın python bloğu içinde olup olmadığını kontrol et"""
        in_python_block = False
        python_block_indent = 0
        
        for line_num, line in enumerate(lines[:target_line], 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            
            indent = self._calculate_indent(line)
            
            if self.python_block_re.match(stripped):
                in_python_block = True
                python_block_indent = indent
                continue
            
            if in_python_block and indent <= python_block_indent and stripped:
                if not stripped.startswith('#'):
                    in_python_block = False
        
        return in_python_block
    
    def _extract_triple_string_content(self, triple_quoted: str) -> str:
        """Triple-quoted string'in içeriğini çıkar"""
        if not triple_quoted:
            return ''
        
        if triple_quoted.startswith('"""') and triple_quoted.endswith('"""'):
            return triple_quoted[3:-3].strip()
        elif triple_quoted.startswith("'''") and triple_quoted.endswith("'''"):
            return triple_quoted[3:-3].strip()
        return triple_quoted.strip()
    
    def _is_deep_scan_candidate(self, text: str, in_python: bool, context_line: str) -> bool:
        """
        Determine if a string is a candidate for deep scanning.

        Args:
            text: The string to evaluate.
            in_python: Whether the string is inside a Python block.
            context_line: The line of code providing context for the string.

        Returns:
            True if the string is a candidate for deep scanning, False otherwise.
        """
        # Example logic using in_python
        if len(text) > 300 and in_python and context_line.strip().startswith('renpy.notify'):
            return True

        if not text or len(text.strip()) < 3:
            return False
        
        text_lower = text.lower().strip()
        context_lower = context_line.lower()
        
        # is_meaningful_text kontrolü (fix typo -> use is_meaningful_text)
        if not self.is_meaningful_text(text):
            return False
        
        # Dosya yolları ve teknik terimler
        if any(ext in text_lower for ext in ['.png', '.jpg', '.mp3', '.ogg', '.ttf', '.otf', '.rpy']):
            return False
        
        # Değişken isimleri gibi görünen tek kelimeler (snake_case, camelCase)
        if re.match(r'^[a-z_][a-z0-9_]*$', text.strip()):
            return False
        if re.match(r'^[a-z]+[A-Z][a-zA-Z0-9]*$', text.strip()):
            return False
        
        # Renk kodları (#ffffff)
        if re.match(r'^#[0-9a-fA-F]{3,8}$', text.strip()):
            return False
        
        # Label/screen/transform isimleri
        if 'label' in context_lower or 'jump' in context_lower or 'call' in context_lower:
            if re.match(r'^[a-z_][a-z0-9_]*$', text.strip()):
                return False
        
        # Transform ve style isimleri
        if 'transform' in context_lower or 'style' in context_lower:
            return False
        
        # Image/audio tanımları
        if 'image ' in context_lower or 'audio ' in context_lower:
            return False
        
        # register_ ve config. ayarları (teknik)
        if 'register_' in context_lower:
            return False
        
        # Sadece placeholder olan stringler
        if re.fullmatch(r'\s*(\[[^\]]+\]|\{[^}]+\})+\s*', text):
            return False
        
        # En az 1 harf ve en az 3 karakter içermeli (Unicode-aware)
        if not any(ch.isalpha() for ch in text) or len(text.strip()) < 3:
            return False
        
        # If the text is too long and in a Python block, check for docstring patterns
        if len(text) > 300 and context_line.strip().startswith('renpy.notify'):
            # If the text lacks game-specific tags, it is likely a docstring
            if '{' not in text and '[' not in text:
                return False  # Skip docstrings
        
        return True
    
    def _create_deep_scan_entry(
        self,
        text: str,
        line_number: int,
        context_line: str,
        in_python: bool,
        file_path: str = '',
        found_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Deep scan sonucu için entry oluştur"""
        
        processed_text, placeholder_map = self.preserve_placeholders(text)
        
        text_type = 'deep_scan'
        if in_python:
            text_type = 'python_string'
        context_tag = 'deep_scan'
        if found_key:
            context_tag = f'variable:{found_key}'

        return {
            'text': text,
            'line_number': line_number,
            'context_line': context_line,
            'character': '',
            'text_type': text_type,
            'context_path': [context_tag],
            'processed_text': processed_text,
            'placeholder_map': placeholder_map,
            'is_deep_scan': True,  # Marker for UI
            'file_path': file_path,
        }
    
    def extract_with_deep_scan(
        self,
        file_path: Union[str, Path],
        include_deep_scan: bool = True,
        include_ast_scan: bool = True  # NEW: v2.4.1
    ) -> List[Dict[str, Any]]:
        """
        Normal extraction + opsiyonel deep scan + AST scan.
        
        Args:
            file_path: Dosya yolu
            include_deep_scan: Regex-based deep scan sonuçlarını dahil et
            include_ast_scan: AST-based deep scan sonuçlarını dahil et (v2.4.1)
            
        Returns:
            Birleştirilmiş entry listesi
        """
        entries = self.extract_text_entries(file_path)
        seen_texts = {e.get('text', '') for e in entries}
        
        if include_deep_scan:
            deep_entries = self.deep_scan_strings(file_path)
            for entry in deep_entries:
                if entry.get('text') not in seen_texts:
                    entries.append(entry)
                    seen_texts.add(entry.get('text'))
        
        # NEW v2.4.1: AST-based deep scan
        if include_ast_scan:
            try:
                ast_entries = self.deep_scan_strings_ast(file_path)
                for entry in ast_entries:
                    if entry.get('text') not in seen_texts:
                        entries.append(entry)
                        seen_texts.add(entry.get('text'))
            except Exception as exc:
                self.logger.debug(f"AST scan failed for {file_path}: {exc}")
        
        return entries
    
    def extract_from_directory_with_deep_scan(
        self,
        directory: Union[str, Path],
        include_deep_scan: bool = True,
        recursive: bool = True
    ) -> Dict[Path, List[Dict[str, Any]]]:
        """
        Klasördeki tüm dosyaları deep scan ile tara.
        
        Args:
            directory: Klasör yolu
            include_deep_scan: Deep scan dahil et
            recursive: Alt klasörleri de tara
            
        Returns:
            {dosya_yolu: [entry listesi]} dictionary
        """
        directory = Path(directory)
        search_root = self._resolve_search_root(directory)
        results: Dict[Path, List[Dict[str, Any]]] = {}
        
        if recursive:
            iterator = search_root.glob("**/*.rpy")
        else:
            iterator = search_root.glob("*.rpy")
        
        rpy_files = [f for f in iterator if not self._is_excluded_rpy(f, search_root)]
        
        self.logger.info(
            "Deep scan: Found %s .rpy files for processing",

            len(rpy_files),
        )
        
        for rpy_file in rpy_files:
            try:
                entries = self.extract_with_deep_scan(rpy_file, include_deep_scan, include_ast_scan=include_deep_scan)
                results[rpy_file] = entries
            except Exception as exc:
                self.logger.error("Error in deep scan for %s: %s", rpy_file, exc)
                results[rpy_file] = []
        
        total_normal = sum(
            len([e for e in entries if not e.get('is_deep_scan')])
            for entries in results.values()
        )
        total_deep = sum(
            len([e for e in entries if e.get('is_deep_scan')])
            for entries in results.values()
        )
        
        self.logger.info(
            "Deep scan completed: %s files, %s normal texts, %s deep scan texts",
            len(results),
            total_normal,
            total_deep,
        )
        
        return results

    # ========== RPYC DIRECT READER ==========
    # Bu modül .rpyc dosyalarını doğrudan okuyarak AST'den metin çıkarır
    # .rpy dosyası olmasa bile çalışır
    
    def extract_from_rpyc(
        self,
        file_path: Union[str, Path]
    ) -> List[Dict[str, Any]]:
        """
        .rpyc dosyasından doğrudan metin çıkar.
        AST (Abstract Syntax Tree) okuyarak çalışır.
        
        Args:
            file_path: .rpyc dosya yolu
            
        Returns:
            Metin entry listesi
        """
        try:
            from .rpyc_reader import extract_texts_from_rpyc
            return extract_texts_from_rpyc(file_path)
        except ImportError:
            self.logger.warning("rpyc_reader module not available")
            return []
        except Exception as exc:
            self.logger.error("Error reading RPYC %s: %s", file_path, exc)
            return []
    
    def extract_from_rpyc_directory(
        self,
        directory: Union[str, Path],
        recursive: bool = True
    ) -> Dict[Path, List[Dict[str, Any]]]:
        """
        Klasördeki tüm .rpyc dosyalarından metin çıkar.
        
        Args:
            directory: Klasör yolu
            recursive: Alt klasörleri de tara
            
        Returns:
            {dosya_yolu: [entry listesi]} dictionary
        """
        try:
            from .rpyc_reader import extract_texts_from_rpyc_directory
            return extract_texts_from_rpyc_directory(directory, recursive)
        except ImportError:
            self.logger.warning("rpyc_reader module not available")
            return {}
        except Exception as exc:
            self.logger.error("Error reading RPYC directory %s: %s", directory, exc)
            return {}
    
    def extract_combined(
        self,
        directory: Union[str, Path],
        include_rpy: bool = True,
        include_rpyc: bool = False,
        include_deep_scan: bool = False,
        recursive: bool = True
    ) -> Dict[Path, List[Dict[str, Any]]]:
        """
        Hem .rpy hem .rpyc dosyalarından metin çıkar.
        En kapsamlı çıkarma yöntemi.
        
        Args:
            directory: Klasör yolu
            include_rpy: .rpy dosyalarını işle
            include_rpyc: .rpyc dosyalarını işle (AST ile)
            include_deep_scan: Deep scan uygula (.rpy için)
            recursive: Alt klasörleri de tara
            
        Returns:
            Birleştirilmiş sonuçlar
        """
        results: Dict[Path, List[Dict[str, Any]]] = {}
        all_texts: Set[str] = set()
        
        # .rpy dosyalarından çıkar
        if include_rpy:
            rpy_results = self.extract_from_directory_with_deep_scan(
                directory,
                include_deep_scan=include_deep_scan,
                recursive=recursive
            )
            for file_path, entries in rpy_results.items():
                results[file_path] = entries
                for entry in entries:
                    all_texts.add(entry.get('text', ''))
        
        # .rpyc dosyalarından çıkar (opsiyonel)
        if include_rpyc:
            try:
                rpyc_results = self.extract_from_rpyc_directory(directory, recursive)
                
                # RPYC sonuçlarını ekle (duplicate'leri atla)
                for file_path, entries in rpyc_results.items():
                    # Sadece .rpy'de bulunmayan metinleri ekle
                    new_entries = [
                        e for e in entries 
                        if e.get('text', '') not in all_texts
                    ]
                    
                    if new_entries:
                        if file_path not in results:
                            results[file_path] = []
                        results[file_path].extend(new_entries)
                        
                        # Yeni metinleri kaydet
                        for entry in new_entries:
                            all_texts.add(entry.get('text', ''))
                
                rpyc_only = sum(
                    len([e for e in entries if e.get('is_rpyc')])
                    for entries in results.values()
                )
                self.logger.info(
                    "RPYC extraction added %s unique texts not found in .rpy files",
                    rpyc_only
                )
                
            except Exception as exc:
                self.logger.warning("RPYC extraction failed: %s", exc)
        
        total = sum(len(entries) for entries in results.values())
        self.logger.info(
            "Combined extraction: %s files, %s total texts",
            len(results),
            total
        )
        
        
        return results

    def _is_meaningful_data_value(self, text: str, key: Optional[str]) -> bool:
        """
        Veri dosyaları (JSON, XML vb.) için özel filtre.
        Standart metinlerden daha esnek davranır (tek kelimelik eşya isimleri vb. için).
        """
        if not text:
            return False

        # 1. If key is provided and it's a BLACKLIST key, it's not meaningful
        if key and str(key).lower() in self.DATA_KEY_BLACKLIST:
            return False


        # If there's a key, only accept it when the key is in the whitelist
        if key:
            key_lower = str(key).lower()
            if key_lower in self.DATA_KEY_WHITELIST:
                # Accept if not a numeric or URL/file path
                if not re.match(r'^[-+]?\d+(\.\d+)?$', text.strip()) and not text.strip().startswith(('#', 'http')):
                    return True
            # If key present but not in whitelist, do not accept (smart whitelist)
            return False


        # If no key provided, use heuristics similar to is_meanful_text but allow
        # simple single-word items (e.g., 'Sword')
        if re.match(r'^[-+]?\d+(\.\d+)?$', text.strip()) or text.strip().startswith(('#', 'http')):
            return False

        if any(text.lower().endswith(ext) for ext in ['.png', '.jpg', '.mp3', '.ogg']):
            return False

        # Language-independent: strip placeholders/tags and require at least
        # two Unicode letters for data values when no key provided.
        try:
            cleaned = re.sub(r'(\[[^\]]+\]|\{[^}]+\})', '', text or '').strip()
            if sum(1 for ch in cleaned if ch.isalpha()) < 2:
                return False
        except Exception:
            # Fallback: require at least one alphabetic char
            if not any(ch.isalpha() for ch in text):
                return False

        return True



        # Extraction döngüsü içinde olmalı:
        while index < len(lines):
            raw_line = lines[index]
            stripped_line = raw_line.strip()

            # Edge-case: Teknik satırları, sadece teknik terimleri, dosya yollarını, renk kodlarını, değişken/tag satırlarını, boş veya yorum satırlarını atla
            if (
                self.technical_line_re.match(stripped_line)
                or self.numeric_or_path_re.match(stripped_line)
                or self.renpy_var_or_tag_re.match(stripped_line)
                or self.comment_or_empty_re.match(stripped_line)
            ):
                index += 1
                continue

            # Menü/choice satırlarında teknik koşulları atla
            if self.menu_technical_condition_re.match(stripped_line):
                index += 1
                continue

            # ...mevcut extraction işlemleri...
            index += 1
