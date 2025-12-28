from pathlib import Path
from src.core.parser import RenPyParser
import json
import re

TARGET='summertimesaga'

def is_potential_false_positive(text):
    if text is None:
        return True
    s = text.strip()
    if not s:
        return True
    # Short strings that don't contain letters are likely not translatable
    if len(s) < 4 and not re.search(r'[A-Za-zÇĞİÖŞÜçğıöşü]', s):
        return True
    # Remove placeholders/tags and check remaining letters
    cleaned = re.sub(r'(\[[^\]]+\]|\{[^}]+\})', '', s).strip()
    if len(re.findall(r'[A-Za-zÇĞİÖŞÜçğıöşü]', cleaned)) < 2:
        return True
    lw = s.lower()
    if lw.startswith(('label ', 'scene ', 'show ', 'hide ', '$')):
        return True
    return False

p = Path(TARGET)
parser = RenPyParser()
count=0
for f in p.rglob('*.rpy'):
    try:
        entries = parser.extract_text_entries(f)
    except Exception as e:
        continue
    for e in entries:
        if is_potential_false_positive(e.get('text')):
            count+=1
            print('---')
            print(f, e.get('line_number'))
            print(e.get('text'))
print('TOTAL', count)
