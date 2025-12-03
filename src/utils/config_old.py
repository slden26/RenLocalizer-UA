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
    
    def get_ui_translations(self) -> Dict[str, Dict[str, str]]:
        """Get UI translations for supported languages from JSON files."""
        return {
            'en': {
                'app_title': 'RenLocalizer V2',
                'file_menu': 'File',
                'open_directory': 'Open Directory',
                'save_translations': 'Save Translations',
                'exit': 'Exit',
                'edit_menu': 'Edit',
                'settings': 'Settings',
                'api_keys': 'API Keys',
                'help_menu': 'Help',
                'about': 'About',
                'info': 'Info',
                'view_menu': 'View',
                'theme_menu': 'Theme',
                'dark_theme': 'Dark Theme',
                'solarized_theme': 'Eye-Friendly Theme',
                'source_language': 'Source Language',
                'target_language': 'Target Language',
                'translation_engine': 'Translation Engine',
                'start_translation': 'Start Translation',
                'stop_translation': 'Stop Translation',
                'progress': 'Progress',
                'status': 'Status',
                'ready': 'Ready',
                'translating': 'Translating...',
                'completed': 'Completed',
                'error': 'Error',
                'files_found': 'Files Found',
                'texts_extracted': 'Texts Extracted',
                'translations_completed': 'Translations Completed',
                'output_directory': 'Output Directory',
                'browse': 'Browse',
                'proxy_enabled': 'Enable Proxy',
                'concurrent_threads': 'Concurrent Threads',
                'batch_size': 'Batch Size',
                'request_delay': 'Request Delay (ms)',
                # GUI sections
                'input_section': 'Input',
                'translation_settings': 'Translation Settings',
                'advanced_settings': 'Advanced Settings',
                'directory_label': 'Directory:',
                'directory_placeholder': 'Select folder containing .rpy files',
                'source_lang_label': 'Source Language:',
                'target_lang_label': 'Target Language:',
                'translation_engine_label': 'Translation Engine:',
                'concurrent_threads_label': 'Concurrent Threads:',
                'batch_size_label': 'Batch Size:',
                'request_delay_label': 'Request Delay:',
                'proxy_enabled_label': 'Enable Proxy:',
                # Tab labels
                'extracted_texts_tab': 'Extracted Texts',
                'translation_results_tab': 'Translation Results',
                'log_tab': 'Log',
                # Tree headers
                'text_header': 'Text',
                'type_header': 'Type',
                'file_header': 'File',
                'line_header': 'Line',
                'original_header': 'Original',
                'translated_header': 'Translated',
                'engine_header': 'Engine',
                'status_header': 'Status',
                # Status bar
                'files_status': 'Files: {count}',
                'texts_status': 'Texts: {count}',
                'translations_status': 'Translations: {count}',
                # Messages
                'select_directory_title': 'Select Directory with .rpy files',
                'scanning_directory': 'Scanning directory...',
                'directory_scanned': 'Directory scanned',
                'error_scanning_directory': 'Error scanning directory',
                'starting_translation': 'Starting translation...',
                'stopping': 'Stopping...',
                'translation_completed': 'Translation completed',
                'auto_save_question': 'Would you like to save the translations?',
                'auto_saved': 'Auto-saved',
                'auto_save_success': 'Auto-saved {count} translation files to {directory}',
                'auto_save_error': 'Auto-Save Error',
                'auto_save_error_message': 'Failed to auto-save translations: {error}\n\nPlease save manually.',
                'warning': 'Warning',
                'no_texts_warning': 'No texts to translate. Please select a directory first.',
                'translation_error': 'Translation Error',
                'success': 'Success',
                'failed': 'Failed',
                'no_translations_warning': 'No translations to save.',
                'select_output_directory': 'Select Output Directory',
                'translations_saved': 'Translations saved to {count} files in {directory}',
                'error_saving': 'Error saving translations: {error}',
                'about_title': 'About RenLocalizer V2',
                'about_content': '''<h3>RenLocalizer V2</h3>
<p>Advanced multi-engine translation tool for Ren'Py games.</p>
<p><b>Features:</b></p>
<ul>
<li>Multi-engine translation support</li>
<li>Automatic proxy rotation</li>
<li>Batch processing</li>
<li>Modern user interface</li>
<li>UTF-8 Ren'Py format output</li>
</ul>
<p><b>Version:</b> 2.0.1</p>
<p><b>Framework:</b> {framework}</p>
<p>© 2025 RenLocalizer Team</p>''',
                'info_title': 'Output Format Information',
                'info_content': '''<h3>Translation File Formats</h3>
<p>RenLocalizer V2 supports two output formats for Ren'Py translation files:</p>

<h4>🟦 SIMPLE Format (Default)</h4>
<p><b>Characteristics:</b></p>
<ul>
<li>Clean and readable syntax</li>
<li>Original text in comments</li>
<li>Fewer lines of code</li>
<li>Ideal for manual editing</li>
<li>Compatible with modern Ren'Py (7.0+)</li>
</ul>
<p><b>Example:</b></p>
<pre>translate tr hello_world:
    # "Hello, world!"
    "Merhaba, dünya!"</pre>

<h4>🟩 OLD_NEW Format (Official)</h4>
<p><b>Characteristics:</b></p>
<ul>
<li>Official Ren'Py export format</li>
<li>Compatible with all Ren'Py versions (6.0+)</li>
<li>Explicit old/new text separation</li>
<li>Full compatibility with Ren'Py tools</li>
<li>More structured approach</li>
</ul>
<p><b>Example:</b></p>
<pre>translate tr hello_world:
    old "Hello, world!"
    new "Merhaba, dünya!"</pre>

<h4>💡 Which to Choose?</h4>
<p><b>SIMPLE:</b> Modern projects, manual editing, clean output</p>
<p><b>OLD_NEW:</b> Legacy projects, official tools, maximum compatibility</p>

<p><b>Note:</b> Both formats work perfectly in Ren'Py engine. The difference is only in syntax style and readability.</p>

<p>You can change the output format in Settings → General → Output Format.</p>''',
                # Settings dialog
                'general_tab': 'General',
                'translation_tab': 'Translation',
                'proxy_tab': 'Proxy',
                'advanced_tab': 'Advanced',
                'ui_language_label': 'UI Language:',
                'theme_label': 'Theme:',
                'auto_save_label': 'Auto Save Settings:',
                'auto_save_translations_label': 'Auto Save Translations:',
                'check_updates_label': 'Check for Updates:',
                'window_size_group': 'Window Size',
                'width_label': 'Width:',
                'height_label': 'Height:',
                'default_languages_group': 'Default Languages',
                'performance_group': 'Performance',
                'max_threads_label': 'Max Concurrent Threads:',
                'max_batch_label': 'Max Batch Size:',
                'request_delay_setting_label': 'Request Delay:',
                'retry_settings_group': 'Retry Settings',
                'max_retries_label': 'Max Retries:',
                'timeout_label': 'Timeout:',
                'enable_proxy_label': 'Enable Proxy:',
                'auto_rotate_label': 'Auto Rotate Proxies:',
                'test_startup_label': 'Test Proxies on Startup:',
                'update_interval_label': 'Update Interval:',
                'max_failures_label': 'Max Failures:',
                'custom_proxies_group': 'Custom Proxies',
                'custom_proxies_note': 'Enter custom proxies (one per line, format: host:port)',
                'refresh_proxies_btn': 'Refresh Proxies',
                'proxy_refresh_started': 'Proxy list is being refreshed in background...',
                'proxy_refresh_unavailable': 'Proxy refresh is not available right now',
                'info': 'Information',
                'log_level_label': 'Log Level:',
                'max_log_size_label': 'Max Log File Size:',
                'memory_optimization_group': 'Memory Optimization',
                'chunk_size_label': 'File Chunk Size:',
                'debugging_group': 'Debugging',
                'debug_mode_label': 'Debug Mode:',
                'verbose_logging_label': 'Verbose Logging:'
            },
            'tr': {
                'app_title': 'RenLocalizer V2',
                'file_menu': 'Dosya',
                'open_directory': 'Klasör Aç',
                'save_translations': 'Çevirileri Kaydet',
                'exit': 'Çıkış',
                'edit_menu': 'Düzenle',
                'settings': 'Ayarlar',
                'api_keys': 'API Anahtarları',
                'help_menu': 'Yardım',
                'about': 'Hakkında',
                'info': 'Bilgi',
                'view_menu': 'Görünüm',
                'theme_menu': 'Tema',
                'dark_theme': 'Koyu Tema',
                'solarized_theme': 'Göz Dostu Tema',
                'source_language': 'Kaynak Dil',
                'target_language': 'Hedef Dil',
                'translation_engine': 'Çeviri Motoru',
                'start_translation': 'Çeviriyi Başlat',
                'stop_translation': 'Çeviriyi Durdur',
                'progress': 'İlerleme',
                'status': 'Durum',
                'ready': 'Hazır',
                'translating': 'Çevriliyor...',
                'completed': 'Tamamlandı',
                'error': 'Hata',
                'files_found': 'Bulunan Dosyalar',
                'texts_extracted': 'Çıkarılan Metinler',
                'translations_completed': 'Tamamlanan Çeviriler',
                'output_directory': 'Çıktı Klasörü',
                'browse': 'Gözat',
                'proxy_enabled': 'Proxy Etkin',
                'concurrent_threads': 'Eş Zamanlı Thread',
                'batch_size': 'Batch Boyutu',
                'request_delay': 'İstek Gecikmesi (ms)',
                # GUI sections
                'input_section': 'Giriş',
                'translation_settings': 'Çeviri Ayarları',
                'advanced_settings': 'Gelişmiş Ayarlar',
                'directory_label': 'Klasör:',
                'directory_placeholder': '.rpy dosyalarının bulunduğu klasörü seçin',
                'source_lang_label': 'Kaynak Dil:',
                'target_lang_label': 'Hedef Dil:',
                'translation_engine_label': 'Çeviri Motoru:',
                'concurrent_threads_label': 'Eş Zamanlı Thread:',
                'batch_size_label': 'Batch Boyutu:',
                'request_delay_label': 'İstek Gecikmesi:',
                'proxy_enabled_label': 'Proxy Etkin:',
                # Tab labels
                'extracted_texts_tab': 'Çıkarılan Metinler',
                'translation_results_tab': 'Çeviri Sonuçları',
                'log_tab': 'Log',
                # Tree headers
                'text_header': 'Metin',
                'type_header': 'Tür',
                'file_header': 'Dosya',
                'line_header': 'Satır',
                'original_header': 'Orijinal',
                'translated_header': 'Çevrilmiş',
                'engine_header': 'Motor',
                'status_header': 'Durum',
                # Status bar
                'files_status': 'Dosyalar: {count}',
                'texts_status': 'Metinler: {count}',
                'translations_status': 'Çeviriler: {count}',
                # Messages
                'select_directory_title': '.rpy dosyalarının bulunduğu klasörü seçin',
                'scanning_directory': 'Klasör taranıyor...',
                'directory_scanned': 'Klasör tarandı',
                'error_scanning_directory': 'Klasör taranırken hata',
                'starting_translation': 'Çeviri başlatılıyor...',
                'stopping': 'Durduruluyor...',
                'translation_completed': 'Çeviri tamamlandı',
                'auto_save_question': 'Çevirileri kaydetmek istiyor musunuz?',
                'auto_saved': 'Otomatik kaydedildi',
                'auto_save_success': '{count} çeviri dosyası {directory} konumuna otomatik kaydedildi',
                'auto_save_error': 'Otomatik Kaydetme Hatası',
                'auto_save_error_message': 'Çeviriler otomatik kaydedilemedi: {error}\n\nLütfen manuel olarak kaydedin.',
                'warning': 'Uyarı',
                'no_texts_warning': 'Çevrilecek metin yok. Lütfen önce bir klasör seçin.',
                'translation_error': 'Çeviri Hatası',
                'success': 'Başarılı',
                'failed': 'Başarısız',
                'no_translations_warning': 'Kaydedilecek çeviri yok.',
                'select_output_directory': 'Çıktı Klasörünü Seçin',
                'translations_saved': 'Çeviriler {directory} konumunda {count} dosyaya kaydedildi',
                'error_saving': 'Çeviriler kaydedilirken hata: {error}',
                'about_title': 'RenLocalizer V2 Hakkında',
                'about_content': '''<h3>RenLocalizer V2</h3>
<p>Ren'Py oyunları için gelişmiş çok-motorlu çeviri aracı.</p>
<p><b>Özellikler:</b></p>
<ul>
<li>Çok-motorlu çeviri desteği</li>
<li>Otomatik proxy rotasyonu</li>
<li>Toplu işlem</li>
<li>Modern kullanıcı arayüzü</li>
<li>UTF-8 Ren'Py format çıktısı</li>
</ul>
<p><b>Sürüm:</b> 2.0.0</p>
<p><b>Framework:</b> {framework}</p>
<p>© 2025 RenLocalizer Ekibi</p>''',
                'info_title': 'Çıktı Format Bilgileri',
                'info_content': '''<h3>Çeviri Dosya Formatları</h3>
<p>RenLocalizer V2, Ren'Py çeviri dosyaları için iki çıktı formatını destekler:</p>

<h4>🟦 SIMPLE Format (Varsayılan)</h4>
<p><b>Özellikler:</b></p>
<ul>
<li>Temiz ve okunabilir syntax</li>
<li>Orijinal metin yorumlarda</li>
<li>Daha az kod satırı</li>
<li>Manuel düzenleme için ideal</li>
<li>Modern Ren'Py ile uyumlu (7.0+)</li>
</ul>
<p><b>Örnek:</b></p>
<pre>translate tr hello_world:
    # "Hello, world!"
    "Merhaba, dünya!"</pre>

<h4>🟩 OLD_NEW Format (Resmi)</h4>
<p><b>Özellikler:</b></p>
<ul>
<li>Ren'Py'nin resmi export formatı</li>
<li>Tüm Ren'Py sürümleri ile uyumlu (6.0+)</li>
<li>Eski/yeni metin açık ayrımı</li>
<li>Ren'Py araçları ile tam uyumluluk</li>
<li>Daha yapısal yaklaşım</li>
</ul>
<p><b>Örnek:</b></p>
<pre>translate tr hello_world:
    old "Hello, world!"
    new "Merhaba, dünya!"</pre>

<h4>💡 Hangisini Seçmeli?</h4>
<p><b>SIMPLE:</b> Modern projeler, manuel düzenleme, temiz çıktı</p>
<p><b>OLD_NEW:</b> Eski projeler, resmi araçlar, maksimum uyumluluk</p>

<p><b>Not:</b> Her iki format da Ren'Py motorunda mükemmel çalışır. Fark sadece syntax stili ve okunabilirlikte.</p>

<p>Çıktı formatını Ayarlar → Genel → Çıktı Formatı'ndan değiştirebilirsiniz.</p>''',
                # Settings dialog
                'general_tab': 'Genel',
                'translation_tab': 'Çeviri',
                'proxy_tab': 'Proxy',
                'advanced_tab': 'Gelişmiş',
                'ui_language_label': 'Arayüz Dili:',
                'theme_label': 'Tema:',
                'auto_save_label': 'Otomatik Kaydetme:',
                'auto_save_translations_label': 'Çevirileri Otomatik Kaydet:',
                'check_updates_label': 'Güncellemeleri Kontrol Et:',
                'window_size_group': 'Pencere Boyutu',
                'width_label': 'Genişlik:',
                'height_label': 'Yükseklik:',
                'default_languages_group': 'Varsayılan Diller',
                'performance_group': 'Performans',
                'max_threads_label': 'Maksimum Eş Zamanlı Thread:',
                'max_batch_label': 'Maksimum Batch Boyutu:',
                'request_delay_setting_label': 'İstek Gecikmesi:',
                'retry_settings_group': 'Yeniden Deneme Ayarları',
                'max_retries_label': 'Maksimum Deneme:',
                'timeout_label': 'Zaman Aşımı:',
                'enable_proxy_label': 'Proxy Etkin:',
                'auto_rotate_label': 'Proxy Otomatik Rotasyon:',
                'test_startup_label': 'Başlangıçta Proxy Test Et:',
                'update_interval_label': 'Güncelleme Aralığı:',
                'max_failures_label': 'Maksimum Hata:',
                'custom_proxies_group': 'Özel Proxy\'ler',
                'custom_proxies_note': 'Özel proxy\'leri girin (satır başına bir tane, format: host:port)',
                'refresh_proxies_btn': 'Proxy\'leri Yenile',
                'proxy_refresh_started': 'Proxy listesi arka planda yenileniyor...',
                'proxy_refresh_unavailable': 'Proxy yenileme şu anda mevcut değil',
                'info': 'Bilgi',
                'log_level_label': 'Log Seviyesi:',
                'max_log_size_label': 'Maksimum Log Dosya Boyutu:',
                'memory_optimization_group': 'Bellek Optimizasyonu',
                'chunk_size_label': 'Dosya Parça Boyutu:',
                'debugging_group': 'Hata Ayıklama',
                'debug_mode_label': 'Debug Modu:',
                'verbose_logging_label': 'Detaylı Log:'
            }
        }
    
    def get_ui_text(self, key: str) -> str:
        """Get UI text in current language."""
        translations = self.get_ui_translations()
        current_lang = self.app_settings.ui_language
        
        if current_lang in translations and key in translations[current_lang]:
            return translations[current_lang][key]
        
        # Fallback to English
        if 'en' in translations and key in translations['en']:
            return translations['en'][key]
        
        # Fallback to key itself
        return key
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self.translation_settings = TranslationSettings()
        self.api_keys = ApiKeys()
        self.app_settings = AppSettings()
        self.proxy_settings = ProxySettings()
        self.logger.info("Configuration reset to defaults")
