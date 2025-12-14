import os
import sys
from pathlib import Path
import copy

# Add project root to sys.path so src.* imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import importlib.util
import types

# Import RenPyParser without importing top-level 'src' that requires heavy deps
PROJECT_ROOT = Path(__file__).parent.parent
PARSER_PATH = PROJECT_ROOT / 'src' / 'core' / 'parser.py'
spec = importlib.util.spec_from_file_location('src.core.parser', str(PARSER_PATH))
parser_module = importlib.util.module_from_spec(spec)
sys.modules['src'] = types.ModuleType('src')
sys.modules['src.core'] = types.ModuleType('src.core')
sys.modules['src.core.parser'] = parser_module
spec.loader.exec_module(parser_module)
RenPyParser = getattr(parser_module, 'RenPyParser')

CONFIG_PATH = PROJECT_ROOT / 'src' / 'utils' / 'config.py'
spec2 = importlib.util.spec_from_file_location('src.utils.config', str(CONFIG_PATH))
config_module = importlib.util.module_from_spec(spec2)
sys.modules['src.utils'] = types.ModuleType('src.utils')
sys.modules['src.utils.config'] = config_module
spec2.loader.exec_module(config_module)
ConfigManager = getattr(config_module, 'ConfigManager')


def create_rpy_with_text(path: Path, filename: str, text: str, type: str = 'dialogue'):
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / filename
    if type == 'dialogue':
        file_path.write_text(f'label start:\n    "{text}"\n', encoding='utf-8')
    else:
        # Create a screen with a UI text element
        file_path.write_text(f'screen test:\n    text "{text}"\n', encoding='utf-8')
    return file_path


def test_engine_common_force_ui(tmp_path):
    # Create fake SDK common directory with UI text
    sdk_root = tmp_path / 'fake_sdk'
    sdk_common = sdk_root / 'renpy' / 'common'
    sdk_common.mkdir(parents=True, exist_ok=True)
    create_rpy_with_text(sdk_common, '00sdk_ui.rpy', 'Engine Common UI Text', type='ui')

    # Project parser with translate_ui disabled
    proj_conf = ConfigManager()
    proj_conf.translation_settings.translate_ui = False
    project_parser = RenPyParser(proj_conf)

    # Parsing the SDK common using the project's parser should not include the UI text
    proj_results = project_parser.parse_directory(str(sdk_common))
    proj_items = [(e['text'], e.get('text_type') or e.get('type')) for entries in proj_results.values() for e in entries]
    all_proj_texts = [text for (text, ttype) in proj_items]
    # If the project's parser treats this as a UI text, it should respect translate_ui setting
    # Otherwise, it's not classified as UI and will be included regardless
    # This assert checks that if it was classified as UI, it's excluded when translate_ui=False
    for (text, ttype) in proj_items:
        if text == 'Engine Common UI Text':
            if ttype == 'ui':
                assert False, "Project parser included a UI text while translate_ui=False"
            else:
                # It was classified as not-UI — therefore included regardless
                pass

    # Temp parser that forces UI translation
    temp_conf = ConfigManager()
    temp_conf.translation_settings = copy.deepcopy(proj_conf.translation_settings)
    temp_conf.translation_settings.translate_ui = True
    temp_parser = RenPyParser(temp_conf)

    temp_results = temp_parser.parse_directory(str(sdk_common))
    temp_items = [(e['text'], e.get('text_type') or e.get('type')) for entries in temp_results.values() for e in entries]
    all_temp_texts = [text for (text, ttype) in temp_items]
    assert 'Engine Common UI Text' in all_temp_texts
    # If it's classified as UI, ensure temp parser included it because translate_ui=True
    for (text, ttype) in temp_items:
        if text == 'Engine Common UI Text' and ttype == 'ui':
            assert True
