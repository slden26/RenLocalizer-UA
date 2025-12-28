# -*- coding: utf-8 -*-
"""
Ren'Py SDK Finder
Sistemdeki Ren'Py SDK kurulumlarını bulur.
"""

import os
import glob
import subprocess
import re
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass


@dataclass
class RenPySDK:
    """Ren'Py SDK bilgilerini tutar"""
    path: str
    version: str
    python_path: str
    renpy_script: str
    
    def __str__(self) -> str:
        return f"Ren'Py {self.version} ({self.path})"


class SDKFinder:
    """Sistemdeki Ren'Py SDK kurulumlarını bulan sınıf"""
    
    # Yaygın SDK kurulum konumları
    COMMON_LOCATIONS = [
        # Windows yaygın konumlar
        os.path.expanduser("~/renpy-*"),
        os.path.expanduser("~/Desktop/renpy-*"),
        os.path.expanduser("~/Documents/renpy-*"),
        "C:/Program Files/renpy-*",
        "C:/Program Files (x86)/renpy-*",
        "C:/renpy-*",
        "D:/renpy-*",
        # Steam Ren'Py
        os.path.expanduser("~/AppData/Local/Steam/steamapps/common/Ren'Py*"),
        "C:/Program Files/Steam/steamapps/common/Ren'Py*",
        "C:/Program Files (x86)/Steam/steamapps/common/Ren'Py*",
        # Itch.io
        os.path.expanduser("~/AppData/Roaming/itch/apps/renpy*"),
    ]
    
    # Linux/macOS yaygın konumlar
    UNIX_LOCATIONS = [
        os.path.expanduser("~/renpy-*"),
        os.path.expanduser("~/Desktop/renpy-*"),
        os.path.expanduser("~/Downloads/renpy-*"),
        "/opt/renpy-*",
        "/usr/local/renpy-*",
        os.path.expanduser("~/.local/share/renpy-*"),
    ]
    
    def __init__(self):
        self.found_sdks: List[RenPySDK] = []
        self._cache_valid = False
    
    def find_all(self, custom_paths: Optional[List[str]] = None) -> List[RenPySDK]:
        """
        Tüm Ren'Py SDK kurulumlarını bulur.
        
        Args:
            custom_paths: Ek arama yolları
            
        Returns:
            Bulunan SDK'ların listesi
        """
        self.found_sdks = []
        search_locations = self.COMMON_LOCATIONS.copy()
        
        # Platform kontrolü
        if os.name != 'nt':
            search_locations.extend(self.UNIX_LOCATIONS)
        
        # Özel yollar
        if custom_paths:
            search_locations.extend(custom_paths)
        
        # PATH ortam değişkeninden ara
        path_sdks = self._search_in_path()
        for sdk in path_sdks:
            if sdk not in [s.path for s in self.found_sdks]:
                self.found_sdks.append(sdk)
        
        # Yaygın konumlarda ara
        for pattern in search_locations:
            expanded = os.path.expanduser(pattern)
            matches = glob.glob(expanded)
            
            for match in matches:
                if os.path.isdir(match):
                    sdk = self._validate_sdk(match)
                    if sdk and sdk.path not in [s.path for s in self.found_sdks]:
                        self.found_sdks.append(sdk)
        
        # Sürüme göre sırala (en yeni önce)
        self.found_sdks.sort(key=lambda x: self._version_key(x.version), reverse=True)
        self._cache_valid = True
        
        return self.found_sdks
    
    def _search_in_path(self) -> List[RenPySDK]:
        """PATH ortam değişkeninde Ren'Py arar"""
        sdks = []
        path_var = os.environ.get('PATH', '')
        
        for path_dir in path_var.split(os.pathsep):
            # renpy.exe veya renpy.sh ara
            for script in ['renpy.exe', 'renpy.sh', 'renpy.py']:
                script_path = os.path.join(path_dir, script)
                if os.path.exists(script_path):
                    parent = os.path.dirname(path_dir) if path_dir.endswith('lib') else path_dir
                    sdk = self._validate_sdk(parent)
                    if sdk:
                        sdks.append(sdk)
        
        return sdks
    
    def _validate_sdk(self, path: str) -> Optional[RenPySDK]:
        """
        Bir dizinin geçerli Ren'Py SDK olup olmadığını kontrol eder.
        
        Args:
            path: Kontrol edilecek dizin yolu
            
        Returns:
            Geçerliyse RenPySDK objesi, değilse None
        """
        path = os.path.abspath(path)
        
        # renpy.py veya renpy.sh/renpy.exe kontrolü
        renpy_script = None
        python_path = None
        
        # Windows
        if os.name == 'nt':
            possible_scripts = [
                os.path.join(path, 'renpy.exe'),
                os.path.join(path, 'renpy.py'),
                os.path.join(path, 'lib', 'windows-x86_64', 'renpy.exe'),
            ]
            possible_pythons = [
                os.path.join(path, 'lib', 'py3-windows-x86_64', 'python.exe'),
                os.path.join(path, 'lib', 'windows-x86_64', 'python.exe'),
                os.path.join(path, 'lib', 'pythonw.exe'),
                os.path.join(path, 'python.exe'),
            ]
        else:
            possible_scripts = [
                os.path.join(path, 'renpy.sh'),
                os.path.join(path, 'renpy.py'),
            ]
            possible_pythons = [
                os.path.join(path, 'lib', 'py3-linux-x86_64', 'python'),
                os.path.join(path, 'lib', 'linux-x86_64', 'python'),
                os.path.join(path, 'lib', 'python'),
            ]
        
        for script in possible_scripts:
            if os.path.exists(script):
                renpy_script = script
                break
        
        for python in possible_pythons:
            if os.path.exists(python):
                python_path = python
                break
        
        if not renpy_script:
            return None
        
        # Sürüm bilgisini al
        version = self._get_version(path)
        if not version:
            return None
        
        # Python yoksa sistem Python kullanılabilir
        if not python_path:
            python_path = 'python'
        
        return RenPySDK(
            path=path,
            version=version,
            python_path=python_path,
            renpy_script=renpy_script
        )
    
    def _get_version(self, sdk_path: str) -> Optional[str]:
        """SDK sürümünü bulur"""
        
        # 1. Yol isminden çıkar (renpy-8.2.0-sdk gibi)
        dirname = os.path.basename(sdk_path)
        version_match = re.search(r'renpy[_-]?(\d+\.\d+(?:\.\d+)?)', dirname, re.I)
        if version_match:
            return version_match.group(1)
        
        # 2. renpy/__init__.py dosyasından
        init_paths = [
            os.path.join(sdk_path, 'renpy', '__init__.py'),
            os.path.join(sdk_path, 'launcher', 'game', 'about.rpy'),
        ]
        
        for init_path in init_paths:
            if os.path.exists(init_path):
                try:
                    with open(init_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # version = "8.2.0" veya version_tuple = (8, 2, 0) ara
                        match = re.search(r'version\s*=\s*["\'](\d+\.\d+(?:\.\d+)?)["\']', content)
                        if match:
                            return match.group(1)
                        match = re.search(r'version_tuple\s*=\s*\((\d+),\s*(\d+)(?:,\s*(\d+))?\)', content)
                        if match:
                            v = f"{match.group(1)}.{match.group(2)}"
                            if match.group(3):
                                v += f".{match.group(3)}"
                            return v
                except Exception:
                    pass
        
        # 3. Sürüm bulunamazsa "unknown" döndür
        return "unknown"
    
    def _version_key(self, version: str) -> Tuple:
        """Sürüm karşılaştırması için anahtar oluşturur"""
        if version == "unknown":
            return (0, 0, 0)
        
        parts = version.split('.')
        try:
            return tuple(int(p) for p in parts)
        except ValueError:
            return (0, 0, 0)
    
    def get_latest(self) -> Optional[RenPySDK]:
        """En son sürüm SDK'yı döndürür"""
        if not self._cache_valid:
            self.find_all()
        return self.found_sdks[0] if self.found_sdks else None
    
    def get_by_version(self, version: str) -> Optional[RenPySDK]:
        """Belirli sürüm SDK'yı döndürür"""
        if not self._cache_valid:
            self.find_all()
        
        for sdk in self.found_sdks:
            if sdk.version == version:
                return sdk
        return None
    
    def validate_path(self, path: str) -> Optional[RenPySDK]:
        """Kullanıcının verdiği bir yolu doğrular"""
        return self._validate_sdk(path)


def find_renpy_sdks(custom_paths: Optional[List[str]] = None) -> List[RenPySDK]:
    """
    Kolaylaştırıcı fonksiyon - sistemdeki tüm Ren'Py SDK'larını bulur.
    
    Args:
        custom_paths: Ek arama yolları
        
    Returns:
        Bulunan SDK'ların listesi
    """
    finder = SDKFinder()
    return finder.find_all(custom_paths)


if __name__ == "__main__":
    # Test
    print("Ren'Py SDK'ları aranıyor...")
    sdks = find_renpy_sdks()
    
    if sdks:
        print(f"\n{len(sdks)} SDK bulundu:\n")
        for sdk in sdks:
            print(f"  • {sdk}")
            print(f"    Path: {sdk.path}")
            print(f"    Script: {sdk.renpy_script}")
            print()
    else:
        print("Hiç SDK bulunamadı.")
