import importlib.machinery
import importlib.util
from pathlib import Path

# Load rpyc_reader module like tests do
rpyc_path = Path(__file__).parent.parent / "src" / "core" / "rpyc_reader.py"
parser_path = Path(__file__).parent.parent / "src" / "core" / "parser.py"
loader = importlib.machinery.SourceFileLoader('src.core.parser', str(parser_path))
spec = importlib.util.spec_from_loader(loader.name, loader)
parser_mod = importlib.util.module_from_spec(spec)
import sys
sys.modules[loader.name] = parser_mod
loader.exec_module(parser_mod)

loader2 = importlib.machinery.SourceFileLoader('src.core.rpyc_reader', str(rpyc_path))
spec2 = importlib.util.spec_from_loader(loader2.name, loader2)
module = importlib.util.module_from_spec(spec2)
sys.modules[loader2.name] = module
loader2.exec_module(module)

ASTTextExtractor = module.ASTTextExtractor
extr = ASTTextExtractor()
extr.current_file = 'tmp.rpyc'
extr.extracted = []
code = 'greeting = f"Hello {player_name}"'
extr._extract_strings_from_code(code, 1)
print('EXTRACTED', [e.text for e in extr.extracted])
import re
generic_string_re = re.compile(r'''(?P<quote>(?:[rRuUbBfF]{,2})?(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'))''')
for match in generic_string_re.finditer(code):
	raw = match.group('quote')
	print('RAW', raw)
	print('EXTRACTED', extr._extract_string_content(raw))
	start_pos = match.start()
	lookback_len = 1000
	lookback = code[max(0, start_pos - lookback_len):start_pos]
	import re
	list_context_re = re.compile(r'(?P<var>[a-zA-Z_]\w*)\s*(?:=\s*[\[\(\{]|\+=\s*[\[\(]|\.(?:append|extend|insert)\s*\()|["\'](?P<key>\w+)["\']\s*[:=]')
	assignment_context_re = re.compile(r'(?P<var>[a-zA-Z_]\w*)\s*=\s*')
	key_match = list(list_context_re.finditer(lookback))
	found_key = None
	if key_match:
		last = key_match[-1]
		found_key = last.groupdict().get('var') or last.groupdict().get('key')
	else:
		assign_match = list(assignment_context_re.finditer(lookback))
		if assign_match:
			last = assign_match[-1]
			found_key = last.groupdict().get('var')
	print('FOUND_KEY', found_key)
print('SEEN', extr.seen_texts)
print('EXTRACTED FULL', extr.extracted)
