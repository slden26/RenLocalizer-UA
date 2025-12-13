import importlib.machinery, importlib.util, sys
from pathlib import Path
import tempfile

repo = Path(__file__).parent.parent
parser_path = repo / 'src' / 'core' / 'parser.py'
loader = importlib.machinery.SourceFileLoader('src.core.parser', str(parser_path))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = module
loader.exec_module(module)

RenPyParser = module.RenPyParser

cases = [
    ('fstring', 'init python:\nplayer_name = "Player"\ngreeting = f"Hello {player_name}"\n'),
    ('plus concat', 'init python:\nmsg = "Hello " + player_name\n'),
    ('join', 'init python:\nmsg = ", ".join(["a", "b"])\n'),
    ('multiline concat', 'init python:\ntext = "Hello " \\\n+    "World"\n'),
]

for name, content in cases:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        f = tmp_dir / 'case.rpy'
        f.write_text(content, encoding='utf-8')
        p = RenPyParser()
        res = p.extract_with_deep_scan(f, include_deep_scan=True)
        print('\nCase', name)
        for e in res:
            print(e)
