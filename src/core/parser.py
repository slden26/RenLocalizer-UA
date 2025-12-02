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
        self.narrator_multiline_re = re.compile(
            r'^(?P<indent>\s*)(?P<delim>"""|\'\'\')(?P<body>.*)$'
        )
        self.extend_multiline_re = re.compile(
            r'^(?P<indent>\s*)extend\s+(?P<delim>"""|\'\'\')(?P<body>.*)$'
        )

        self.menu_choice_re = re.compile(
            r'^\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*(?:if\s+[^:]+)?\s*:\s*'
        )
        self.menu_choice_multiline_re = re.compile(
            r'^\s*(?P<delim>"""|\'\'\')(?P<body>.*)\s*(?:if\s+[^:]+)?\s*:\s*$'
        )
        self.menu_title_re = re.compile(
            r'^\s*menu\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')?:'
        )

        self.screen_text_re = re.compile(
            r'^\s*(?:text|label|tooltip)\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        self.textbutton_re = re.compile(
            r'^\s*textbutton\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')'
        )
        self.screen_multiline_re = re.compile(
            r'^\s*(?:text|label|tooltip|textbutton)\s+(?P<delim>"""|\'\'\')(?P<body>.*)$'
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
            {'regex': self.char_dialog_re, 'type': 'dialogue', 'character_group': 'char'},
            {'regex': self.extend_re, 'type': 'dialogue'},
            {'regex': self.narrator_re, 'type': 'dialogue'},
            {'regex': self.menu_choice_re, 'type': 'menu'},
            {'regex': self.menu_title_re, 'type': 'menu'},
            {'regex': self.screen_text_re, 'type': 'ui'},
            {'regex': self.textbutton_re, 'type': 'button'},
            {'regex': self.config_string_re, 'type': 'config'},
            {'regex': self.gui_text_re, 'type': 'gui'},
            {'regex': self.style_property_re, 'type': 'style'},
            {'regex': self.python_renpy_re, 'type': 'renpy_func'},
            {'regex': self.renpy_function_re, 'type': 'renpy_func'},
        ]

        self.multiline_registry = [
            {'regex': self.char_multiline_re, 'type': 'dialogue', 'character_group': 'char'},
            {'regex': self.extend_multiline_re, 'type': 'dialogue'},
            {'regex': self.narrator_multiline_re, 'type': 'dialogue'},
            {'regex': self.screen_multiline_re, 'type': 'ui'},
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
            text, end_index = self._consume_multiline(lines, index, delimiter, body)

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
    ) -> Tuple[str, int]:
        buffer: List[str] = []
        remainder = initial_body or ''
        closing_inline = remainder.find(delimiter)
        if closing_inline != -1:
            buffer.append(remainder[:closing_inline])
            return "\n".join(buffer).strip('\n'), start_index

        if remainder:
            buffer.append(remainder)

        index = start_index + 1
        while index < len(lines):
            current = lines[index]
            closing_pos = current.find(delimiter)
            if closing_pos != -1:
                buffer.append(current[:closing_pos])
                tail = current[closing_pos + len(delimiter) :].strip()
                if tail:
                    buffer.append(tail)
                return "\n".join(buffer).strip('\n'), index

            buffer.append(current)
            index += 1

        return "\n".join(buffer).strip('\n'), len(lines) - 1

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
        if text_lower in self.renpy_technical_terms:
            return False

        if re.fullmatch(r"\s*(\[[^\]]+\]|\{[^}]+\}|%s|%\([^)]+\)[sdif])\s*", text):
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

        return 'dialogue'

    def _should_translate_text(self, text: str, text_type: str) -> bool:
        if self.config is None:
            return True

        ts = self.config.translation_settings
        if text_type == 'dialogue' and not ts.translate_dialogue:
            return False
        if text_type == 'menu' and not ts.translate_menu:
            return False
        if text_type == 'ui' and not ts.translate_ui:
            return False
        if text_type == 'config' and not ts.translate_config_strings:
            return False
        if text_type == 'gui' and not ts.translate_gui_strings:
            return False
        if text_type == 'style' and not ts.translate_style_strings:
            return False
        if text_type == 'renpy_func' and not ts.translate_renpy_functions:
            return False

        rules: Dict[str, Any] = getattr(self.config, 'never_translate_rules', {}) or {}
        text_strip = text.strip()

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
