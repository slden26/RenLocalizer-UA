"""
Native RPA Archive Parser for Ren'Py games.

This is a fallback implementation that doesn't rely on external unrpa dependency.
Supports RPA-3.0 and RPA-2.0 formats (most common in modern Ren'Py games).

Used when:
1. unrpa fails to import in frozen (PyInstaller) environment
2. unrpa is not installed
"""

import os
import pickle
import zlib
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, BinaryIO


class RPAParser:
    """Native RPA archive parser supporting RPAv2 and RPAv3 formats."""
    
    # RPA format signatures
    RPA3_SIGNATURE = b"RPA-3.0"
    RPA2_SIGNATURE = b"RPA-2.0"
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_archive(self, rpa_path: Path, output_dir: Path) -> bool:
        """
        Extract all files from an RPA archive.
        
        Args:
            rpa_path: Path to the .rpa file
            output_dir: Directory to extract files to
            
        Returns:
            bool: True if extraction was successful
        """
        if not rpa_path.exists():
            self.logger.error(f"RPA file not found: {rpa_path}")
            return False
        
        try:
            with open(rpa_path, 'rb') as f:
                # Read header to determine format
                header = f.readline()
                
                if header.startswith(self.RPA3_SIGNATURE):
                    return self._extract_rpa3(f, header, output_dir)
                elif header.startswith(self.RPA2_SIGNATURE):
                    return self._extract_rpa2(f, header, output_dir)
                else:
                    self.logger.error(f"Unknown RPA format: {header[:20]}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error extracting {rpa_path}: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    def _extract_rpa3(self, f: BinaryIO, header: bytes, output_dir: Path) -> bool:
        """Extract RPA-3.0 format archive."""
        try:
            # Parse header: "RPA-3.0 XXXXXXXXXXXXXXXX YYYYYYYY\n"
            # XXXXXXXXXXXXXXXX = hex offset to index
            # YYYYYYYY = hex key for deobfuscation
            parts = header.decode('utf-8').strip().split()
            if len(parts) < 3:
                self.logger.error(f"Invalid RPA-3.0 header: {header}")
                return False
            
            offset = int(parts[1], 16)
            key = int(parts[2], 16)
            
            # Read and decompress index
            f.seek(offset)
            index_data = f.read()
            
            try:
                index = pickle.loads(zlib.decompress(index_data))
            except:
                # Some archives use raw pickle
                f.seek(offset)
                index = pickle.loads(f.read())
            
            return self._extract_files(f, index, output_dir, key)
            
        except Exception as e:
            self.logger.error(f"RPA-3.0 extraction error: {e}")
            return False
    
    def _extract_rpa2(self, f: BinaryIO, header: bytes, output_dir: Path) -> bool:
        """Extract RPA-2.0 format archive."""
        try:
            # Parse header: "RPA-2.0 XXXXXXXXXXXXXXXX\n"
            parts = header.decode('utf-8').strip().split()
            if len(parts) < 2:
                self.logger.error(f"Invalid RPA-2.0 header: {header}")
                return False
            
            offset = int(parts[1], 16)
            
            # Read and decompress index
            f.seek(offset)
            index_data = f.read()
            
            try:
                index = pickle.loads(zlib.decompress(index_data))
            except:
                f.seek(offset)
                index = pickle.loads(f.read())
            
            # RPA-2.0 doesn't use key obfuscation
            return self._extract_files(f, index, output_dir, key=0)
            
        except Exception as e:
            self.logger.error(f"RPA-2.0 extraction error: {e}")
            return False
    
    def _extract_files(self, f: BinaryIO, index: Dict, output_dir: Path, key: int = 0) -> bool:
        """Extract files from index to output directory."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        extracted = 0
        errors = 0
        
        for filename, data_list in index.items():
            try:
                # Normalize filename
                if isinstance(filename, bytes):
                    filename = filename.decode('utf-8')
                
                # Get file info - format: [(offset, length, prefix), ...]
                if not data_list:
                    continue
                
                file_data = data_list[0]
                
                if len(file_data) >= 2:
                    offset = file_data[0] ^ key
                    length = file_data[1] ^ key
                    prefix = file_data[2] if len(file_data) > 2 else b''
                else:
                    continue
                
                # Handle prefix (may be bytes or string)
                if isinstance(prefix, str):
                    prefix = prefix.encode('latin-1')
                
                # Create output path
                out_path = output_dir / filename
                out_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Read and write file
                f.seek(offset)
                content = prefix + f.read(length - len(prefix))
                
                with open(out_path, 'wb') as out_f:
                    out_f.write(content)
                
                extracted += 1
                
            except Exception as e:
                self.logger.warning(f"Failed to extract {filename}: {e}")
                errors += 1
        
        self.logger.info(f"Extracted {extracted} files ({errors} errors)")
        return extracted > 0


# Convenience function
def extract_rpa(rpa_path: Path, output_dir: Path) -> bool:
    """Extract an RPA archive using native parser."""
    parser = RPAParser()
    return parser.extract_archive(rpa_path, output_dir)
