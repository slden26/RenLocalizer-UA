#!/bin/bash
# RenLocalizer GUI Launcher for Linux/Mac
# Version: 2.4.3

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       RenLocalizer v2.4.3            ║${NC}"
echo -e "${GREEN}║   Professional Ren'Py Translation    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed.${NC}"
    echo "Please install Python 3.10 or higher."
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "  Fedora: sudo dnf install python3 python3-pip"
    echo "  macOS: brew install python3"
    exit 1
fi

# Check Python version (minimum 3.10)
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    echo -e "${RED}Error: Python 3.10 or higher is required.${NC}"
    echo "Current version: Python $PYTHON_VERSION"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION detected"

# Setup virtual environment if not exists
if [ ! -d "venv" ]; then
    echo ""
    echo -e "${YELLOW}Setting up RenLocalizer environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    
    # Upgrade pip first
    echo "Upgrading pip..."
    pip install --upgrade pip > /dev/null 2>&1
    
    if [ -f "requirements.txt" ]; then
        echo "Installing dependencies (this may take a moment)..."
        pip install -r requirements.txt
    else
        echo -e "${RED}Warning: requirements.txt not found!${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓${NC} Environment setup complete"
else
    source venv/bin/activate
    echo -e "${GREEN}✓${NC} Virtual environment activated"
fi

# Run the application
echo ""
echo "Starting RenLocalizer GUI..."
python3 run.py
