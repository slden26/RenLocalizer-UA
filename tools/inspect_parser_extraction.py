import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import sys

# Load parser without package-level side effects
parser_path = Path(__file__).parent.parent / 'src' / 'core' / 'parser.py'
loader = importlib.machinery.SourceFileLoader('parser_module', str(parser_path))
spec = importlib.util.spec_from_loader(loader.name, loader)
parser_mod = importlib.util.module_from_spec(spec)
import sys
sys.modules[loader.name] = parser_mod
loader.exec_module(parser_mod)

RenPyParser = parser_mod.RenPyParser

with tempfile.TemporaryDirectory() as tmp_dir:
    tmp_dir = Path(tmp_dir)
    f = tmp_dir / 'test_file.rpy'
    content = '''init python:
    tips = [
        "Run fast",
        "Eat food",
        "Sleep"
    ]
    greeting = f"Hello {player_name}"
    msg = "Hello " + player_name
    msg2 = ", ".join(["a", "b"])
    text = "Hello " \
        "World"
'''
    f.write_text(content, encoding='utf-8')
    p = RenPyParser()
    results = p.extract_with_deep_scan(f, include_deep_scan=True)
    print('RESULTS', results)
