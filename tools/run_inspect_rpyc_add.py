import importlib.machinery, importlib.util, sys
from pathlib import Path
repo = Path(__file__).parent.parent
rpyc_path = repo / 'src' / 'core' / 'rpyc_reader.py'
parser_path = repo / 'src' / 'core' / 'parser.py'
loader = importlib.machinery.SourceFileLoader('src.core.parser', str(parser_path))
parser_spec = importlib.util.spec_from_loader(loader.name, loader)
parser_mod = importlib.util.module_from_spec(parser_spec)
sys.modules[loader.name] = parser_mod
loader.exec_module(parser_mod)
loader2 = importlib.machinery.SourceFileLoader('src.core.rpyc_reader', str(rpyc_path))
spec2 = importlib.util.spec_from_loader(loader2.name, loader2)
module = importlib.util.module_from_spec(spec2)
sys.modules[loader2.name] = module
loader2.exec_module(module)

ASTTextExtractor = module.ASTTextExtractor
extr = ASTTextExtractor()

# Try to add a sample string
extr._add_text('Sword', 1, 'string', context='rpyc_val:items')
print('ADDED', [e.text for e in extr.extracted])
