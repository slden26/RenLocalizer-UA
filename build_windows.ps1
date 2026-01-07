# Build script for RenLocalizer on Windows
# Creates venv, installs dependencies and runs PyInstaller with RenLocalizer.spec
set -e
$venv = Join-Path $PWD '.venv'
if (-Not (Test-Path $venv)) {
    python -m venv .venv
}
$python = Join-Path $venv 'Scripts\python.exe'
# Upgrade pip
& $python -m pip install --upgrade pip setuptools wheel
# Install requirements (ignore failures for optional packages)
& $python -m pip install -r requirements.txt
# Install PyInstaller
& $python -m pip install pyinstaller
# Run PyInstaller using module to ensure correct interpreter
& $python -m PyInstaller RenLocalizer.spec --noconfirm
Write-Output 'BUILD_SCRIPT_DONE'