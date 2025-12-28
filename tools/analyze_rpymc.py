
import sys
import types
import zlib
import pickle


class AutoDummyImporter:
    def find_spec(self, fullname, path, target=None):
        if fullname not in sys.modules:
            sys.modules[fullname] = DummyModule(fullname)
        return None

sys.meta_path.insert(0, AutoDummyImporter())

# Sahte renpy modülü ve alt modüller
fake_renpy = types.ModuleType('renpy')
fake_ast = types.ModuleType('renpy.ast')
fake_sl2 = types.ModuleType('renpy.sl2')
fake_slast = types.ModuleType('renpy.sl2.slast')
fake_atl = types.ModuleType('renpy.atl')


# Sık karşılaşılan AST sınıfları için dummy class

class DummyMeta(type):
    def __call__(cls, *a, **k):
        return super().__call__(*a, **k)

class Dummy(metaclass=DummyMeta):
    def __init__(self, *a, **k):
        pass
    def __setstate__(self, state):
        if isinstance(state, dict):
            self.__dict__.update(state)
    def __call__(self, *a, **k):
        return self
    def __iter__(self):
        return iter([])
    def __getitem__(self, key):
        return self
    def __setitem__(self, key, value):
        pass
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
    def __bool__(self):
        return False
    def __len__(self):
        return 0
    def __contains__(self, item):
        return False
    def __str__(self):
        return '<Dummy>'
    def __repr__(self):
        return '<Dummy>'

# Dinamik olarak eksik attribute'ları Dummy ile karşılayan modül wrapper

# Dinamik DummyModule: Her attribute isteğinde DummyModule veya Dummy döndürür
class DummyModule(types.ModuleType):
    def __getattr__(self, name):
        if name[0].isupper():
            d = make_dummy_type(name)
            setattr(self, name, d)
            return d
        mod_name = self.__name__ + '.' + name
        m = DummyModule(mod_name)
        sys.modules[mod_name] = m
        setattr(self, name, m)
        return m
    def __iter__(self):
        return iter([])

# Tüm renpy modül zincirini DummyModule ile başlat
sys.modules['renpy'] = DummyModule('renpy')
sys.modules['renpy.ast'] = DummyModule('renpy.ast')
sys.modules['renpy.sl2'] = DummyModule('renpy.sl2')
sys.modules['renpy.sl2.slast'] = DummyModule('renpy.sl2.slast')
sys.modules['renpy.atl'] = DummyModule('renpy.atl')

# AST'de olabilecek bazı sınıfları baştan ekle (hızlı erişim için)
ast_classes = [
    'Dialogue', 'Say', 'Menu', 'Label', 'Screen', 'Python', 'Jump', 'Translate', 'If', 'While', 'With',
    'UserStatement', 'Block', 'Image', 'Show', 'Hide', 'Scene', 'Call', 'Return', 'Define', 'Default',
    'Transform', 'Style', 'Config', 'Store', 'DynamicCharacter', 'Text', 'RawBlock', 'ATLTransform',
    'ArgumentInfo', 'ParameterInfo', 'PostUserStatement', 'TranslateSay', 'NVL', 'Voice', 'Choice',
]
for cls in ast_classes:
    setattr(sys.modules['renpy.ast'], cls, Dummy())
    setattr(sys.modules['renpy.sl2.slast'], cls, Dummy())
    setattr(sys.modules['renpy.atl'], cls, Dummy())

def make_dummy_type(name):
    return type(name, (Dummy,), {})

for cls in ast_classes:
    dummy_type = make_dummy_type(cls)
    setattr(sys.modules['renpy.ast'], cls, dummy_type)
    setattr(sys.modules['renpy.sl2.slast'], cls, dummy_type)
    setattr(sys.modules['renpy.atl'], cls, dummy_type)

def analyze_rpymc_ast(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    if not data.startswith(b'RENPY'):
        print('Unknown header or not RENPY format')
        return
    header_len = data.find(b'\x78')
    if header_len == -1:
        print('Zlib header not found')
        return
    try:
        zdata = data[header_len:]
        decompressed = zlib.decompress(zdata)
    except Exception as e:
        print(f'Zlib decompress error: {e}')
        return
    # Eksik modül hatası için tekrar deneme mekanizması
    import re
    max_attempts = 20
    for attempt in range(max_attempts):
        try:
            ast = pickle.loads(decompressed)
            break
        except ModuleNotFoundError as e:
            m = re.search(r"No module named '([^']+)'", str(e))
            if m:
                modname = m.group(1)
                sys.modules[modname] = DummyModule(modname)
                print(f'Auto-added DummyModule for missing: {modname}')
                continue
            else:
                print(f'Unpickle error: {e}')
                return
        except Exception as e:
            print(f'Unpickle error: {e}')
            return
    else:
        print('Unpickle error: Too many missing modules')
        return
    def walk(node, depth=0, max_depth=3):
        indent = '  ' * depth
        if isinstance(node, str):
            print(f'{indent}str: {repr(node)[:60]}')
        elif isinstance(node, (int, float, bool, type(None))):
            print(f'{indent}{type(node).__name__}: {node}')
        elif isinstance(node, (list, tuple)):
            print(f'{indent}{type(node).__name__} (len={len(node)})')
            if depth < max_depth:
                for item in node[:5]:
                    walk(item, depth+1, max_depth)
                if len(node) > 5:
                    print(f'{indent}  ...')
        elif isinstance(node, dict):
            print(f'{indent}dict (len={len(node)})')
            if depth < max_depth:
                for k, v in list(node.items())[:5]:
                    print(f'{indent}  key: {repr(k)[:30]}')
                    walk(v, depth+1, max_depth)
                if len(node) > 5:
                    print(f'{indent}  ...')
        else:
            print(f'{indent}{type(node).__name__}')
            if hasattr(node, '__dict__') and depth < max_depth:
                for k, v in list(vars(node).items())[:5]:
                    print(f'{indent}  attr: {k}')
                    walk(v, depth+1, max_depth)
                if len(vars(node)) > 5:
                    print(f'{indent}  ...')
    print('AST Root:', type(ast))
    walk(ast)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python analyze_rpymc.py <file.rpymc>')
        sys.exit(1)
    analyze_rpymc_ast(sys.argv[1])
