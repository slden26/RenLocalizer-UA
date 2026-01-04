# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
project_dir = os.path.abspath(os.getcwd())

# Automatically collect all submodules from src package
hidden_imports = collect_submodules('src')

# Aggressively collect submodules for external libraries to prevent missing imports
hidden_imports += collect_submodules('qfluentwidgets')
hidden_imports += collect_submodules('aiohttp')
hidden_imports += collect_submodules('requests')
hidden_imports += collect_submodules('urllib3')
hidden_imports += collect_submodules('pykakasi')
hidden_imports += collect_submodules('PIL')
hidden_imports += collect_submodules('engineio')
hidden_imports += collect_submodules('socketio')
hidden_imports += collect_submodules('rapidfuzz')  # Often used for fuzzy matching
hidden_imports += collect_submodules('packaging')
hidden_imports += collect_submodules('chardet')
hidden_imports += collect_submodules('charset_normalizer')

# Manual additions for specific edge cases
hidden_imports.extend([
    'PIL._tkinter_finder', 
    'engineio.async_drivers.aiohttp',
    'win32timezone',
])

# Define datas with absolute paths to avoid not found errors
datas_list = [
    (os.path.join(project_dir, 'locales'), 'locales'),
    (os.path.join(project_dir, 'icon.ico'), '.'),
    # fluent resources folder needs to preserve its structure
    (os.path.join(project_dir, 'src', 'gui', 'fluent', 'resources'), os.path.join('src', 'gui', 'fluent', 'resources')),
]

# Add Linux/Mac shell scripts only when building on those platforms
# These are for source-based execution assistance, not required for bundled apps
if sys.platform != 'win32':
    sh_files = [
        (os.path.join(project_dir, 'RenLocalizer.sh'), '.'),
        (os.path.join(project_dir, 'RenLocalizerCLI.sh'), '.')
    ]
    # Only add if files exist
    for sh_src, sh_dst in sh_files:
        if os.path.exists(sh_src):
            datas_list.append((sh_src, sh_dst))


# =========================================================
# GUI Application Analysis (RenLocalizer)
# =========================================================
a = Analysis(
    ['run.py'],
    pathex=[project_dir],
    binaries=[],
    datas=datas_list,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RenLocalizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico'
)

# =========================================================
# CLI Application Analysis (RenLocalizerCLI)
# =========================================================
b = Analysis(
    ['run_cli.py'],
    pathex=[project_dir],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz_cli = PYZ(b.pure, b.zipped_data, cipher=block_cipher)

exe_cli = EXE(
    pyz_cli,
    b.scripts,
    [],
    exclude_binaries=True,
    name='RenLocalizerCLI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico'
)

# =========================================================
# COLLECT (Folder Output)
# =========================================================
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    
    exe_cli,
    b.binaries,
    b.zipfiles,
    b.datas,
    
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RenLocalizer',
)
