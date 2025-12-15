import os
import sys
from pathlib import Path
import pytest

# Make project root importable as 'src'
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import importlib.util
import types

PROJECT_ROOT = project_root
PARSER_PATH = PROJECT_ROOT / 'src' / 'core' / 'parser.py'

sys.modules['src'] = types.ModuleType('src')
sys.modules['src.core'] = types.ModuleType('src.core')
spec = importlib.util.spec_from_file_location('src.core.parser', str(PARSER_PATH))
parser_module = importlib.util.module_from_spec(spec)
# Ensure module path exists so dataclasses and other internals resolve correctly
sys.modules['src.core.parser'] = parser_module
spec.loader.exec_module(parser_module)
RenPyParser = getattr(parser_module, 'RenPyParser')


def create_rpy_with_text(path: Path, filename: str, text: str):
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / filename
    file_path.write_text(f"label start:\n    \"{text}\"\n", encoding='utf-8')
    return file_path


def test_parse_renpy_sdk_common(tmp_path, monkeypatch):
    # Setup fake SDK directory
    sdk_root = tmp_path / 'fake_sdk'
    common_dir = sdk_root / 'renpy' / 'common'
    create_rpy_with_text(common_dir, '00sdk_common.rpy', 'Engine Common Text')

    # We only test parser.parse_directory on the SDK common directory

    # Parse SDK common using the parser
    parser = RenPyParser()
    results = parser.parse_directory(str(common_dir))

    # There should be at least one file parsed and contain our text
    texts = [e['text'] for entries in results.values() for e in entries]
    assert 'Engine Common Text' in texts
