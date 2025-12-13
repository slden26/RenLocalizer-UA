from src.utils.config import ConfigManager
from src.utils.unren_manager import UnRenManager
m = UnRenManager(ConfigManager())
print(m.verify_installation())
