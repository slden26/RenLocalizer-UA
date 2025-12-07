#!/usr/bin/env python3
"""
Format Comparison Tool
Shows the difference between 'simple' and 'old_new' output formats
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.output_formatter import RenPyOutputFormatter

def demonstrate_formats():
    """Demonstrate the difference between output formats"""
    
    formatter = RenPyOutputFormatter()
    
    # Test data
    original_text = 'Hello world! This is a "test" dialogue.'
    translated_text = 'Merhaba dünya! Bu bir "test" diyaloğu.'
    language_code = "tr"
    translation_id = "hello_world_test"
    
    print("🔍 RenLocalizer-V2 Output Format Comparison")
    print("=" * 60)
    
    print("\n📄 Original Text:")
    print(f'   "{original_text}"')
    print("\n🔄 Translated Text:")
    print(f'   "{translated_text}"')
    
    print("\n" + "=" * 60)
    print("🟦 SIMPLE FORMAT (Varsayılan)")
    print("=" * 60)
    
    simple_block = formatter.generate_translation_block(
        original_text, translated_text, language_code, 
        translation_id, mode="simple"
    )
    print(simple_block)
    
    print("=" * 60)
    print("🟩 OLD_NEW FORMAT (Ren'Py Resmi)")
    print("=" * 60)
    
    old_new_block = formatter.generate_translation_block(
        original_text, translated_text, language_code, 
        translation_id, mode="old_new"
    )
    print(old_new_block)
    
    print("=" * 60)
    print("📊 KARŞILAŞTIRMA")
    print("=" * 60)
    
    print("\n🟦 SIMPLE FORMAT Özellikleri:")
    print("✅ Daha temiz ve okunabilir")
    print("✅ Yorumlarda orijinal metin gösteriliyor")
    print("✅ Daha az satır kullanıyor")
    print("✅ Manuel düzenleme için ideal")
    print("✅ Modern Ren'Py sürümleriyle uyumlu")
    
    print("\n🟩 OLD_NEW FORMAT Özellikleri:")
    print("✅ Ren'Py'nin resmi export formatı")
    print("✅ Eski Ren'Py sürümleriyle tam uyumlu")
    print("✅ Orijinal ve çeviri metni açık şekilde ayrılmış")
    print("✅ Ren'Py'nin kendi araçlarıyla tam uyumlu")
    print("✅ Daha yapısal yaklaşım")
    
    print("\n🎯 ÖNERI:")
    print("📌 SIMPLE: Modern projeler, manuel editing, temiz output")
    print("📌 OLD_NEW: Eski projeler, resmi Ren'Py araçları, maksimum uyumluluk")
    
    print("\n💡 İpucu: GUI'den output format'ı değiştirebilirsiniz!")

if __name__ == "__main__":
    demonstrate_formats()
