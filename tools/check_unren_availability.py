from src.utils.config import ConfigManager
from src.utils.unren_manager import UnRenManager
from pathlib import Path
import sys
c = ConfigManager()
manager = UnRenManager(c)
print('Cache dir:', manager.get_cache_dir())
print('Custom path:', manager.get_custom_path())
root = manager.get_unren_root()
print('UnRen root:', root)
print('Is available:', manager.is_available())
if root:
    print('Scripts found:')
    for p in list(Path(root).glob('**/*.bat')):
        print(' -', p)

# Quick run test
try:
    print('\nAttempting to run UnRen (non-automatic, no wait)')
    p = manager.run_unren(Path('examples'), wait=False)
    print('Launched, PID:', p.pid)
except Exception as e:
    print('Failed to launch UnRen:', e)
    sys.exit(2)

print('All tests passed')
