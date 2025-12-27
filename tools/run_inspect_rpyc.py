import importlib.machinery, importlib.util, sys
from pathlib import Path
repo = Path(__file__).parent.parent
parser_path = repo / 'src' / 'core' / 'parser.py'
rpyc_path = repo / 'src' / 'core' / 'rpyc_reader.py'
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

codes = [
    'init python:\nitems = ["Sword", "Shield"]\n',
    'init python:\ntips = [\n  "Run fast",\n  "Eat food"\n]\n',
    'init python:\nquest = {"desc": "Go east"}\n',
    'init python:\nplayer_name = "Player"\ngreeting = f"Hello {player_name}"\n',
    'init python:\npp = f"Score: {player.score + 10}"\n',
    'init python:\nmsg = "Hello " + player_name\n',
    'init python:\nmsg = ", ".join(["a", "b"])\n',
    'init python:\ntext = "Hello " \\\n+    "World"\n',
]

for code in codes:
    print('\n---- CODE ----')
    print(code)
    extr.extracted = []
    import re
    generic_string_re = re.compile(r'''(?P<quote>(?:[rRuUbBfF]{,2})?(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'))''')
    matches = [m.group('quote') for m in generic_string_re.finditer(code)]
    print('REGEX MATCHES', matches)
    for m in matches:
        raw = extr._extract_string_content(m)
        print(' RAW_TEXT', raw, 'IS_TECH', extr._is_technical_string(raw, ''))
    ok = False
    try:
        ok = extr._extract_strings_from_code_ast(code, 1)
        print('AST PARSED', ok)
    except Exception as e:
        print('AST ERROR', e)
    if not ok:
        extr._extract_strings_from_code(code, 1)
    print('FOUND ->', [e.text for e in extr.extracted])
    # Monkey patch _add_text to print calls
    orig_add = extr._add_text
    calls = []
    def dbg_add(text, line_number, text_type, character='', context='', placeholder_map=None):
        print('DBG _add_text CALLED ->', text, 'context=', context, 'type=', text_type)
        calls.append((text, context, text_type))
        return orig_add(text, line_number, text_type, character, context, placeholder_map)
    extr._add_text = dbg_add
    extr.extracted = []
    extr._extract_strings_from_code(code, 1)
    print('AFTER MONKEY FOUND ->', [e.text for e in extr.extracted])
    extr._add_text = orig_add
    # Now run a manual replica of the fallback code to debug why extras were not added
    print('\nMANUAL SCAN:')
    p = parser_mod.RenPyParser()
    generic_string_re = re.compile(r"""(?P<quote>(?:[rRuUbBfF]{,2})?(?:\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'))""")
    list_context_re = re.compile(r'(?P<var>[a-zA-Z_]\w*)\s*(?:=\s*[\[\(\{]|\+=\s*[\[\(]|\.(?:append|extend|insert)\s*\()|["\'](?P<key>\w+)["\']\s*[:=]')
    matches2 = list(generic_string_re.finditer(code))
    for match in matches2:
        raw_quote = match.group('quote')
        text = extr._extract_string_content(raw_quote)
        if not text or len(text) < 2:
            print(' SKIP too short', text)
            continue
        if extr._is_technical_string(text):
            print(' SKIP technical', text)
            continue
        start_pos = match.start()
        lookback_len = 1000
        lookback = code[max(0, start_pos-lookback_len):start_pos]
        key_match = list(list_context_re.finditer(lookback))
        found_key = None
        if key_match:
            last = key_match[-1]
            found_key = last.groupdict().get('var') or last.groupdict().get('key')
        print(' found_key', found_key)
        is_whitelisted = found_key and found_key.lower() in extr.DATA_KEY_WHITELIST
        print(' whitelisted', is_whitelisted)
        processed_text, placeholder_map = p.preserve_placeholders(text)
        if found_key:
            if is_whitelisted:
                extr._add_text(processed_text, 1, 'data_string', context=f'rpyc_val:{found_key}', placeholder_map=placeholder_map)
                print(' ADD data_string', processed_text)
            else:
                extr._add_text(processed_text, 1, 'string', context='', placeholder_map=placeholder_map)
                print(' ADD string var', processed_text)
        else:
            extr._add_text(processed_text, 1, 'string', context='', placeholder_map=placeholder_map)
            print(' ADD string', processed_text)
    print('MANUAL ADD FOUND', [e.text for e in extr.extracted])
