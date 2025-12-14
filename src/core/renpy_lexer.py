"""Improved Ren'Py lexer.

This lexer is line-oriented and maintains a simple indentation/context stack
so extracted `context_path` values are more accurate. It preserves both
`raw_text` (original literal including quotes/prefix) and `text` (unescaped).

The goal is not to be a full Ren'Py parser, but to reliably extract string
literals in contexts relevant for translation, handling prefixes and
triple-quoted literals across multiple lines.
"""
from __future__ import annotations

import re
from typing import List, Dict, Optional, Iterator
from dataclasses import dataclass


PREFIX_RE = re.compile(r'^(?P<prefix>[rRuUbBfF]{,2})')


def _unescape_renpy_string(s: str) -> str:
    if s is None:
        return ''
    s = s.replace('\\r\\n', '\n').replace('\\r', '\n').replace('\\n', '\n')
    s = s.replace('\\t', '\t').replace('\\"', '"').replace("\\'", "'")
    s = s.replace('\\\\', '\\')
    return s


def _classify_context(stack: List[Dict[str, object]]) -> List[str]:
    path = []
    for item in stack:
        if item.get('type') == 'screen':
            path.append(f"screen:{item.get('name')}")
        elif item.get('type') == 'label':
            path.append(f"label:{item.get('name')}")
        else:
            path.append(item.get('type'))
    return path


def extract_with_lexer(content: str, file_path: str = '') -> List[Dict[str, object]]:
    if content is None:
        return []

    stream = TokenStream(content, file_path=file_path)
    entries: List[Dict[str, object]] = []
    for token in stream:
        if token.type in ("STRING", "TRIPLE_STRING"):
            entries.append({
                'text': token.text,
                'raw_text': token.raw_text,
                'line_number': token.line_number,
                'context_path': token.context_path,
                'context_line': token.context_line,
                'text_type': token.text_type,
                'file_path': token.file_path,
            })
    return entries


@dataclass
class Token:
    type: str
    text: str
    raw_text: str
    prefix: str
    line_number: int
    context_path: List[str]
    context_line: str
    text_type: str
    file_path: str


class TokenStream:
    """Simple token stream API over the existing lexer logic.

    Methods:
    - peek(n=1): lookahead without advancing
    - next(): consume and return current token
    - current: last returned token or None
    - __iter__(): iterate over tokens
    """

    def __init__(self, content: str, file_path: str = '') -> None:
        self.content = content
        self.file_path = file_path
        self._tokens: List[Token] = []
        self._pos = 0
        self._tokenize()
        self._current: Optional[Token] = None

    def _tokenize(self) -> None:
        lines = self.content.splitlines()
        context_stack: List[Dict[str, object]] = []
        idx = 0
        while idx < len(lines):
            line = lines[idx]
            stripped = line.lstrip()
            indent = len(line) - len(stripped)

            while context_stack and indent <= context_stack[-1].get('indent', 0):
                context_stack.pop()

            if not stripped or stripped.startswith('#'):
                idx += 1
                continue

            low = stripped.lower()
            if low.startswith('label '):
                parts = stripped.split()
                name = parts[1].strip(':') if len(parts) > 1 else ''
                context_stack.append({'type': 'label', 'indent': indent, 'name': name})
            elif low.startswith('screen '):
                parts = stripped.split()
                name = parts[1].strip(':') if len(parts) > 1 else ''
                context_stack.append({'type': 'screen', 'indent': indent, 'name': name})
            elif low.startswith('menu'):
                context_stack.append({'type': 'menu', 'indent': indent})
            elif low.startswith('python') or low.startswith('init python'):
                context_stack.append({'type': 'python', 'indent': indent})

            i = 0
            while i < len(stripped):
                ch = stripped[i]
                if ch == '#':
                    break
                m_pref = PREFIX_RE.match(stripped[i:])
                pref = m_pref.group('prefix') if m_pref else ''
                j = i + (len(pref) if pref else 0)
                if j < len(stripped) and stripped[j] in ('"', "'"):
                    q = stripped[j]
                    is_triple = stripped[j:j+3] == q * 3
                    if is_triple:
                        delim = q * 3
                        collected = []
                        kline = idx
                        after = stripped[j+3:]
                        collected.append(after)
                        closed = False
                        while kline + 1 < len(lines):
                            kline += 1
                            l = lines[kline]
                            if delim in l:
                                before, _, after_cl = l.partition(delim)
                                collected.append(before)
                                raw_lines = lines[idx:kline+1]
                                raw = '\n'.join(raw_lines)
                                text_inner = '\n'.join(collected)
                                prefix = pref
                                if 'r' in prefix.lower():
                                    text = text_inner
                                else:
                                    text = _unescape_renpy_string(text_inner)
                                ctx = _classify_context(context_stack)
                                token = Token(
                                    type='TRIPLE_STRING',
                                    text=text,
                                    raw_text=raw,
                                    prefix=prefix,
                                    line_number=idx + 1,
                                    context_path=ctx,
                                    context_line=stripped,
                                    text_type='dialogue' if not ctx or any('label' in c for c in ctx) else 'ui',
                                    file_path=self.file_path,
                                )
                                self._tokens.append(token)
                                idx = kline
                                closed = True
                                break
                            else:
                                collected.append(l)
                        if not closed:
                            raw = '\n'.join(lines[idx:])
                            text = _unescape_renpy_string('\n'.join(collected))
                            ctx = _classify_context(context_stack)
                            token = Token(
                                type='TRIPLE_STRING',
                                text=text,
                                raw_text=raw,
                                prefix=pref,
                                line_number=idx + 1,
                                context_path=ctx,
                                context_line=stripped,
                                text_type='dialogue',
                                file_path=self.file_path,
                            )
                            self._tokens.append(token)
                            idx = len(lines)
                            break
                        break
                    else:
                        sstart = j
                        k = j + 1
                        escaped = False
                        inner = []
                        while k < len(stripped):
                            c = stripped[k]
                            if escaped:
                                inner.append('\\' + c)
                                escaped = False
                                k += 1
                                continue
                            if c == '\\':
                                escaped = True
                                k += 1
                                continue
                            if c == q:
                                raw = stripped[sstart:k+1]
                                text_inner = ''.join(inner)
                                prefix = pref
                                if 'r' in prefix.lower():
                                    text = text_inner
                                else:
                                    text = _unescape_renpy_string(text_inner)
                                ctx = _classify_context(context_stack)
                                token = Token(
                                    type='STRING',
                                    text=text,
                                    raw_text=raw,
                                    prefix=prefix,
                                    line_number=idx + 1,
                                    context_path=ctx,
                                    context_line=stripped,
                                    text_type='dialogue' if not ctx or any('label' in c for c in ctx) else 'ui',
                                    file_path=self.file_path,
                                )
                                self._tokens.append(token)
                                i = k + 1
                                break
                            else:
                                inner.append(c)
                            k += 1
                        else:
                            i = len(stripped)
                            break
                        i += 1
                        continue
                i += 1
            idx += 1

    def peek(self, n: int = 1) -> Optional[Token]:
        pos = self._pos + (n - 1)
        if 0 <= pos < len(self._tokens):
            return self._tokens[pos]
        return None

    def next(self) -> Optional[Token]:
        if self._pos >= len(self._tokens):
            return None
        tok = self._tokens[self._pos]
        self._pos += 1
        self._current = tok
        return tok

    @property
    def current(self) -> Optional[Token]:
        return self._current

    def __iter__(self) -> Iterator[Token]:
        while True:
            t = self.next()
            if t is None:
                break
            yield t

