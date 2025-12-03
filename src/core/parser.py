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
        
        # ========== NEW SCREEN ELEMENT PATTERNS ==========
        
        # imagebutton with alt text for accessibility
        self.imagebutton_alt_re = re.compile(
            r'^\s*imagebutton\s+.*?\balt\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # hotspot with alt text
        self.hotspot_alt_re = re.compile(
            r'^\s*hotspot\s+.*?\balt\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # hotbar with alt text
        self.hotbar_alt_re = re.compile(
            r'^\s*hotbar\s+.*?\balt\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # input with default text
        self.input_default_re = re.compile(
            r'^\s*input\s+.*?\bdefault\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # input with prefix/suffix
        self.input_prefix_re = re.compile(
            r'^\s*input\s+.*?\b(?:prefix|suffix)\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # frame with title (indirect via label)
        self.frame_label_re = re.compile(
            r'^\s*frame\s*:\s*.*?\blabel\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # Action strings - Jump, Call, Show, etc. with string arguments that may need translation
        # Notify action: Notify("message")
        self.action_notify_re = re.compile(
            r'^\s*.*?\bNotify\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # Confirm action: Confirm("prompt", ...)
        self.action_confirm_re = re.compile(
            r'^\s*.*?\bConfirm\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # renpy.notify() function
        self.renpy_notify_re = re.compile(
            r'^\s*(?:\$\s+)?renpy\.notify\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # renpy.confirm() function
        self.renpy_confirm_re = re.compile(
            r'^\s*(?:\$\s+)?renpy\.confirm\s*\(\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        
        # renpy.input() function with prompt
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

        self.label_def_re = re.compile(r'^label\s+([A-Za-z_][\w\.]*)\s*:')
        self.menu_def_re = re.compile(r'^menu\s*(?:"([^"]*)"|\'([^\']*)\')?:')
        self.screen_def_re = re.compile(r'^screen\s+([A-Za-z_]\w*)')
        self.python_block_re = re.compile(r'^(?:init(?:\s+[-+]?\d+)?\s+)?python\b.*:')

        self.pattern_registry = [
            # Most specific patterns first
            # NEW: Extended screen patterns (more specific)
            {'regex': self.imagebutton_alt_re, 'type': 'alt_text'},
            {'regex': self.hotspot_alt_re, 'type': 'alt_text'},
            {'regex': self.hotbar_alt_re, 'type': 'alt_text'},
            {'regex': self.input_default_re, 'type': 'input'},
            {'regex': self.input_prefix_re, 'type': 'input'},
            {'regex': self.action_notify_re, 'type': 'notify'},
            {'regex': self.action_confirm_re, 'type': 'confirm'},
            {'regex': self.renpy_notify_re, 'type': 'notify'},
            {'regex': self.renpy_confirm_re, 'type': 'confirm'},
            {'regex': self.renpy_input_re, 'type': 'input'},
            # _() marked screen elements - ALWAYS translatable (check BEFORE general patterns)
            {'regex': self.textbutton_translatable_re, 'type': 'translatable_string'},
            {'regex': self.screen_text_translatable_re, 'type': 'translatable_string'},
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
        if not text:
            return text, {}

        placeholder_map: Dict[str, str] = {}
        processed_text = text
        placeholder_counter = 0

        renpy_var_pattern = r'\[([^\]]+)\]'
        for match in re.finditer(renpy_var_pattern, text):
            placeholder_id = f"XYZ{placeholder_counter:03d}"
            placeholder_map[placeholder_id] = match.group(0)
            processed_text = processed_text.replace(match.group(0), placeholder_id, 1)
            placeholder_counter += 1

        renpy_tag_pattern = r'\{[^}]*\}'
        for match in re.finditer(renpy_tag_pattern, text):
            placeholder_id = f"XYZ{placeholder_counter:03d}"
            placeholder_map[placeholder_id] = match.group(0)
            processed_text = processed_text.replace(match.group(0), placeholder_id, 1)
            placeholder_counter += 1

        python_format_pattern = r'%\([^)]+\)[sdif]|%[sdif]'
        for match in re.finditer(python_format_pattern, text):
            placeholder_id = f"XYZ{placeholder_counter:03d}"
            placeholder_map[placeholder_id] = match.group(0)
            processed_text = processed_text.replace(match.group(0), placeholder_id, 1)
            placeholder_counter += 1

        fstring_pattern = r'\{[^}]+\}'
        for match in re.finditer(fstring_pattern, processed_text):
            if not match.group(0).startswith('XYZ'):
                placeholder_id = f"XYZ{placeholder_counter:03d}"
                placeholder_map[placeholder_id] = match.group(0)
                processed_text = processed_text.replace(match.group(0), placeholder_id, 1)
                placeholder_counter += 1

        return processed_text, placeholder_map

        processed_text = text
        placeholder_counter = 0
        
        # RenPy variable placeholders like [variable_name]
        renpy_var_pattern = r'\[([^\]]+)\]'
        for match in re.finditer(renpy_var_pattern, text):
            # Use NUMBERS ONLY to prevent translation engines from translating
            placeholder_id = f"XYZ{placeholder_counter:03d}"
            placeholder_map[placeholder_id] = match.group(0)
            processed_text = processed_text.replace(match.group(0), placeholder_id, 1)
            placeholder_counter += 1
        
        # RenPy text tags like {color=#ff0000}, {/color}, {b}, {/b}, etc.
        renpy_tag_pattern = r'\{[^}]*\}'
        for match in re.finditer(renpy_tag_pattern, text):
            # Use NUMBERS ONLY to prevent translation engines from translating
            placeholder_id = f"XYZ{placeholder_counter:03d}"
            placeholder_map[placeholder_id] = match.group(0)
            processed_text = processed_text.replace(match.group(0), placeholder_id, 1)
            placeholder_counter += 1
        
        # Python-style format strings like %(variable)s, %s, %d, etc.
        python_format_pattern = r'%\([^)]+\)[sdif]|%[sdif]'
        for match in re.finditer(python_format_pattern, text):
            # Use NUMBERS ONLY to prevent translation engines from translating
            placeholder_id = f"XYZ{placeholder_counter:03d}"
            placeholder_map[placeholder_id] = match.group(0)
            processed_text = processed_text.replace(match.group(0), placeholder_id, 1)
            placeholder_counter += 1
        
        # Python 3.6+ f-string style placeholders like {variable}
        fstring_pattern = r'\{[^}]+\}'
        for match in re.finditer(fstring_pattern, processed_text):  # Use processed_text to avoid double replacement
            # Skip if already replaced by RenPy tag pattern
            if not match.group(0).startswith('XYZ'):
                # Use NUMBERS ONLY to prevent translation engines from translating
                placeholder_id = f"XYZ{placeholder_counter:03d}"
                placeholder_map[placeholder_id] = match.group(0)
                processed_text = processed_text.replace(match.group(0), placeholder_id, 1)
                placeholder_counter += 1
        
        return processed_text, placeholder_map
    
    def restore_placeholders(self, translated_text: str, placeholder_map: dict) -> str:
        """
        Restore placeholders in translated text.
        """
        if not translated_text or not placeholder_map:
            return translated_text
        
        import re
        restored_text = translated_text
        
        # First try exact match
        for placeholder_id, original_placeholder in placeholder_map.items():
            restored_text = restored_text.replace(placeholder_id, original_placeholder)
        
        # Try with various corruptions that translation engines might introduce
        for placeholder_id, original_placeholder in placeholder_map.items():
            # Handle case changes, spaces, and common corruptions
            corrupted_patterns = [
                # Case variations
                placeholder_id.lower(),                    # xyz000
                placeholder_id.upper(),                    # XYZ000
                placeholder_id.capitalize(),               # Xyz000
                placeholder_id.replace('XYZ', 'Xyz'),      # Xyz000
                placeholder_id.replace('XYZ', 'xyz'),      # xyz000
                
                # Space variations
                placeholder_id.replace('XYZ', 'XYZ '),     # XYZ 000
                placeholder_id.replace('XYZ', ' XYZ'),     # Space before
                placeholder_id.replace('XYZ', ' XYZ '),    # Spaces around
                placeholder_id.replace('XYZ', 'Xyz '),     # Xyz 000
                placeholder_id.replace('XYZ', 'xyz '),     # xyz 000
                
                # Multiple space variations
                placeholder_id.replace('XYZ', 'X Y Z'),    # X Y Z000
                placeholder_id.replace('XYZ', 'x y z'),    # x y z000
            ]
            
            for pattern in corrupted_patterns:
                # Try both exact and with spaces around
                restored_text = restored_text.replace(pattern, original_placeholder)
                restored_text = restored_text.replace(f" {pattern} ", f" {original_placeholder} ")
                restored_text = restored_text.replace(f" {pattern}", f" {original_placeholder}")
                restored_text = restored_text.replace(f"{pattern} ", f"{original_placeholder} ")
        
        # Handle very corrupted cases with regex - more aggressive approach
        for placeholder_id, original_placeholder in placeholder_map.items():
            # Extract the number from XYZ000 pattern
            if placeholder_id.startswith('XYZ'):
                number_part = placeholder_id[3:]  # Get "000" part
                
                # Create multiple regex patterns for different corruptions
                patterns = [
                    # Standard corruptions
                    r'\b\s*[Xx][Yy][Zz]\s*' + number_part + r'\s*\b',
                    # With spaces in XYZ
                    r'\b\s*[Xx]\s*[Yy]\s*[Zz]\s*' + number_part + r'\s*\b',
                    # Just the number when XYZ gets completely corrupted
                    r'\b(?:XYZ|Xyz|xyz|X Y Z|x y z)\s*' + number_part + r'\b',
                    # More aggressive - any 3 letters followed by the number
                    r'\b[A-Za-z]{3}\s*' + number_part + r'\b'
                ]
                
                for pattern in patterns:
                    restored_text = re.sub(pattern, original_placeholder, restored_text, flags=re.IGNORECASE)
        
        return restored_text
