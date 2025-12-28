# -*- coding: utf-8 -*-
"""
RenLocalizer Deferred Loading Module
====================================

Generates translation files with deferred loading support for large projects.
This prevents startup lag when games have thousands of translation strings.

Ren'Py's init system:
- init python -> init offset = N python (higher N = later loading)
- Deferred loading delays translation until language is first activated

Use cases:
1. Games with 10,000+ strings
2. Multiple language packs
3. DLC/expansion translations
"""

import os
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime


class DeferredLoadingGenerator:
    """
    Generates translation files with deferred loading for performance.
    """
    
    # Default init offset for deferred loading
    DEFAULT_OFFSET = 10
    
    def __init__(self, offset: int = DEFAULT_OFFSET):
        """
        Initialize generator.
        
        Args:
            offset: Init offset level (higher = later loading)
        """
        self.offset = offset
        self.logger = logging.getLogger(__name__)
    
    def wrap_with_offset(self, content: str, offset: Optional[int] = None) -> str:
        """
        Wrap translation content with init offset.
        
        Args:
            content: Original translation file content
            offset: Init offset (uses default if None)
        
        Returns:
            Content with init offset wrapper
        """
        use_offset = offset if offset is not None else self.offset
        
        # Add header with offset
        header = f"""\
# -*- coding: utf-8 -*-
# RenLocalizer Deferred Loading
# Generated: {datetime.now().isoformat()}
# This file uses deferred loading for performance optimization.

init offset = {use_offset}

"""
        return header + content
    
    def generate_language_pack_loader(
        self,
        language: str,
        pack_files: List[str],
        base_path: str
    ) -> str:
        """
        Generate a language pack loader that conditionally loads translation files.
        
        This creates a master loader that only loads translations when the
        language is actually selected.
        
        Args:
            language: Language code (e.g., 'turkish')
            pack_files: List of translation file paths to include
            base_path: Base path for relative imports
        
        Returns:
            Loader script content
        """
        loader_content = f"""\
# -*- coding: utf-8 -*-
# RenLocalizer Language Pack Loader
# Language: {language}
# Generated: {datetime.now().isoformat()}
#
# This loader implements deferred loading for the {language} language pack.
# Translation files are only loaded when this language is activated.

init -10 python:
    # Register language pack
    _renloc_language_packs = getattr(renpy.store, '_renloc_language_packs', {{}})
    _renloc_language_packs['{language}'] = {{
        'loaded': False,
        'files': {pack_files!r}
    }}
    renpy.store._renloc_language_packs = _renloc_language_packs

init python:
    def _renloc_load_language_pack(language):
        \"\"\"Load a language pack if not already loaded.\"\"\"
        packs = getattr(renpy.store, '_renloc_language_packs', {{}})
        pack = packs.get(language)
        
        if pack and not pack['loaded']:
            # Mark as loaded to prevent double-loading
            pack['loaded'] = True
            renpy.notify("Loading language pack...")
            
            # Force reload of translation files
            renpy.translation.init()
    
    # Hook into language change
    config.after_change_language = _renloc_load_language_pack

# Language definition
define config.language = None  # Let user choose

# Translations follow below with deferred init
init offset = {self.offset}

"""
        return loader_content
    
    def estimate_load_time(self, string_count: int, file_count: int) -> dict:
        """
        Estimate loading performance impact.
        
        Args:
            string_count: Total number of translation strings
            file_count: Number of translation files
        
        Returns:
            Dict with performance estimates
        """
        # Rough estimates based on typical Ren'Py performance
        # These are approximations and will vary by system
        
        parse_time_per_string = 0.0001  # ~0.1ms per string
        file_overhead_per_file = 0.01   # ~10ms per file
        
        estimated_parse_time = string_count * parse_time_per_string
        estimated_file_time = file_count * file_overhead_per_file
        total_time = estimated_parse_time + estimated_file_time
        
        return {
            'string_count': string_count,
            'file_count': file_count,
            'estimated_parse_time_sec': round(estimated_parse_time, 3),
            'estimated_file_time_sec': round(estimated_file_time, 3),
            'total_estimated_time_sec': round(total_time, 3),
            'recommendation': self._get_recommendation(string_count, file_count)
        }
    
    def _get_recommendation(self, string_count: int, file_count: int) -> str:
        """Get performance recommendation based on project size."""
        if string_count > 10000:
            return "STRONGLY RECOMMEND deferred loading - large project"
        elif string_count > 5000:
            return "RECOMMEND deferred loading - medium-large project"
        elif string_count > 1000:
            return "OPTIONAL - deferred loading may help"
        else:
            return "NOT NEEDED - project is small enough"
    
    def should_use_deferred(self, string_count: int) -> bool:
        """Check if deferred loading is recommended."""
        return string_count > 5000


class LanguagePackGenerator:
    """
    Generates modular language packs for distribution.
    
    Benefits:
    1. Users can download only languages they need
    2. Smaller initial download size
    3. Easy to add new languages post-release
    """
    
    def __init__(self, deferred: bool = True):
        self.deferred = deferred
        self.deferred_gen = DeferredLoadingGenerator() if deferred else None
        self.logger = logging.getLogger(__name__)
    
    def generate_pack_structure(
        self,
        language: str,
        output_dir: str
    ) -> dict:
        """
        Generate recommended folder structure for a language pack.
        
        Args:
            language: Language code
            output_dir: Output directory
        
        Returns:
            Dict describing created structure
        """
        structure = {
            'root': os.path.join(output_dir, f'langpack_{language}'),
            'tl': os.path.join(output_dir, f'langpack_{language}', 'game', 'tl', language),
            'manifest': os.path.join(output_dir, f'langpack_{language}', 'manifest.txt'),
        }
        
        # Create directories
        os.makedirs(structure['tl'], exist_ok=True)
        
        # Create manifest
        manifest_content = f"""\
# RenLocalizer Language Pack
# Language: {language}
# Generated: {datetime.now().isoformat()}
#
# Installation:
# 1. Copy the 'game' folder into your game directory
# 2. Start the game and select {language} from language menu
#
# This pack was generated with deferred loading: {self.deferred}
"""
        
        with open(structure['manifest'], 'w', encoding='utf-8') as f:
            f.write(manifest_content)
        
        return structure
    
    def create_archive_script(self, language: str, output_dir: str) -> str:
        """
        Generate a script to create an RPA archive for the language pack.
        
        Returns:
            Path to generated script
        """
        script_content = f"""\
# Language Pack Archive Script
# Run this with Ren'Py SDK to create an RPA archive

import os
import sys

# Add Ren'Py to path
renpy_path = r"C:\\Program Files\\RenPy"  # Adjust as needed
sys.path.insert(0, renpy_path)

try:
    from renpy import archiver
    
    pack_dir = os.path.join(os.path.dirname(__file__), 'game')
    output_file = 'langpack_{language}.rpa'
    
    archiver.archive(pack_dir, output_file)
    print(f"Created: {{output_file}}")
except ImportError:
    print("Ren'Py SDK not found. Please install Ren'Py SDK to create RPA archives.")
"""
        
        script_path = os.path.join(output_dir, f'create_archive_{language}.py')
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        return script_path
