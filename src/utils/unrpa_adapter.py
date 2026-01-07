"""
Adapter for RPA archive extraction in Ren'Py games.

Provides a unified interface with automatic fallback:
1. First tries unrpa library (if available)
2. Falls back to native rpa_parser.py (PyInstaller compatible)

The native parser is essential for frozen (PyInstaller) builds where
unrpa may fail to import due to dynamic import issues.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional, List

# Check if we're running in a frozen/bundled environment (PyInstaller)
IS_FROZEN = getattr(sys, 'frozen', False)

# Track which extraction method is available
_UNRPA_AVAILABLE = None
_NATIVE_AVAILABLE = True  # Native parser is always available


def _check_unrpa() -> bool:
    """Check if unrpa library is usable (not just importable, but actually works)."""
    global _UNRPA_AVAILABLE
    
    if _UNRPA_AVAILABLE is not None:
        return _UNRPA_AVAILABLE
    
    try:
        from unrpa import UnRPA
        # Try to access versions to ensure all submodules loaded
        _ = UnRPA.__init__
        _UNRPA_AVAILABLE = True
    except (ImportError, AttributeError, Exception) as e:
        logging.getLogger(__name__).debug(f"unrpa not available: {e}")
        _UNRPA_AVAILABLE = False
    
    return _UNRPA_AVAILABLE


def _is_unrpa_installed() -> bool:
    """Check if any extraction method is available."""
    return _check_unrpa() or _NATIVE_AVAILABLE


class UnrpaAdapter:
    """
    Unified RPA extraction adapter with automatic fallback.
    
    Tries unrpa library first, then falls back to native parser.
    The native parser is essential for PyInstaller builds.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._use_native = not _check_unrpa()
        
        if self._use_native:
            self.logger.info("Using native RPA parser (unrpa not available)")
        else:
            self.logger.debug("Using unrpa library")

    @staticmethod
    def is_available() -> bool:
        """Check if RPA extraction is available (via any method)."""
        return _is_unrpa_installed()

    def extract_rpa(self, rpa_path: Path, output_dir: Path) -> bool:
        """
        Extract a single RPA file to the output directory.
        
        Args:
            rpa_path: Path to the .rpa file
            output_dir: Directory where files should be extracted
            
        Returns:
            bool: True if extraction was successful, False otherwise.
        """
        if not rpa_path.exists():
            self.logger.error(f"RPA file not found: {rpa_path}")
            return False

        # Try native parser first if we know unrpa won't work
        if self._use_native:
            return self._extract_native(rpa_path, output_dir)
        
        # Try unrpa, fall back to native on failure
        try:
            return self._extract_unrpa(rpa_path, output_dir)
        except Exception as e:
            self.logger.warning(f"unrpa failed, trying native parser: {e}")
            self._use_native = True
            return self._extract_native(rpa_path, output_dir)

    def _extract_unrpa(self, rpa_path: Path, output_dir: Path) -> bool:
        """Extract using unrpa library."""
        try:
            self.logger.info(f"Extracting {rpa_path} with unrpa...")
            
            from unrpa import UnRPA
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # unrpa 2.3.0 extracts to current working directory
            original_cwd = os.getcwd()
            try:
                os.chdir(str(output_dir))
                extractor = UnRPA(str(rpa_path), verbosity=0)
                extractor.extract_files()
                self.logger.info(f"Successfully extracted {rpa_path.name}")
                return True
            finally:
                os.chdir(original_cwd)
                
        except Exception as e:
            self.logger.error(f"unrpa extraction failed: {e}")
            raise  # Let caller handle fallback

    def _extract_native(self, rpa_path: Path, output_dir: Path) -> bool:
        """Extract using native RPA parser (PyInstaller compatible)."""
        try:
            self.logger.info(f"Extracting {rpa_path} with native parser...")
            
            from src.utils.rpa_parser import RPAParser
            
            parser = RPAParser()
            result = parser.extract_archive(rpa_path, output_dir)
            
            if result:
                self.logger.info(f"Successfully extracted {rpa_path.name}")
            else:
                self.logger.error(f"Native extraction failed for {rpa_path.name}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Native extraction error: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False

    def extract_game(self, game_dir: Path) -> bool:
        """
        Finds all .rpa files in the game directory and extracts them.
        
        Args:
            game_dir: The 'game' directory of the Ren'Py project.
            
        Returns:
            bool: True if at least one RPA was extracted or none found.
        """
        if not game_dir.exists():
            self.logger.error(f"Game directory not found: {game_dir}")
            return False

        rpa_files = list(game_dir.glob("**/*.rpa"))
        self.logger.info(f"Found {len(rpa_files)} RPA files in {game_dir}")
        
        if not rpa_files:
            self.logger.info("No .rpa files found to extract.")
            return True

        success_count = 0
        for rpa_file in rpa_files:
            self.logger.info(f"Processing: {rpa_file.name}")
            
            if self.extract_rpa(rpa_file, rpa_file.parent):
                success_count += 1
                
                # Rename the rpa file to .rpa.bak
                try:
                    bak_path = rpa_file.with_suffix(".rpa.bak")
                    if bak_path.exists():
                        bak_path.unlink()
                    rpa_file.rename(bak_path)
                    self.logger.info(f"Renamed {rpa_file.name} to .rpa.bak")
                except OSError as e:
                    self.logger.warning(f"Could not rename {rpa_file}: {e}")

        self.logger.info(f"Extraction complete: {success_count}/{len(rpa_files)} archives")
        return success_count > 0


