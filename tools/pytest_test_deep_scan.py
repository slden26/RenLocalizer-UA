import tempfile
from pathlib import Path
import importlib.machinery
import importlib.util
import pytest


def load_parser_module():
    parser_path = Path(__file__).parent.parent / "src" / "core" / "parser.py"
    loader = importlib.machinery.SourceFileLoader("parser_module", str(parser_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def parser_module():
    return load_parser_module()


@pytest.mark.parametrize("content,expected", [
    (
        '''init python:
    tips = [
        "Run fast",
        "Eat food",
        "Sleep"
    ]
''',
        ['Run fast', 'Eat food', 'Sleep']
    ),
    (
        '''init python:
    renpy.notify("Item purchased!")
''',
        ['Item purchased!']
    ),
    (
        '''init python:
    quest = {"desc": "Go east"}
''',
        ['Go east']
    ),
    (
        '''init python:
    items.append("Sword")
''',
        ['Sword']
    ),
    (
        '''init python:
    items.extend(["A","B"])
''',
        ['A','B']
    ),
    (
        '''init python:
    items.insert(0, "X")
''',
        ['X']
    ),
    (
        '''init python:
    items += ["Sword"]
''',
        ['Sword']
    ),
])

def test_deep_scan_strings(parser_module, content, expected):
    RenPyParser = parser_module.RenPyParser
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        f = tmp_dir / "test_file.rpy"
        f.write_text(content, encoding="utf-8")
        parser = RenPyParser()
        results = parser.extract_with_deep_scan(f, include_deep_scan=True)
        texts = {e['text'] for e in results}
        for t in expected:
                if '⟦' in t:
                    assert any(f"Hello " in f and '⟦' in f for f in texts)
                else:
                    assert t in texts


def test_deep_scan_whitelist_behavior(parser_module):
    RenPyParser = parser_module.RenPyParser
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        f = tmp_dir / "test_file.rpy"
        f.write_text(
            'init python:\nitems = ["Sword", "Shield"]\n' +
            'data = ["Alpha", "Beta"]\n', encoding='utf-8'
        )
        parser = RenPyParser()
        results = parser.extract_with_deep_scan(f, include_deep_scan=True)
        items_ctx = [r for r in results if r['text'] == 'Sword']
        assert items_ctx and any('variable:items' in (p for p in r.get('context_path', [])) for r in items_ctx)
        # data (not whitelisted) should either not be extracted or be filtered
        assert not any(r['text']=='Alpha' for r in results)


    def test_deep_scan_dedupe_prefer_variable_context(parser_module):
        RenPyParser = parser_module.RenPyParser
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)
            f = tmp_dir / "test_file.rpy"
            f.write_text(
                'init python:\nitems = ["Sword"]\n' +
                'some_text = "Sword"\n', encoding='utf-8'
            )
            parser = RenPyParser()
            results = parser.extract_with_deep_scan(f, include_deep_scan=True)
            swords = [r for r in results if r['text'] == 'Sword']
            # Should only be one Sword and prefer variable context rather than plain python string
            assert len(swords) == 1
            assert any('variable:items' in (ctx for ctx in r.get('context_path', [])) for r in swords)
