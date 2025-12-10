from src.utils.config import ConfigManager
from src.utils.unren_manager import UnRenManager
from pathlib import Path
c = ConfigManager()
m = UnRenManager(c)
project = Path('examples')
print('Run available? ', m.is_available())
script = '1\r\n'+'y\r\n'+'y\r\n'+'2\r\n'+'n\r\n'+'x\r\n'
try:
    proc = m.run_unren(project, variant='auto', wait=True, log_callback=lambda s: print('[UNREN]', s), automation_script=script, timeout=30)
    print('Process return code:', proc.returncode)
except Exception as e:
    import traceback
    traceback.print_exc()
