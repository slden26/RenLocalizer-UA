@echo off
echo Starting RenLocalizer V2...
echo.

:: Set project path as PYTHONPATH
set "PYTHONPATH=%~dp0"

:: Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.8+ and add it to PATH.
    pause
    exit /b 1
)

:: Check if requirements are installed
python -c "import PyQt6" >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: PyQt6 not found. Installing dependencies...
    python -m pip install -r requirements.txt
)

:: Run the application
python run.py

if %errorlevel% neq 0 (
    echo.
    echo Application exited with error code: %errorlevel%
)

pause
