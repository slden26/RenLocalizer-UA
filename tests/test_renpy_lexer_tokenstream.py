import sys
import textwrap

import pytest

from src.core.renpy_lexer import TokenStream


def collect_tokens(content: str):
    ts = TokenStream(content, file_path="test.rpy")
    return list(ts)


def test_single_line_string_unescape_and_raw():
    content = textwrap.dedent('''label start:
    "Hello\\nworld"
''')
    tokens = collect_tokens(content)
    assert len(tokens) == 1
    t = tokens[0]
    assert t.type == 'STRING'
    assert t.text == "Hello\nworld"
    assert '"Hello\\nworld"' in t.raw_text
    assert t.line_number == 2


def test_escaped_quote_inside_string():
    content = textwrap.dedent('''label a:
    "She said \\\"Hi\\\" to him"
''')
    tokens = collect_tokens(content)
    assert len(tokens) == 1
    t = tokens[0]
    assert t.text == 'She said "Hi" to him'


def test_raw_string_prefix_r_keeps_backslashes():
    content = textwrap.dedent('''label a:
    r"C:\\Program Files\\App"
''')
    tokens = collect_tokens(content)
    assert len(tokens) == 1
    t = tokens[0]
    assert t.prefix.lower() == 'r'
    assert t.text == 'C:\\Program Files\\App'


def test_triple_quoted_multiline_and_raw():
    content = textwrap.dedent('''screen example:
    """Line1
    Line2\\nwithescape
    Line3"""
''')
    tokens = collect_tokens(content)
    assert len(tokens) == 1
    t = tokens[0]
    assert t.type == 'TRIPLE_STRING'
    # triple preserves newlines inside text (unescaped)
    assert 'Line1' in t.text
    assert 'Line3' in t.text
    assert '\\nwithescape' not in t.text  # escaped sequence converted unless raw


def test_unterminated_triple_string_emits_token_for_rest():
    content = textwrap.dedent('''"""start
still here
''')
    tokens = collect_tokens(content)
    assert len(tokens) == 1
    t = tokens[0]
    assert t.type == 'TRIPLE_STRING'
    assert 'still here' in t.text


def test_context_classification_label_and_screen():
    content = textwrap.dedent('''label foo:
    "In label"

screen ui_screen:
    "In screen"
''')
    tokens = collect_tokens(content)
    assert len(tokens) == 2
    assert 'label:foo' in tokens[0].context_path[0]
    assert 'screen:ui_screen' in tokens[1].context_path[0]
