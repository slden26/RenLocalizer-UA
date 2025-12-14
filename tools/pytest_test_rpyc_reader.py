import importlib.machinery
import importlib.util
from pathlib import Path
import pytest


def load_rpyc_module():
    # Ensure package hierarchy exists in sys.modules so relative imports work
    import sys
    pkg_name = 'src'
    core_pkg = 'src.core'
    if pkg_name not in sys.modules:
        import types
        sys.modules[pkg_name] = types.ModuleType(pkg_name)
    if core_pkg not in sys.modules:
        import types
        core_module = types.ModuleType(core_pkg)
        core_module.__path__ = [str(Path(__file__).parent.parent / 'src' / 'core')]
        sys.modules[core_pkg] = core_module

    # Load parser module first to satisfy relative import in rpyc_reader
    parser_path = Path(__file__).parent.parent / "src" / "core" / "parser.py"
    parser_loader = importlib.machinery.SourceFileLoader("src.core.parser", str(parser_path))
    parser_spec = importlib.util.spec_from_loader(parser_loader.name, parser_loader)
    parser_mod = importlib.util.module_from_spec(parser_spec)
    sys.modules[parser_loader.name] = parser_mod
    parser_loader.exec_module(parser_mod)

    rpyc_path = Path(__file__).parent.parent / "src" / "core" / "rpyc_reader.py"
    loader = importlib.machinery.SourceFileLoader("src.core.rpyc_reader", str(rpyc_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rpyc_module():
    return load_rpyc_module()


@pytest.mark.parametrize("code,expected", [
    ("items = [\"Sword\", \"Shield\"]", ['Sword', 'Shield']),
    ("quest = {\"desc\": \"Go east\"}", ['Go east']),
    ("greeting = f\"Hello {player_name}\"", ['Hello ⟦']),
    ("items.append(\"Sword\")", ['Sword']),
    ("items.extend([\"A\", \"B\"])", ['A', 'B']),
    ("items.insert(0, \"X\")", ['X']),
    ("items += [\"Sword\"]", ['Sword']),
])

def test_extract_strings_from_code(rpyc_module, code, expected):
    ASTTextExtractor = rpyc_module.ASTTextExtractor
    extr = ASTTextExtractor()
    extr.current_file = str(Path('tmp.rpyc'))
    extr.extracted = []
    extr._extract_strings_from_code(code, 1)
    found = {t.text for t in extr.extracted}
    for t in expected:
        if '⟦' in t:
            # placeholder present - assert any found contains 'Hello ' and a placeholder token
            assert any(f"Hello " in f and '⟦' in f for f in found)
        else:
            assert t in found


def test_assignment_context_and_type(rpyc_module):
    ASTTextExtractor = rpyc_module.ASTTextExtractor
    extr = ASTTextExtractor()
    extr.current_file = str(Path('tmp.rpyc'))
    extr.extracted = []
    code = 'items = ["Sword", "Shield"]'
    extr._extract_strings_from_code(code, 1)
    found = [t for t in extr.extracted if t.text in {'Sword', 'Shield'}]
    assert len(found) == 2
    for item in found:
        assert item.context == 'rpyc_val:items'
        assert item.text_type == 'data_string'


def test_fstring_placeholders_preserved(rpyc_module):
    ASTTextExtractor = rpyc_module.ASTTextExtractor
    extr = ASTTextExtractor()
    extr.current_file = str(Path('tmp.rpyc'))
    extr.extracted = []
    code = 'pp = f"Score: {player.score + 10}"'
    extr._extract_strings_from_code(code, 1)
    found = [t for t in extr.extracted if 'Score:' in t.text]
    assert found
    # Check placeholders present in processed text and placeholder_map populated
    for f in found:
        assert '⟦' in f.text and '⟧' in f.text
        assert f.placeholder_map


def test_preserve_and_restore_placeholders(rpyc_module):
    from src.core.parser import RenPyParser
    p = RenPyParser()
    text = 'Hello {player_name}, score: %(score)d'
    processed, placeholder_map = p.preserve_placeholders(text)
    assert '⟦' in processed and '⟧' in processed
    restored = p.restore_placeholders(processed, placeholder_map)
    assert restored == text


def test_rpyc_dedupe_prefer_context(rpyc_module):
    """Ensure that when AST would produce both a python_string and data_string for the same text, only the contextual data_string remains."""
    ASTTextExtractor = rpyc_module.ASTTextExtractor
    extr = ASTTextExtractor()
    extr.current_file = str(Path('tmp.rpyc'))
    extr.extracted = []
    code = 'items = ["Sword", "Shield"]'
    extr._extract_strings_from_code(code, 1)
    found_texts = [t.text for t in extr.extracted]
    assert found_texts.count('Sword') == 1
    sword_entry = next(t for t in extr.extracted if t.text == 'Sword')
    assert sword_entry.context == 'rpyc_val:items'


@pytest.mark.parametrize("line,expected", [
    ("tips = [\"Run fast\", \"Eat food\"]", ['Run fast', 'Eat food']),
])

def test_extract_strings_from_line(rpyc_module, line, expected):
    ASTTextExtractor = rpyc_module.ASTTextExtractor
    extr = ASTTextExtractor()
    extr.current_file = str(Path('tmp.rpyc'))
    extr.extracted = []
    extr._extract_strings_from_line(line, 1)
    found = {t.text for t in extr.extracted}
    for t in expected:
        assert t in found
