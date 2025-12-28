from pathlib import Path

# Bu script, dosyanın ilk 64 byte'ını hex olarak gösterir
file_path = Path('cast.rpymc')
with file_path.open('rb') as f:
    data = f.read(64)
print(' '.join(f'{b:02X}' for b in data))
print('ASCII:', ''.join(chr(b) if 32 <= b < 127 else '.' for b in data))
