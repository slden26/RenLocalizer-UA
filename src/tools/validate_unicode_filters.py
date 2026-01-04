"""Validate Unicode-aware filters in RenLocalizer parser.

Run: python src/tools/validate_unicode_filters.py
Exits with code 0 if all checks pass, non-zero otherwise.
"""
import sys
from src.core.parser import RenPyParser

parser = RenPyParser()

samples = {
    'English': 'Hello world',
    'Russian': 'Привет мир',
    'Arabic': 'مرحبا بالعالم',
    'Japanese': 'こんにちは世界',
    'Chinese': '你好，世界',
    'Hindi': 'नमस्ते दुनिया',
    'PlaceholderOnly': '{player}',
    'Short': 'a',
    'Numbers': '12345',
    'Mixed': 'Start {player} مرحبا',
}

expected_meaningful = {
    'English': True,
    'Russian': True,
    'Arabic': True,
    'Japanese': True,
    'Chinese': True,
    'Hindi': True,
    'PlaceholderOnly': False,
    'Short': False,
    'Numbers': False,
    'Mixed': True,
}

ok = True
print('Testing is_meaningful_text:')
for name, txt in samples.items():
    res = parser.is_meaningful_text(txt)
    print(f" - {name}: {repr(txt)} -> {res} (expected {expected_meaningful[name]})")
    if res != expected_meaningful[name]:
        ok = False

# Test JSON/CSV/TXT extraction helpers
print('\nTesting _is_meaningful_data_value (no key):')
for name, txt in samples.items():
    res = parser._is_meaningful_data_value(txt, None)
    expected = expected_meaningful[name]
    print(f" - {name}: {txt[:30] + '...' if len(txt) > 30 else txt} -> {res} (expected {expected})")
    if res != expected:
        ok = False

# Create a temporary txt content and run extract_from_txt
print('\nTesting extract_from_txt parsing behavior:')
from pathlib import Path
p = Path('src/tools/_validate_tmp.txt')
p.write_text('\n'.join([samples[k] for k in samples]), encoding='utf-8')
entries = parser.extract_from_txt(p)
print(f" - extract_from_txt found {len(entries)} entries (expected >= 6)")
if len(entries) < 6:
    ok = False
p.unlink()

if ok:
    print('\nAll validations passed.')
    sys.exit(0)
else:
    print('\nValidation FAILED: some checks did not match expectations.')
    sys.exit(2)

# helper
def _short(s):
    return (s[:30] + '...') if len(s) > 30 else s
