import os
import sys
import copy
from pathlib import Path

# Add repo root to sys.path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import importlib.util
import types

# Load parser module without importing top-level src which requires heavy deps
PARSER_PATH = project_root / 'src' / 'core' / 'parser.py'
spec = importlib.util.spec_from_file_location('src.core.parser', str(PARSER_PATH))
parser_module = importlib.util.module_from_spec(spec)
sys.modules['src'] = types.ModuleType('src')
sys.modules['src.core'] = types.ModuleType('src.core')
sys.modules['src.core.parser'] = parser_module
spec.loader.exec_module(parser_module)
RenPyParser = getattr(parser_module, 'RenPyParser')

# Load simple ConfigManager via importlib
CONFIG_PATH = project_root / 'src' / 'utils' / 'config.py'
spec2 = importlib.util.spec_from_file_location('src.utils.config', str(CONFIG_PATH))
config_module = importlib.util.module_from_spec(spec2)
sys.modules['src.utils'] = types.ModuleType('src.utils')
sys.modules['src.utils.config'] = config_module
spec2.loader.exec_module(config_module)
ConfigManager = getattr(config_module, 'ConfigManager')

# Load translation_pipeline similarly (only for calling _run_translate_command)
PIPELINE_PATH = project_root / 'src' / 'core' / 'translation_pipeline.py'
spec3 = importlib.util.spec_from_file_location('src.core.translation_pipeline', str(PIPELINE_PATH))
pipeline_module = importlib.util.module_from_spec(spec3)
sys.modules['src.core.translation_pipeline'] = pipeline_module
# To avoid importing top-level src, inject minimal modules for dependencies
sys.modules['src.utils.unren_manager'] = types.ModuleType('src.utils.unren_manager')
sys.modules['src.core.tl_parser'] = types.ModuleType('src.core.tl_parser')
sys.modules['src.core.translator'] = types.ModuleType('src.core.translator')
# Provide minimal sdk_finder module used in pipeline
sdk_finder_mod = types.ModuleType('src.utils.sdk_finder')
def find_renpy_sdks(custom_paths=None):
    return []
sdk_finder_mod.find_renpy_sdks = find_renpy_sdks
sys.modules['src.utils.sdk_finder'] = sdk_finder_mod
# Add a minimal UnRenManager stub
unren_mod = sys.modules['src.utils.unren_manager']
class UnRenManager:
    def __init__(self, conf=None):
        pass
    def is_available(self):
        return True
    def ensure_available(self):
        return True
    def get_unren_root(self):
        return None
    def verify_installation(self):
        return {}
    def run_unren(self, project_path_obj, variant='auto', wait=True, log_callback=None, automation_script=None, timeout=600):
        class P: returncode = 0
        return P()
unren_mod.UnRenManager = UnRenManager

# Add a minimal TLParser stub
tl_parser_mod = sys.modules['src.core.tl_parser']
class TLParser:
    def parse_directory(self, path, lang=None):
        return []
    def parse_directory_parallel(self, directory):
        return {}
    def save_translations(self, tl_file, translations):
        return True
class TranslationFile:
    def __init__(self):
        self.entries = []
    def get_untranslated(self):
        return []
class TranslationEntry:
    def __init__(self, original_text=''):
        self.original_text = original_text
def get_translation_stats(files):
    return {'translated': 0, 'untranslated': 0}
tl_parser_mod.TLParser = TLParser
tl_parser_mod.TranslationFile = TranslationFile
tl_parser_mod.TranslationEntry = TranslationEntry
tl_parser_mod.get_translation_stats = get_translation_stats

# Minimal translator stubs
translator_mod = sys.modules['src.core.translator']
class TranslationManager:
    def __init__(self):
        pass
    def set_proxy_enabled(self, v):
        pass
    async def translate_batch(self, requests):
        return []
class TranslationRequest:
    def __init__(self, text='', source_lang='', target_lang='', engine=None, metadata=None):
        self.text = text
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.engine = engine
        self.metadata = metadata or {}
class TranslationEngine:
    GOOGLE = 'google'
translator_mod.TranslationManager = TranslationManager
translator_mod.TranslationRequest = TranslationRequest
translator_mod.TranslationEngine = TranslationEngine

# Provide dummy PyQt6/PySide6 QtCore modules to avoid dependency on GUI libs in tests
qtcore = types.ModuleType('PyQt6.QtCore')
class QObject:
    def __init__(self, *args, **kwargs):
        pass
class QThread:
    def __init__(self, *args, **kwargs):
        pass
def pyqtSignal(*args, **kwargs):
    return None
qtcore.QObject = QObject
qtcore.QThread = QThread
qtcore.pyqtSignal = pyqtSignal
sys.modules['PyQt6.QtCore'] = qtcore
sys.modules['PySide6.QtCore'] = qtcore
spec3.loader.exec_module(pipeline_module)
TranslationPipeline = getattr(pipeline_module, 'TranslationPipeline')

# Define a dummy translation manager with minimal API to satisfy pipeline constructor
class DummyTranslationManager:
    def set_proxy_enabled(self, v):
        pass
    def translate_batch(self, requests):
        # Return empty list as no real translation is executed during generation
        async def runner():
            return []
        import asyncio
        return asyncio.sleep(0, result=[])


def create_rpy_with_text(path: Path, filename: str, text: str, type: str = 'ui'):
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / filename
    if type == 'ui':
        file_path.write_text(f'screen test:\n    text "{text}"\n', encoding='utf-8')
    else:
        file_path.write_text(f'label start:\n    "{text}"\n', encoding='utf-8')
    return file_path


def test_project_common_force_ui(tmp_path):
    # Create a fake game project with a renpy/common UI string
    game_dir = tmp_path / 'game'
    renpy_common = game_dir / 'renpy' / 'common'
    renpy_common.mkdir(parents=True, exist_ok=True)
    create_rpy_with_text(renpy_common, '00common.rpy', 'Do you really want to quit?')

    # Config: translate_ui disabled but include_engine_common enabled
    conf = ConfigManager()
    conf.translation_settings.translate_ui = False
    conf.translation_settings.include_engine_common = True

    # Instantiate pipeline and run only _run_translate_command
    pipeline = TranslationPipeline(conf, DummyTranslationManager())
    # Provide dummy signals with emit method to avoid AttributeError
    class DummySignalObj:
        def emit(self, *args, **kwargs):
            return None
    pipeline.log_message = DummySignalObj()
    pipeline.stage_changed = DummySignalObj()
    pipeline.progress_updated = DummySignalObj()
    pipeline.finished = DummySignalObj()
    pipeline.show_warning = DummySignalObj()
    pipeline.game_exe_path = str(game_dir / 'dummy.exe')
    pipeline.project_path = str(tmp_path)
    pipeline.target_language = 'turkish'

    # Make sure tl dir doesn't exist
    tl_dir = os.path.join(str(game_dir), 'tl', pipeline.target_language)
    if os.path.isdir(tl_dir):
        import shutil
        shutil.rmtree(tl_dir)

    success = pipeline._run_translate_command(str(tmp_path))
    assert success

    strings_path = os.path.join(tl_dir, 'strings.rpy')
    assert os.path.exists(strings_path)

    content = open(strings_path, 'r', encoding='utf-8').read()
    assert 'Do you really want to quit?' in content
    assert '[engine_common]' in content
