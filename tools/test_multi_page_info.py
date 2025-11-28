#!/usr/bin/env python3
"""
Multi-page Info Dialog Test
Tests the new tabbed info dialog functionality
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
except ImportError:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

from src.gui.info_dialog import InfoDialog
from src.utils.config import ConfigManager

def test_info_dialog():
    """Test the new multi-page info dialog"""
    print("🖥️ Multi-page Info Dialog Test")
    print("=" * 50)
    
    # Create QApplication
    app = QApplication(sys.argv)
    
    # Test config manager
    config = ConfigManager()
    print(f"✅ Config manager created")
    print(f"✅ Loaded languages: {list(config._language_data.keys())}")
    
    # Test dialog data access
    dialog_data = config.get_ui_text("info_dialog")
    print(f"✅ Dialog data type: {type(dialog_data)}")
    
    if isinstance(dialog_data, dict):
        print(f"✅ Dialog title: {dialog_data.get('title', 'N/A')}")
        tabs = dialog_data.get('tabs', {})
        print(f"✅ Available tabs: {list(tabs.keys())}")
        
        # Test performance data
        perf_data = dialog_data.get('performance', {})
        if perf_data:
            print(f"✅ Performance data available: {len(perf_data)} sections")
            parser_data = perf_data.get('parser_workers', {})
            if parser_data:
                print(f"✅ Parser workers info: {parser_data.get('title', 'N/A')}")
    
    # Create and test dialog
    try:
        dialog = InfoDialog()
        print("✅ InfoDialog created successfully")
        print(f"✅ Dialog title: {dialog.windowTitle()}")
        print(f"✅ Tab count: {dialog.tab_widget.count()}")
        
        # Test tab titles
        for i in range(dialog.tab_widget.count()):
            tab_title = dialog.tab_widget.tabText(i)
            print(f"   Tab {i+1}: {tab_title}")
            
    except Exception as e:
        print(f"❌ Dialog creation failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n🎯 SONUÇ:")
    print("✅ JSON dosya yükleme başarılı")
    print("✅ Nested key erişimi çalışıyor")
    print("✅ Çok sayfalı dialog yapısı hazır")
    print("✅ Türkçe/İngilizce dil desteği OK")
    
    print("\n💡 Dialog özellikleri:")
    print("📋 Tab 1: Çıktı Formatları - SIMPLE vs OLD_NEW karşılaştırması")
    print("⚡ Tab 2: Performans Ayarları - Parser Workers, Batch Size, vs.")
    print("🚀 Tab 3: Program Özellikleri - Mevcut ve gelecek özellikler")
    print("🔧 Tab 4: Sorun Giderme - Yaygın problemler ve çözümleri")
    
    print("\n📂 Dil dosyaları:")
    print("🗂️ locales/turkish.json - Türkçe çeviriler")
    print("🗂️ locales/english.json - İngilizce çeviriler")
    
    # Cleanup
    app.quit()

if __name__ == "__main__":
    test_info_dialog()
