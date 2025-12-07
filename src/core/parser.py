"""
Ren'Py-aware parser used by RenLocalizer.

The parser keeps track of indentation-based blocks so it can better decide
which strings should be translated and which ones belong to technical code.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import chardet


@dataclass
class ContextNode:
    indent: int
    kind: str
    name: str = ""


class RenPyParser:
    def __init__(self, config_manager=None):
        self.logger = logging.getLogger(__name__)
        self.config = config_manager

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
        # Multiline narrator pattern - exclude closing patterns like """)
        self.narrator_multiline_re = re.compile(
            r'^(?P<indent>\s*)(?P<delim>"""|\'\'\')(?P<body>(?![\s]*\)).*)$'
        )
        self.extend_multiline_re = re.compile(
            r'^(?P<indent>\s*)extend\s+(?P<delim>"""|\'\'\')(?P<body>(?![\s]*\)).*)$'
        )

        self.menu_choice_re = re.compile(
            r'^\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*(?:if\s+[^:]+)?\s*:\s*'
        )
        # Menu choice multiline - exclude closing patterns
        self.menu_choice_multiline_re = re.compile(
            r'^\s*(?P<delim>"""|\'\'\')(?P<body>(?![\s]*\)).*)\s*(?:if\s+[^:]+)?\s*:\s*$'
        )
        self.menu_title_re = re.compile(
            r'^\s*menu\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')?:'
        )

        self.screen_text_re = re.compile(
            r'^\s*(?:text|label|tooltip)\s+(?:_\s*\(\s*)?(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')(?:\s*\))?'
        )
        self.textbutton_re = re.compile(
            r'^\s*textbutton\s+(?:_\s*\(\s*)?(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')(?:\s*\))?'
        )
        
        # Special patterns for _() marked screen elements - these should ALWAYS be translated
        # textbutton _("History") - navigation buttons
        self.textbutton_translatable_re = re.compile(
            r'^\s*textbutton\s+_\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*\)'
        )
        # text _("some text") - marked for translation
        self.screen_text_translatable_re = re.compile(
            r'^\s*(?:text|label|tooltip)\s+_\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*\)'
        )
        
        self.screen_multiline_re = re.compile(
            r'^\s*(?:text|label|tooltip|textbutton)\s+(?:_\s*\(\s*)?(?P<delim>"""|\'\'\')(?P<body>.*)$'
        )

        self.config_string_re = re.compile(
            r'^\s*config\.(?:name|version|about|menu_|window_title|save_name)\s*=\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        self.gui_text_re = re.compile(
            r'^\s*gui\.(?:text|button|label|title|heading|caption|tooltip|confirm)(?:_[a-z_]*)?(?:\[[^\]]*\])?\s*=\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        self.style_property_re = re.compile(
            r'^\s*style\s*\.\s*[a-zA-Z_]\w*\s*=\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # _p() function for multi-line paragraph text (single-line version)
        self._p_single_re = re.compile(
            r'^\s*(?:define\s+)?(?:gui|config)\.[a-zA-Z_]\w*\s*=\s*_p\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*\)'
        )
        
        # _p() function with triple-quoted strings (multi-line)
        self._p_multiline_re = re.compile(
            r'^\s*(?:define\s+)?(?:gui|config)\.[a-zA-Z_]\w*\s*=\s*_p\s*\(\s*(?P<delim>"""|\'\'\')(?P<body>.*)$'
        )
        
        # _() translation marker function (also for Character names)
        self._underscore_re = re.compile(
            r'^\s*(?:define\s+)?[a-zA-Z_]\w*\s*=\s*(?:Character\s*\(\s*)?_\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*\)?'
        )
        
        # define statement with simple string (fallback)
        self.define_string_re = re.compile(
            r'^\s*define\s+(?:gui|config)\.[a-zA-Z_]\w*\s*=\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # ========== OPTIMIZED SCREEN ELEMENT PATTERNS ==========
        # Combined alt text pattern for imagebutton, hotspot, hotbar (accessibility)
        self.alt_text_re = re.compile(
            r'^\s*(?:imagebutton|hotspot|hotbar)\s+.*?\balt\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # Combined input pattern for default/prefix/suffix
        self.input_text_re = re.compile(
            r'^\s*input\s+.*?\b(?:default|prefix|suffix)\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # Combined Notify pattern - both Notify() action and renpy.notify()
        self.notify_re = re.compile(
            r'^\s*(?:\$\s+)?(?:renpy\.)?[Nn]otify\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # Combined Confirm pattern - both Confirm() action and renpy.confirm()
        self.confirm_re = re.compile(
            r'^\s*(?:\$\s+)?(?:renpy\.)?[Cc]onfirm\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # renpy.input() function with prompt (also used as renpy_input_re alias)
        self.renpy_input_re = re.compile(
            r'^\s*(?:\$\s+)?renpy\.input\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # NVL mode clear text - nvl clear statement doesn't need translation, but nvl dialogue does
        # NVL character is handled same as regular character dialogue
        
        # Side image text (for accessibility)
        self.side_text_re = re.compile(
            r'^\s*side\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # vbox/hbox with text children (handled by screen_text_re)
        
        # Button text inside button statement
        self.button_text_re = re.compile(
            r'^\s*button\s*:.*?\btext\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # Voice statement - for dubbing/localization reference
        # voice "audio/eileen.ogg" - extracts path for localization mapping
        # NOTE: Voice files are handled separately for localization (audio replacement)
        self.voice_re = re.compile(
            r'^\s*voice\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # ========== ENHANCED PATTERNS FOR BETTER COVERAGE ==========
        
        # ATL (Animation and Transformation Language) text patterns
        # text inside animation/transform blocks: text "Hello" at center
        self.atl_text_re = re.compile(
            r'^\s*text\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s+(?:at|with|align|xalign|yalign|pos|xpos|ypos)'
        )
        
        # renpy.say() function - programmatic dialogue
        # $ renpy.say(e, "Hello there!")
        self.renpy_say_re = re.compile(
            r'^\s*(?:\$\s+)?renpy\.say\s*\([^,]*,\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # Action text patterns - SetField, Call with text parameters
        # action SetField(store, "message", _("Text"))
        self.action_text_re = re.compile(
            r'^\s*action\s+.*?_\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*\)'
        )
        
        # Caption pattern for various screen elements
        # vbar caption "Volume"
        self.caption_re = re.compile(
            r'^\s*(?:vbar|bar|slider|viewport|scrollbar)\s+.*?\bcaption\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # Frame/window title patterns
        # frame title "Settings"
        self.frame_title_re = re.compile(
            r'^\s*(?:frame|window|vbox|hbox|viewport)\s+.*?\btitle\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # Generic _() pattern anywhere in the line (fallback for complex expressions)
        # This catches: Function(_("text")), something(_("text")), etc.
        self.generic_translatable_re = re.compile(
            r'_\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*\)'
        )
        
        # ========== REN'PY TRANSLATION SYSTEM PATTERNS ==========
        # Hidden labels should be excluded from translation (label name hide:)
        self.hidden_label_re = re.compile(
            r'^label\s+[A-Za-z_][\w\.]*\s+hide\s*:'
        )
        
        # NVL mode patterns - nvl character definitions and statements
        # define narrator_nvl = Character(None, kind=nvl_narrator)
        self.nvl_character_re = re.compile(
            r'^\s*define\s+[A-Za-z_]\w*\s*=\s*Character\s*\([^)]*kind\s*=\s*nvl'
        )
        
        # id clause for dialogue - e "Text" id some_identifier
        # Used to force specific translation ID
        self.dialogue_with_id_re = re.compile(
            r'^(?P<indent>\s*)(?P<char>[A-Za-z_]\w*)\s+'
            r'(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
            r'\s+id\s+(?P<id>[A-Za-z_]\w*)'
        )
        
        # ========== END NEW PATTERNS ==========

        self.extend_re = re.compile(
            r'^(?P<indent>\s*)extend\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )

        self.python_renpy_re = re.compile(
            r'^\s*\$\s+.*?(?:renpy\.)?(?:input|notify)\s*\([^)]*?(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        self.renpy_function_re = re.compile(
            r'^\s*(?:renpy\.)?(?:input|notify)\s*\([^)]*?(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )

        # Regular label definition (excludes hidden labels)
        self.label_def_re = re.compile(r'^label\s+([A-Za-z_][\w\.]*)\s*(?!hide):')  # Negative lookahead for 'hide'
        self.menu_def_re = re.compile(r'^menu\s*(?:"([^"]*)"|\'([^\']*)\')?:')
        self.screen_def_re = re.compile(r'^screen\s+([A-Za-z_]\w*)')
        self.python_block_re = re.compile(r'^(?:init(?:\s+[-+]?\d+)?\s+)?python\b.*:')

        self.pattern_registry = [
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
            {'regex': self.action_text_re, 'type': 'translatable_string'},  # action _("text")
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
        ]

        self.multiline_registry = [
            {'regex': self.char_multiline_re, 'type': 'dialogue', 'character_group': 'char'},
            {'regex': self.extend_multiline_re, 'type': 'dialogue'},
            {'regex': self.narrator_multiline_re, 'type': 'dialogue'},
            {'regex': self.screen_multiline_re, 'type': 'ui'},
            # _p() multi-line patterns - check FIRST as it's most specific
            {'regex': self._p_multiline_re, 'type': 'paragraph'},
        ]

        self.renpy_technical_terms = {
            'left', 'right', 'center', 'top', 'bottom', 'gui', 'config',
            'true', 'false', 'none', 'auto', 'png', 'jpg', 'mp3', 'ogg'
        }

    def extract_translatable_text(self, file_path: Union[str, Path]) -> Set[str]:
        entries = self.extract_text_entries(file_path)
        return {entry['text'] for entry in entries}

    async def extract_translatable_text_async(self, file_path: Union[str, Path]) -> Set[str]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.extract_translatable_text, file_path)

    def extract_text_entries(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        try:
            lines = self._read_file_lines(file_path)
        except Exception as exc:
            self.logger.error("Error reading %s: %s", file_path, exc)
            return []

        entries: List[Dict[str, Any]] = []
        context_stack: List[ContextNode] = []
        index = 0

        while index < len(lines):
            raw_line = lines[index]
            stripped_line = raw_line.strip()

            if not stripped_line or stripped_line.startswith('#'):
                index += 1
                continue

            indent = self._calculate_indent(raw_line)
            self._pop_contexts(context_stack, indent)
            pending_context = self._detect_new_context(stripped_line, indent)
            context_path = self._build_context_path(context_stack, pending_context)

            multi_entry, consumed_idx = self._handle_multiline_start(
                lines, index, raw_line, stripped_line, context_path
            )
            if multi_entry:
                entries.append(multi_entry)
                index = consumed_idx + 1
                if pending_context:
                    context_stack.append(pending_context)
                continue

            matched = False
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
                    text = self._extract_string_content(quote)
                    text_type = descriptor.get('type') or self.determine_text_type(
                        text, stripped_line, context_path
                    )
                    entry = self._record_entry(
                        text=text,
                        line_number=index + 1,
                        context_line=stripped_line,
                        text_type=text_type,
                        context_path=context_path,
                        character=character,
                    )
                    if entry:
                        entries.append(entry)
                matched = True
                break

            if pending_context:
                context_stack.append(pending_context)

            if not matched:
                index += 1
            else:
                index += 1

        return entries

    def parse_directory(self, directory: Union[str, Path]) -> List[dict]:
        directory = Path(directory)
        search_root = self._resolve_search_root(directory)
        results: List[dict] = []
        rpy_files = [
            f
            for f in search_root.glob("**/*.rpy")
            if not self._is_excluded_rpy(f, search_root)
        ]
        self.logger.info(
            "Found %s .rpy files in %s (excluding Ren'Py engine & tl folders)",
            len(rpy_files),
            search_root,
        )

        for rpy_file in rpy_files:
            try:
                seen_texts: Set[str] = set()
                for entry in self.extract_text_entries(rpy_file):
                    text = entry['text']
                    if text in seen_texts:
                        continue
                    seen_texts.add(text)

                    text_type = entry.get('text_type') or self.determine_text_type(
                        text,
                        entry.get('context_line', ''),
                        entry.get('context_path'),
                    )

                    if not self._should_translate_text(text, text_type):
                        continue

                    text_data = {
                        'text': text,
                        'type': text_type,
                        'file_path': str(rpy_file),
                        'line_number': entry.get('line_number', 1),
                        'character': entry.get('character', ''),
                        'context': entry.get('context_line', ''),
                        'context_path': entry.get('context_path', []),
                        'processed_text': entry.get('processed_text', text),
                        'placeholder_map': entry.get('placeholder_map', {}),
                    }
                    results.append(text_data)
            except Exception as exc:
                self.logger.error("Error parsing file %s: %s", rpy_file, exc)

        self.logger.info("Total extracted texts: %s", len(results))
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

    def _resolve_search_root(self, directory: Path) -> Path:
        """Use the project's game/ folder when available to avoid SDK files."""

        game_dir = directory / "game"
        try:
            if game_dir.exists():
                return game_dir
        except Exception:
            pass
        return directory

    def _is_excluded_rpy(self, file_path: Path, search_root: Path) -> bool:
        """Skip Ren'Py translation output folders and SDK/engine files."""

        try:
            rel_path = file_path.relative_to(search_root)
        except ValueError:
            return True

        rel_str = str(rel_path).replace('\\', '/').lower()
        if rel_str.startswith("tl/"):
            return True

        # If user selected a folder above game/, ensure we ignore engine folders.
        engine_folders = ("renpy/", "lib/", "launcher/", "sdk/", "tutorial/", "templates/")
        return any(rel_str.startswith(segment) for segment in engine_folders)

    def _read_file_lines(self, file_path: Union[str, Path]) -> List[str]:
        with open(file_path, 'rb') as raw_file:
            raw_bytes = raw_file.read()
        detected = chardet.detect(raw_bytes)
        encoding = detected.get('encoding') or 'utf-8'
        return raw_bytes.decode(encoding, errors='ignore').splitlines()

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
            title = menu_match.group(1) or menu_match.group(2) or ''
            name = title or 'menu'
            return ContextNode(indent=indent, kind='menu', name=name)

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

        return {
            'text': text,
            'line_number': line_number,
            'context_line': context_line,
            'character': character,
            'text_type': resolved_type,
            'context_path': list(context_path),
            'processed_text': processed_text,
            'placeholder_map': placeholder_map,
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
        if quoted_string.startswith('"') and quoted_string.endswith('"'):
            content = quoted_string[1:-1]
        elif quoted_string.startswith("\'") and quoted_string.endswith("\'"):
            content = quoted_string[1:-1]
        else:
            content = quoted_string
        content = content.replace('\\"', '"').replace("\\'", "'")
        content = content.replace('\\n', '\n').replace('\\t', '\t')
        return content.strip()

    def is_meaningful_text(self, text: str) -> bool:
        if not text or len(text.strip()) < 2:
            return False

        text_lower = text.lower().strip()
        text_strip = text.strip()
        
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
                if not re.search(r'[a-zA-ZçğıöşüÇĞIİÖŞÜа-яА-Я]{3,}', remaining):
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

        return bool(re.search(r'[a-zA-ZçğıöşüÇĞIİÖŞÜ]', text)) and len(text.strip()) >= 2

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

    # ========== DEEP STRING SCANNER ==========
    # Bu modül, normal pattern'lerin yakalayamadığı gizli metinleri bulur
    # init python bloklarındaki dictionary'ler, değişken atamaları vb.
    
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
        already_found: Set[str] = set()
        
        # Normal pattern'lerle bulunanları al (bunları atlamak için)
        normal_entries = self.extract_text_entries(file_path)
        for entry in normal_entries:
            already_found.add(entry.get('text', ''))
        
        # Tüm dosya içeriği (çok satırlı stringler için)
        full_content = '\n'.join(lines)
        
        # Tüm string literal'leri yakalayan regex
        # Hem tek tırnak hem çift tırnak, escape karakterlerle
        string_literal_re = re.compile(
            r'''(?P<quote>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')'''
        )
        
        # Triple-quoted stringler için ayrı regex (çok satırlı - tüm dosyada ara)
        triple_quote_re = re.compile(
            r'''(?P<triple>"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')'''
        )
        
        # Önce çok satırlı triple-quoted stringleri tüm dosyada ara
        # Bu sayede birden fazla satıra yayılan stringler de yakalanır
        for match in triple_quote_re.finditer(full_content):
            text = self._extract_triple_string_content(match.group('triple'))
            if text and text not in already_found:
                # Satır numarasını hesapla (match.start() pozisyonundan)
                line_number = full_content[:match.start()].count('\n') + 1
                # Context line'ı al
                context_line = lines[line_number - 1].strip() if line_number <= len(lines) else ''
                
                if self._is_deep_scan_candidate(text, context_line):
                    # Python bloğu içinde mi kontrol et
                    in_python = self._is_position_in_python_block(lines, line_number)
                    entry = self._create_deep_scan_entry(
                        text=text,
                        line_number=line_number,
                        context_line=context_line,
                        in_python=in_python
                    )
                    if entry:
                        entries.append(entry)
                        already_found.add(text)
        
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
            for match in string_literal_re.finditer(line):
                text = self._extract_string_content(match.group('quote'))
                if text and text not in already_found and self._is_deep_scan_candidate(text, line):
                    entry = self._create_deep_scan_entry(
                        text=text,
                        line_number=line_num,
                        context_line=stripped,
                        in_python=in_python_block
                    )
                    if entry:
                        entries.append(entry)
                        already_found.add(text)
        
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
    
    def _is_deep_scan_candidate(self, text: str, context_line: str) -> bool:
        """
        Deep scan'de bulunan string'in çeviri adayı olup olmadığını kontrol et.
        Teknik stringleri filtrele.
        """
        if not text or len(text.strip()) < 3:
            return False
        
        text_lower = text.lower().strip()
        context_lower = context_line.lower()
        
        # is_meaningful_text kontrolü
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
        
        # En az 1 harf ve en az 3 karakter içermeli
        if not re.search(r'[a-zA-ZçğıöşüÇĞIİÖŞÜа-яА-Я]', text):
            return False
        
        return True
    
    def _create_deep_scan_entry(
        self,
        text: str,
        line_number: int,
        context_line: str,
        in_python: bool
    ) -> Optional[Dict[str, Any]]:
        """Deep scan sonucu için entry oluştur"""
        
        processed_text, placeholder_map = self.preserve_placeholders(text)
        
        text_type = 'deep_scan'
        if in_python:
            text_type = 'python_string'
        
        return {
            'text': text,
            'line_number': line_number,
            'context_line': context_line,
            'character': '',
            'text_type': text_type,
            'context_path': ['deep_scan'],
            'processed_text': processed_text,
            'placeholder_map': placeholder_map,
            'is_deep_scan': True,  # Marker for UI
        }
    
    def extract_with_deep_scan(
        self,
        file_path: Union[str, Path],
        include_deep_scan: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Normal extraction + opsiyonel deep scan.
        
        Args:
            file_path: Dosya yolu
            include_deep_scan: Deep scan sonuçlarını dahil et
            
        Returns:
            Birleştirilmiş entry listesi
        """
        entries = self.extract_text_entries(file_path)
        
        if include_deep_scan:
            deep_entries = self.deep_scan_strings(file_path)
            entries.extend(deep_entries)
        
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
                entries = self.extract_with_deep_scan(rpy_file, include_deep_scan)
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

