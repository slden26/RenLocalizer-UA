import pytest
import importlib.util
import importlib.machinery
from pathlib import Path


def load_output_formatter_module():
    path = Path(__file__).parent.parent / 'src' / 'core' / 'output_formatter.py'
    loader = importlib.machinery.SourceFileLoader('src.core.output_formatter', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module

ofm = load_output_formatter_module()
RenPyOutputFormatter = ofm.RenPyOutputFormatter


def test_skip_file_extensions_do_not_contain_data_files():
    fmt = RenPyOutputFormatter()
    skip_exts = set(fmt.SKIP_FILE_EXTENSIONS)
    # Ensure JSON/XML/TXT/CSV aren't automatically skipped
    assert '.json' not in skip_exts
    assert '.xml' not in skip_exts
    assert '.txt' not in skip_exts
    assert '.csv' not in skip_exts
