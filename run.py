# -*- coding: utf-8 -*-
"""
RenLocalizer V2 Launcher
Cross-platform launcher for Windows and Unix systems
"""

import sys
import os
from pathlib import Path

def show_error_and_wait(title: str, message: str):
    """Show error message and wait for user input (works without Qt)."""
    print(f"\n{'='*60}")
    print(f"ERROR: {title}")
    print('='*60)
    print(message)
    print('='*60)
    
    # Try Windows MessageBox
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
        except:
            pass
    
    # Keep console open
    print("\nPress Enter to close...")
    try:
        input()
    except:
        import time
        time.sleep(10)  # Wait 10 seconds if input fails

def check_windows_version():
    """Check if Windows version is compatible."""
    if sys.platform != 'win32':
        return True
    
    try:
        import platform
        version = platform.version()
        release = platform.release()
        machine = platform.machine()
        
        print(f"Windows Version: {release} ({version})")
        print(f"Architecture: {machine}")
        
        # Check for 64-bit
        if machine not in ['AMD64', 'x86_64']:
            show_error_and_wait(
                "Unsupported Architecture",
                f"RenLocalizer requires 64-bit Windows.\n\n"
                f"Your system: {machine}\n\n"
                "Please use a 64-bit version of Windows."
            )
            return False
        
        return True
    except Exception as e:
        print(f"Warning: Could not check Windows version: {e}")
        return True

def check_vcruntime():
    """Check if Visual C++ Runtime is installed (Windows only)."""
    if sys.platform != 'win32':
        return True
    
    import ctypes
    
    # Try to load vcruntime140.dll (required by PyQt6)
    required_dlls = ['vcruntime140.dll', 'msvcp140.dll']
    missing_dlls = []
    
    for dll_name in required_dlls:
        try:
            ctypes.WinDLL(dll_name)
            print(f"✓ {dll_name} found")
        except OSError:
            print(f"✗ {dll_name} MISSING")
            missing_dlls.append(dll_name)
    
    if missing_dlls:
        show_error_and_wait(
            "RenLocalizer - Missing Runtime",
            f"RenLocalizer requires Microsoft Visual C++ Redistributable.\n\n"
            f"Missing components: {', '.join(missing_dlls)}\n\n"
            "Please download and install:\n"
            "Visual C++ Redistributable 2015-2022 (x64)\n\n"
            "Download link:\n"
            "https://aka.ms/vs/17/release/vc_redist.x64.exe\n\n"
            "After installation, restart RenLocalizer."
        )
        return False
    
    return True

def get_app_dir() -> Path:
    """Get the application directory - works for both dev and frozen exe."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        return Path(sys.executable).parent
    else:
        # Running in development
        return Path(__file__).parent

def setup_qt_environment():
    """Setup Qt environment variables for frozen exe."""
    if getattr(sys, 'frozen', False):
        # Get the temp extraction directory
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            meipass_path = Path(meipass)
            
            print(f"MEIPASS: {meipass_path}")
            
            # List ALL contents for debugging
            try:
                print(f"\nContents of MEIPASS root (all):")
                all_items = sorted(meipass_path.iterdir(), key=lambda x: x.name.lower())
                for item in all_items:
                    marker = "[DIR]" if item.is_dir() else "[FILE]"
                    print(f"  {marker} {item.name}")
                
                # Check for PyQt6 directory
                pyqt6_dir = meipass_path / 'PyQt6'
                if pyqt6_dir.exists():
                    print(f"\nPyQt6 directory contents:")
                    for item in sorted(pyqt6_dir.iterdir()):
                        print(f"  {item.name}")
                else:
                    print(f"\n⚠️ PyQt6 directory NOT FOUND at {pyqt6_dir}")
                
                # Check for Qt6 DLLs in root
                qt_dlls = [f for f in meipass_path.glob("Qt6*.dll")]
                if qt_dlls:
                    print(f"\nQt6 DLLs found in root: {len(qt_dlls)}")
                    for dll in qt_dlls[:10]:
                        print(f"  {dll.name}")
                else:
                    print(f"\n⚠️ No Qt6*.dll files found in root!")
                
                # Check for qwindows.dll
                qwindows_locations = list(meipass_path.rglob("qwindows.dll"))
                if qwindows_locations:
                    print(f"\nqwindows.dll found at:")
                    for loc in qwindows_locations:
                        print(f"  {loc}")
                else:
                    print(f"\n⚠️ qwindows.dll NOT FOUND anywhere!")
                    
            except Exception as e:
                print(f"Error listing contents: {e}")
            
            # ============================================================
            # CRITICAL: Use os.add_dll_directory() for Python 3.8+
            # This is required because Python 3.8+ changed DLL search behavior
            # ============================================================
            dll_directories_added = []
            
            # Collect all possible DLL paths
            dll_paths = [
                meipass_path,
                meipass_path / 'PyQt6',
                meipass_path / 'PyQt6' / 'Qt6',
                meipass_path / 'PyQt6' / 'Qt6' / 'bin',
                meipass_path / 'PyQt6' / 'Qt6' / 'plugins' / 'platforms',
            ]
            
            # Add DLL directories using the new Python 3.8+ API
            if hasattr(os, 'add_dll_directory'):
                print(f"\nUsing os.add_dll_directory() (Python 3.8+ mode):")
                for dll_path in dll_paths:
                    if dll_path.exists():
                        try:
                            os.add_dll_directory(str(dll_path))
                            dll_directories_added.append(str(dll_path))
                            print(f"  ✓ Added: {dll_path}")
                        except Exception as e:
                            print(f"  ✗ Failed to add {dll_path}: {e}")
            else:
                print(f"\nos.add_dll_directory() not available (Python < 3.8)")
            
            # Collect all possible plugin paths
            plugin_paths = []
            
            # Standard PyQt6 paths
            plugin_paths.append(meipass_path / 'PyQt6' / 'Qt6' / 'plugins')
            plugin_paths.append(meipass_path / 'PyQt6' / 'Qt' / 'plugins')
            plugin_paths.append(meipass_path / 'PyQt6' / 'plugins')
            
            # Root level paths
            plugin_paths.append(meipass_path / 'plugins')
            plugin_paths.append(meipass_path / 'Qt6' / 'plugins')
            plugin_paths.append(meipass_path / 'qt6_plugins')
            
            # Find existing plugin paths
            existing_plugin_paths = [str(p) for p in plugin_paths if p.exists()]
            
            if existing_plugin_paths:
                os.environ['QT_PLUGIN_PATH'] = ';'.join(existing_plugin_paths)
                print(f"\nSet QT_PLUGIN_PATH: {os.environ['QT_PLUGIN_PATH']}")
            else:
                # Fallback: search for platforms directory
                platforms_dirs = list(meipass_path.rglob("platforms"))
                if platforms_dirs:
                    for pdir in platforms_dirs:
                        if (pdir / 'qwindows.dll').exists():
                            parent = pdir.parent
                            os.environ['QT_PLUGIN_PATH'] = str(parent)
                            print(f"\nFound plugins via search: {parent}")
                            break
            
            # Also set PATH (as fallback for older behavior)
            lib_paths = [
                meipass_path / 'PyQt6' / 'Qt6' / 'bin',
                meipass_path / 'PyQt6' / 'Qt6',
                meipass_path / 'PyQt6',
                meipass_path / 'Qt6' / 'bin',
                meipass_path,
            ]
            
            # Build PATH with existing directories
            existing_lib_paths = [str(p) for p in lib_paths if p.exists()]
            current_path = os.environ.get('PATH', '')
            os.environ['PATH'] = ';'.join(existing_lib_paths) + ';' + current_path
            
            print(f"\nAdded to PATH: {';'.join(existing_lib_paths[:3])}...")
            
            # Disable Qt debug output
            os.environ['QT_LOGGING_RULES'] = '*.debug=false'
            
            # ============================================================
            # Try to pre-load critical DLLs manually
            # ============================================================
            print(f"\nPre-loading critical DLLs...")
            import ctypes
            critical_dlls = ['Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll']
            
            for dll_name in critical_dlls:
                # Try to find and load the DLL
                dll_found = False
                for dll_path in dll_paths:
                    full_path = dll_path / dll_name
                    if full_path.exists():
                        try:
                            ctypes.CDLL(str(full_path))
                            print(f"  ✓ Loaded: {dll_name} from {dll_path}")
                            dll_found = True
                            break
                        except Exception as e:
                            print(f"  ✗ Failed to load {full_path}: {e}")
                
                if not dll_found:
                    # Try loading from root
                    root_dll = meipass_path / dll_name
                    if root_dll.exists():
                        try:
                            ctypes.CDLL(str(root_dll))
                            print(f"  ✓ Loaded: {dll_name} from root")
                        except Exception as e:
                            print(f"  ✗ Failed to load {root_dll}: {e}")

# Set working directory to app dir for consistent paths
APP_DIR = get_app_dir()
os.chdir(APP_DIR)

# Add project root to Python path BEFORE any src imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    print("="*60)
    print("RenLocalizer V2 Starting...")
    print("="*60)
    
    # Setup Qt environment FIRST (before any imports)
    setup_qt_environment()
    
    # Check Windows version and architecture
    if not check_windows_version():
        sys.exit(1)
    
    # Check Visual C++ Runtime (before any Qt imports)
    if not check_vcruntime():
        sys.exit(1)
    
    print("\nLoading Qt framework...")
    
    try:
        # Import Qt FIRST to catch DLL errors early
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QIcon
            QT_BACKEND = "PyQt6"
        except ImportError as e:
            print(f"PyQt6 import failed: {e}")
            try:
                from PySide6.QtWidgets import QApplication
                from PySide6.QtGui import QIcon
                QT_BACKEND = "PySide6"
            except ImportError as e2:
                print(f"PySide6 import also failed: {e2}")
                raise RuntimeError("Neither PyQt6 nor PySide6 could be loaded. Please reinstall the application.")
        
        print(f"Using Qt backend: {QT_BACKEND}")
        
        # Now import src modules (they will use the same Qt backend)
        from src.version import VERSION
        from src.gui.main_window import MainWindow
        from src.utils.config import ConfigManager
        
        # Create application
        app = QApplication(sys.argv)
        app.setApplicationName("RenLocalizer")
        app.setApplicationVersion(VERSION)
        
        # Apply Fusion style for consistent cross-platform appearance
        # This prevents system theme from interfering with QSS styles
        app.setStyle("Fusion")
        
        # Set application icon - use APP_DIR for frozen exe
        icon_path = APP_DIR / "icon.ico"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
        
        # Create main window
        window = MainWindow()
        window.show()
        
        # Run application
        sys.exit(app.exec())
        
    except Exception as e:
        error_msg = f"Error starting RenLocalizer V2: {e}"
        print(error_msg)
        import traceback
        tb = traceback.format_exc()
        print(tb)
        
        show_error_and_wait(
            "RenLocalizer - Startup Error",
            f"{error_msg}\n\n{tb}\n\n"
            "Possible solutions:\n"
            "1. Install Visual C++ Redistributable 2015-2022 (x64)\n"
            "2. Disable antivirus temporarily\n"
            "3. Run as Administrator\n"
            "4. Check if Windows is 64-bit"
        )
        
        sys.exit(1)
