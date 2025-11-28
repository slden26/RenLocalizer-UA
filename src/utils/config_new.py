"""
Configuration Manager
====================

Manages application settings and configuration.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class Language(Enum):
    """Supported UI languages."""
    TURKISH = "tr"
    ENGLISH = "en"

@dataclass
class TranslationSettings:
    """Translation-related settings."""
    source_language: str = "auto"
    target_language: str = "tr"
    max_concurrent_threads: int = 32
    request_delay: float = 0.1
    max_batch_size: int = 100
    enable_proxy: bool = True
    max_retries: int = 3
    timeout: int = 30

@dataclass
class ApiKeys:
    """API keys for various translation services."""
    google_api_key: str = ""
    deepl_api_key: str = ""
    bing_api_key: str = ""
    yandex_api_key: str = ""

@dataclass
class AppSettings:
    """General application settings."""
    ui_language: str = Language.TURKISH.value
    theme: str = "solarized"  # Varsayılan tema solarized olarak ayarlandı
    window_width: int = 1200
    window_height: int = 800
    last_input_directory: str = ""
    last_output_directory: str = ""
    auto_save_settings: bool = True
    auto_save_translations: bool = True
    check_for_updates: bool = True
    # Output format: 'simple' (current) or 'old_new' (Ren'Py official old/new blocks)
    output_format: str = "simple"
    # Parser workers for parallel file processing
    parser_workers: int = 4

@dataclass
class ProxySettings:
    """Proxy-related settings."""
    enabled: bool = True
    auto_rotate: bool = True
    test_on_startup: bool = True
    update_interval: int = 3600  # seconds
    max_failures: int = 10
    custom_proxies: list = None
    
    def __post_init__(self):
        if self.custom_proxies is None:
            self.custom_proxies = []

class ConfigManager:
    """Manages application configuration."""
    
    def __init__(self, config_file: str = "config.json"):
        self.logger = logging.getLogger(__name__)
        self.config_file = Path(config_file)
        self.locales_dir = Path("locales")
        
        # Default configuration
        self.translation_settings = TranslationSettings()
        self.api_keys = ApiKeys()
        self.app_settings = AppSettings()
        self.proxy_settings = ProxySettings()
        
        # Load language files
        self._language_data = {}
        self._load_language_files()
        
        # Load existing configuration
        self.load_config()
    
    def _load_language_files(self):
        """Load language JSON files from locales directory."""
        try:
            # Load Turkish
            tr_file = self.locales_dir / "turkish.json"
            if tr_file.exists():
                with open(tr_file, 'r', encoding='utf-8') as f:
                    self._language_data['tr'] = json.load(f)
            
            # Load English
            en_file = self.locales_dir / "english.json"
            if en_file.exists():
                with open(en_file, 'r', encoding='utf-8') as f:
                    self._language_data['en'] = json.load(f)
                    
            self.logger.info(f"Loaded {len(self._language_data)} language files")
        except Exception as e:
            self.logger.warning(f"Could not load language files: {e}")
            # Fallback to embedded translations if JSON files fail
            self._language_data = self._get_fallback_translations()
    
    def _get_fallback_translations(self) -> Dict[str, Dict[str, Any]]:
        """Fallback translations if JSON files are not available."""
        return {
            'tr': {
                'app_title': 'RenLocalizer V2',
                'file_menu': 'Dosya',
                'help_menu': 'Yardım',
                'about': 'Hakkında',
                'info': 'Bilgi',
                'info_dialog': {
                    'title': 'Program Bilgi Merkezi',
                    'tabs': {
                        'formats': 'Çıktı Formatları'
                    }
                }
            },
            'en': {
                'app_title': 'RenLocalizer V2',
                'file_menu': 'File',
                'help_menu': 'Help',
                'about': 'About',
                'info': 'Info',
                'info_dialog': {
                    'title': 'Program Information Center',
                    'tabs': {
                        'formats': 'Output Formats'
                    }
                }
            }
        }
    
    def load_config(self) -> bool:
        """Load configuration from file."""
        try:
            if not self.config_file.exists():
                self.logger.info("Config file doesn't exist, using defaults")
                return False
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Load translation settings
            if 'translation_settings' in config_data:
                trans_data = config_data['translation_settings']
                self.translation_settings = TranslationSettings(**trans_data)
            
            # Load API keys
            if 'api_keys' in config_data:
                api_data = config_data['api_keys']
                self.api_keys = ApiKeys(**api_data)
            
            # Load app settings
            if 'app_settings' in config_data:
                app_data = config_data['app_settings']
                self.app_settings = AppSettings(**app_data)
            
            # Load proxy settings
            if 'proxy_settings' in config_data:
                proxy_data = config_data['proxy_settings']
                self.proxy_settings = ProxySettings(**proxy_data)
            
            self.logger.info("Configuration loaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            return False
    
    def save_config(self, app_settings: Optional[AppSettings] = None) -> bool:
        """Save configuration to file."""
        try:
            # If specific settings provided, update our instance
            if app_settings is not None:
                self.app_settings = app_settings
            
            config_data = {
                'translation_settings': asdict(self.translation_settings),
                'api_keys': asdict(self.api_keys),
                'app_settings': asdict(self.app_settings),
                'proxy_settings': asdict(self.proxy_settings)
            }
            
            # Create backup if file exists
            if self.config_file.exists():
                backup_file = self.config_file.with_suffix('.json.bak')
                # Remove existing backup if it exists
                if backup_file.exists():
                    try:
                        backup_file.unlink()
                    except OSError as e:
                        self.logger.warning(f"Could not remove existing backup: {e}")
                # Create new backup
                try:
                    self.config_file.rename(backup_file)
                except OSError as e:
                    self.logger.warning(f"Could not create backup: {e}")
                    # If backup fails, continue without backup
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            
            self.logger.info("Configuration saved successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
            return False
    
    def get_api_key(self, service: str) -> str:
        """Get API key for a service."""
        return getattr(self.api_keys, f"{service}_api_key", "")
    
    def set_api_key(self, service: str, api_key: str) -> None:
        """Set API key for a service."""
        setattr(self.api_keys, f"{service}_api_key", api_key)
        if self.app_settings.auto_save_settings:
            self.save_config()
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value using dot notation (e.g., 'ui.theme')."""
        try:
            parts = key.split('.')
            if len(parts) == 2:
                section, setting = parts
                if section == 'ui' or section == 'app':
                    return getattr(self.app_settings, setting, default)
                elif section == 'translation':
                    return getattr(self.translation_settings, setting, default)
                elif section == 'proxy':
                    return getattr(self.proxy_settings, setting, default)
            return default
        except Exception:
            return default
    
    def set_setting(self, key: str, value: Any) -> None:
        """Set a setting value using dot notation (e.g., 'ui.theme')."""
        try:
            parts = key.split('.')
            if len(parts) == 2:
                section, setting = parts
                if section == 'ui' or section == 'app':
                    setattr(self.app_settings, setting, value)
                elif section == 'translation':
                    setattr(self.translation_settings, setting, value)
                elif section == 'proxy':
                    setattr(self.proxy_settings, setting, value)
                
                if self.app_settings.auto_save_settings:
                    self.save_config()
        except Exception as e:
            self.logger.error(f"Error setting {key} to {value}: {e}")
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get supported language codes and names."""
        return {
            'auto': 'Auto Detect',
            'en': 'English',
            'tr': 'Turkish',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ru': 'Russian',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh': 'Chinese (Simplified)',
            'zh-tw': 'Chinese (Traditional)',
            'ar': 'Arabic',
            'hi': 'Hindi',
            'th': 'Thai',
            'vi': 'Vietnamese',
            'pl': 'Polish',
            'nl': 'Dutch',
            'sv': 'Swedish',
            'da': 'Danish',
            'no': 'Norwegian',
            'fi': 'Finnish'
        }
    
    def get_ui_translations(self) -> Dict[str, Dict[str, Any]]:
        """Get UI translations for supported languages from JSON files."""
        return self._language_data
    
    def get_ui_text(self, key: str) -> str:
        """Get UI text in current language with support for nested keys."""
        translations = self.get_ui_translations()
        current_lang = self.app_settings.ui_language
        
        # Support for nested keys like 'info_dialog.title'
        def get_nested_value(data: Dict, key_path: str) -> str:
            keys = key_path.split('.')
            value = data
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return None
            return value if isinstance(value, str) else None
        
        # Try current language first
        if current_lang in translations:
            value = get_nested_value(translations[current_lang], key)
            if value:
                return value
        
        # Fallback to English
        if 'en' in translations:
            value = get_nested_value(translations['en'], key)
            if value:
                return value
        
        # Fallback to key itself
        return key
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self.translation_settings = TranslationSettings()
        self.api_keys = ApiKeys()
        self.app_settings = AppSettings()
        self.proxy_settings = ProxySettings()
        self.logger.info("Configuration reset to defaults")
