import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import pytest


def load_module(path: Path, module_name: str):
    loader = importlib.machinery.SourceFileLoader(module_name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def modules():
    repo = Path(__file__).parent.parent
    parser_path = repo / "src" / "core" / "parser.py"
    rpyc_path = repo / "src" / "core" / "rpyc_reader.py"
    parser_mod = load_module(parser_path, "src.core.parser")
    rpyc_mod = load_module(rpyc_path, "src.core.rpyc_reader")
    return parser_mod, rpyc_mod


cases = [
    (
        'single list',
        'init python:\nitems = ["Sword", "Shield"]\n',
        ['Sword', 'Shield']
    ),
    (
        'multi-line list',
        'init python:\ntips = [\n    "Run fast",\n    "Eat food",\n    "Sleep"\n]\n',
        ['Run fast', 'Eat food', 'Sleep']
    ),
    (
        'dict value',
        'init python:\nquest = {"desc": "Go east"}\n',
        ['Go east']
    ),
    (
        'f-string simple',
        'init python:\nplayer_name = "Player"\ngreeting = f"Hello {player_name}"\n',
        ['Hello {player_name}']
    ),
    (
        'f-string expression',
        'init python:\npp = f"Score: {player.score + 10}"\n',
        ['Score: {player.score + 10}']
    ),
    (
        'percent format',
        'init python:\nmsg = "%s points" % player_points\n',
        ['%s points']
    ),
    (
        'format()',
        'init python:\nmsg = "{} points".format(player_points)\n',
        ['{} points']
    ),
    (
        'triple quoted',
        """init python:\ntext = '''Hello\nWorld'''\n""",
        ['Hello\nWorld']
    ),
    (
        'renpy function',
        'init python:\nrenpy.notify("Item purchased!")\n',
        ['Item purchased!']
    ),
    (
        'string concat plus',
        'init python:\nmsg = "Hello " + player_name\n',
        ['Hello ']  # only literal string part
    ),
    (
        'join',
        'init python:\nmsg = ", ".join(["a", "b"])\n',
        [', ', 'a', 'b']
    ),
    (
        'multiline concatenation',
        'init python:\ntext = "Hello " \n    "World"\n',
        ['Hello World']
    ),
    (
        'underscore p multiline',
        'init python:\ntext = _p("""Line1\nLine2""")\n',
        ['Line1\nLine2']
    ),
]


@pytest.mark.parametrize("name, content, expected", cases)
def test_extraction_dataset(modules, name, content, expected):
    parser_mod, rpyc_mod = modules
    RenPyParser = parser_mod.RenPyParser
    ASTTextExtractor = rpyc_mod.ASTTextExtractor

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        f = tmp_dir / "case.rpy"
        f.write_text(content, encoding='utf-8')

        # Run parser deep scan
        parser = RenPyParser()
        parser_res = parser.extract_with_deep_scan(f, include_deep_scan=True)
        parser_texts = {e['processed_text'] if 'processed_text' in e else e['text'] for e in parser_res}

        # For rpyc, we only have code scanning functions; test those on the code content
        extractor = ASTTextExtractor()
        extractor.extracted = []
        # extract from code string
        extractor._extract_strings_from_code(content, 1)
        rpyc_texts = {t.text for t in extractor.extracted}

        # Show differences
        # Use parser placeholder preservation for expected string canonicalization
        p_inst = RenPyParser()
        expected_processed = [p_inst.preserve_placeholders(t)[0] for t in expected]
        missing_in_parser = [t for t in expected_processed if t not in parser_texts]
        missing_in_rpyc = [t for t in expected_processed if t not in rpyc_texts]

        if missing_in_parser or missing_in_rpyc:
            print(f"Case '{name}': parser_missing={missing_in_parser}, rpyc_missing={missing_in_rpyc}")

        assert not missing_in_parser, f"Parser missed {missing_in_parser} in case {name}"
        assert not missing_in_rpyc, f"RPYC extractor missed {missing_in_rpyc} in case {name}"
