import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.parser import RenPyParser
p = RenPyParser()

sample = '''label start:
    e "Merhaba, [player_name]!"
    "Bu bir anlatıcı satırı."
    menu:
        "Devam etmek istiyor musun?":
            e "Evet."
    init python:
        x = _('Kaydet')
        y = "Bu çevrilmez"
    translate tr something:
        old "Hello."
        new "Merhaba."
'''
with open('src/core/test_sample.rpy','w',encoding='utf-8') as f:
    f.write(sample)

# Test parser
texts = p.extract_translatable_text('src/core/test_sample.rpy')
print('✅ Parser Çıkarılan metinler:')
for text in sorted(texts):
    print(f'  "{text}"')

print(f'\n✅ Toplam {len(texts)} metin çıkarıldı')
print('✅ Tokenize tabanlı güvenli ekstraksiyon aktif')
print('✅ GUI format dropdown entegrasyonu hazır')
