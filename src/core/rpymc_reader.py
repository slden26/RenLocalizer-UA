import collections
import io
import pickle
import sys
import types
import zlib

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
class RpymcUnpickler(pickle.Unpickler):
    """Restricted unpickler to avoid executing arbitrary globals from rpymc files."""

    SAFE_BUILTINS = {
        ("builtins", "set"): set,
        ("builtins", "frozenset"): frozenset,
        ("builtins", "dict"): dict,
        ("builtins", "list"): list,
        ("builtins", "tuple"): tuple,
        ("builtins", "str"): str,
        ("builtins", "int"): int,
        ("builtins", "float"): float,
        ("builtins", "bool"): bool,
        ("collections", "defaultdict"): collections.defaultdict,
        ("__builtin__", "set"): set,
        ("__builtin__", "frozenset"): frozenset,
    }

    ALLOWED_PREFIXES = ("renpy.", "store.")
    ALLOWED_MODULES = {"renpy", "store"}

    def find_class(self, module, name):
        key = (module, name)

        if key in self.SAFE_BUILTINS:
            return self.SAFE_BUILTINS[key]

        if module in self.ALLOWED_MODULES or module.startswith(self.ALLOWED_PREFIXES):
            # Return dummy types/modules to satisfy references without executing code
            if module not in sys.modules:
                sys.modules[module] = DummyModule(module)
            mod = sys.modules[module]
            attr = getattr(mod, name, None)
            if attr is None:
                attr = make_dummy_type(name) if name and name[0].isupper() else Dummy
                setattr(mod, name, attr)
            return attr

        raise pickle.UnpicklingError(f"Disallowed global: {module}.{name}")

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
    return RpymcUnpickler(io.BytesIO(decompressed)).load()
