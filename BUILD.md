# RenLocalizer V2 Build Instructions

## 📦 Creating Standalone Executable

### Prerequisites
```bash
pip install pyinstaller
```

### 1. Create PyInstaller Spec File
Create `RenLocalizer.spec`:
```python
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('locales', 'locales'),
        ('icon.ico', '.'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui', 
        'PyQt6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RenLocalizer-V2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico'
)
```

### 2. Build Commands
```bash
# Clean build
pyinstaller RenLocalizer.spec --clean --noconfirm

# Debug build (with console)
# Change console=True in spec file
pyinstaller RenLocalizer.spec --clean --noconfirm
```

### 3. Build Output
- **Executable**: `dist/RenLocalizer-V2.exe`
- **Size**: ~43MB (standalone)
- **Dependencies**: All included

### 4. Important Notes
- The project includes `sys._MEIPASS` detection for proper locales loading
- Icon and assets are properly bundled
- PyQt6 is used (PySide6 excluded)
- UPX compression enabled for smaller size

### 5. Cleanup After Build
```bash
# Remove build artifacts (don't commit these)
rm -rf build/
rm -rf dist/
rm RenLocalizer.spec
```
