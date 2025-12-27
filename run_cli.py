#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RenLocalizer CLI Launcher
Cross-platform command line interface
"""

import os
import sys
from pathlib import Path

# Ensure stdout uses UTF-8
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def setup_environment() -> None:
    """Setup environment variables and paths."""
    # Add project root to Python path
    project_root = Path(__file__).parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

def main() -> int:
    setup_environment()
    
    try:
        from src.cli_main import main as cli_main
        return cli_main()
    except ImportError as e:
        print(f"Error: Could not import CLI module: {e}")
        print("Ensure you are running from the project root and all dependencies are installed.")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
