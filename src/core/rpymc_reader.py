import sys
import types
import zlib
import pickle
import re

# --- Güvenli Dummy ve DummyModule tanımları ---
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

def make_dummy_type(name):
    return type(name, (Dummy,), {})

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

# --- Otomatik eksik modül ekleyici ---
class AutoDummyImporter:
    def find_spec(self, fullname, path, target=None):
        if fullname not in sys.modules:
            sys.modules[fullname] = DummyModule(fullname)
        return None

sys.meta_path.insert(0, AutoDummyImporter())

# --- AST extraction fonksiyonu ---
def extract_rpymc_ast(file_path, ast_classes=None, max_attempts=20):
    if ast_classes is None:
        ast_classes = [
            'Dialogue', 'Say', 'Menu', 'Label', 'Screen', 'Python', 'Jump', 'Translate', 'If', 'While', 'With',
            'UserStatement', 'Block', 'Image', 'Show', 'Hide', 'Scene', 'Call', 'Return', 'Define', 'Default',
            'Transform', 'Style', 'Config', 'Store', 'DynamicCharacter', 'Text', 'RawBlock', 'ATLTransform',
            'ArgumentInfo', 'ParameterInfo', 'PostUserStatement', 'TranslateSay', 'NVL', 'Voice', 'Choice',
        ]
    # AST sınıflarını Dummy type ile doldur
    for cls in ast_classes:
        dummy_type = make_dummy_type(cls)
        for mod in ['renpy.ast', 'renpy.sl2.slast', 'renpy.atl']:
            if mod not in sys.modules:
                sys.modules[mod] = DummyModule(mod)
            setattr(sys.modules[mod], cls, dummy_type)
    with open(file_path, 'rb') as f:
        data = f.read()
    if not data.startswith(b'RENPY'):
        raise ValueError('Unknown header or not RENPY format')
    header_len = data.find(b'\x78')
    if header_len == -1:
        raise ValueError('Zlib header not found')
    zdata = data[header_len:]
    decompressed = zlib.decompress(zdata)
    for attempt in range(max_attempts):
        try:
            ast = pickle.loads(decompressed)
            return ast
        except ModuleNotFoundError as e:
            m = re.search(r"No module named '([^']+)'", str(e))
            if m:
                modname = m.group(1)
                sys.modules[modname] = DummyModule(modname)
                continue
            else:
                raise
        except Exception as e:
            raise
    raise RuntimeError('Too many missing modules while unpickling')
