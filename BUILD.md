# Build Instructions

This document provides instructions for building RenLocalizer into a standalone executable.

## Prerequisites

- Python 3.8+ 
- All dependencies installed (`pip install -r requirements.txt`)
- PyInstaller (`pip install pyinstaller`)

## Building the Executable

### Method 1: Using Spec File (Recommended)

```bash
# Clean previous builds
python -c "import shutil; shutil.rmtree('build', ignore_errors=True); shutil.rmtree('dist', ignore_errors=True)"

# Build using spec file
python -m PyInstaller RenLocalizer.spec --clean
```

### Method 2: Using Build Scripts

**Windows:**
```batch
# Use the provided batch file
build.bat
```

**PowerShell:**
```powershell
# Use the PowerShell script
.\build.ps1
```

### Method 3: Manual PyInstaller Command

```bash
pyinstaller --onefile --windowed --icon=icon.ico \
    --add-data "locales;locales" \
    --add-data "config.json;." \
    --add-data "icon.ico;." \
    --exclude-module "PySide6" \
    --exclude-module "transformers" \
    --exclude-module "torch" \
    run.py -n RenLocalizer
```

## Build Configuration

The `RenLocalizer.spec` file contains optimized build settings:

- **Single File**: Creates one portable .exe file
- **Windowed**: No console window (GUI only)
- **Icon**: Embedded application icon
- **Resources**: Includes locales, config, and icon files
- **Exclusions**: Removes unused heavy dependencies
- **Optimizations**: UPX compression enabled

## Output

After successful build:
- Executable: `dist/RenLocalizer.exe` (~36 MB)
- Portable: No installation required
- Standalone: All dependencies included

## Troubleshooting

### Common Issues

1. **Missing Icon**: Ensure `icon.ico` exists in root directory
2. **Import Errors**: Check all dependencies are installed
3. **Large File Size**: Normal due to PyQt6 and translation engines
4. **Slow Startup**: First run may be slower due to unpacking

### Debug Build

For debugging issues, create a console version:

```bash
# Edit RenLocalizer.spec: change console=False to console=True
python -m PyInstaller RenLocalizer.spec --clean
```

### Clean Build

Always clean before building:

```bash
# Remove old build artifacts
rm -rf build/ dist/ __pycache__/
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +
```

## Distribution

The generated executable is ready for distribution:
- No Python installation required on target systems
- Works on Windows 10/11
- Antivirus may flag initially (common with PyInstaller)
- Recommended to sign the executable for production use

## File Structure After Build

```
dist/
└── RenLocalizer.exe    # Standalone executable (~36 MB)
```

## Notes

- Build time: ~2-5 minutes depending on system
- Memory usage during build: ~2-4 GB
- Target system requirements: Windows 10/11, 64-bit
- No additional files needed alongside the executable