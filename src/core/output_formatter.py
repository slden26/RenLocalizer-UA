"""
Output Formatter
===============

Formats translation results into Ren'Py translate block format.
"""

import logging
from typing import List, Dict, Set, TYPE_CHECKING
from pathlib import Path
import re

if TYPE_CHECKING:
    from src.core.translator import TranslationResult

class RenPyOutputFormatter:
    """Formats translations into Ren'Py translate block format."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def sanitize_translation_id(self, text: str) -> str:
        """Create a valid Ren'Py translation ID from text."""
        # Remove special characters and replace with underscores
        text = re.sub(r'[^a-zA-Z0-9_]', '_', text)
        
        # Remove multiple underscores
        text = re.sub(r'_+', '_', text)
        
        # Remove leading/trailing underscores
        text = text.strip('_')
        
        # Ensure it starts with a letter or underscore
        if text and text[0].isdigit():
            text = '_' + text
        
        # Limit length
        if len(text) > 50:
            text = text[:50]
        
        # Ensure it's not empty
        if not text:
            text = 'translated_text'
        
        return text
    
    def escape_renpy_string(self, text: str) -> str:
        """Escape special characters for Ren'Py strings."""
        # More careful escaping to avoid breaking translations
        # CRITICAL: Don't break Ren'Py variables, placeholders, and tags
        
        # First, temporarily protect Ren'Py variables and expressions
        import re
        
        # Find all Ren'Py variables [variable] and expressions
        variable_pattern = re.compile(r'\[[^\[\]]+\]')
        variables = variable_pattern.findall(text)
        
        # Find all Ren'Py tags like {i}, {b}, {color=#ff0000}, {/i}, etc.
        tag_pattern = re.compile(r'\{[^{}]*\}')
        tags = tag_pattern.findall(text)
        
        # Replace variables and tags with placeholders temporarily
        temp_text = text
        protection_map = {}
        
        # Protect variables
        for i, var in enumerate(variables):
            placeholder = f"__VAR_{i}__"
            protection_map[placeholder] = var
            temp_text = temp_text.replace(var, placeholder, 1)
        
        # Protect tags
        for i, tag in enumerate(tags):
            placeholder = f"__TAG_{i}__"
            protection_map[placeholder] = tag
            temp_text = temp_text.replace(tag, placeholder, 1)
        
        # Now escape the rest
        temp_text = temp_text.replace('\\', '\\\\')  # Escape backslashes first
        temp_text = temp_text.replace('"', '\\"')     # Escape double quotes
        
        # Restore variables and tags
        for placeholder, original_content in protection_map.items():
            temp_text = temp_text.replace(placeholder, original_content)
        
        return temp_text
    
    def generate_translation_block(self, 
                                 original_text: str, 
                                 translated_text: str, 
                                 language_code: str,
                                 translation_id: str = None,
                                 context: str = None,
                                 mode: str = "simple") -> str:
        """Generate a single translation block."""
        
        if not translation_id:
            # Create string-based translation that matches any label
            # This is more compatible with existing Ren'Py games
            import hashlib
            text_hash = hashlib.md5(original_text.encode('utf-8')).hexdigest()[:8]
            translation_id = f"strings_{text_hash}"
        
        escaped_original = self.escape_renpy_string(original_text)
        escaped_translated = self.escape_renpy_string(translated_text)
        
        if mode == "old_new":
            # Old/new format - INDIVIDUAL ENTRY (for building larger block)
            block = (
                f"    old \"{escaped_original}\"\n"
                f"    new \"{escaped_translated}\"\n\n"
            )
        else:
            # Simple format - original text in comment, direct translation line
            comment_original = escaped_original.replace('\n', '\\n')
            block = (
                f"    # \"{comment_original}\"\n"
                f"    \"{escaped_translated}\"\n\n"
            )
        
        return block
    
    def generate_character_translation(self,
                                     character_name: str,
                                     original_text: str,
                                     translated_text: str,
                                     language_code: str,
                                     translation_id: str = None,
                                     mode: str = "simple") -> str:
        """Generate a character dialogue translation block."""
        
        escaped_original = self.escape_renpy_string(original_text)
        escaped_translated = self.escape_renpy_string(translated_text)
        
        if mode == "old_new":
            # String-based format - INDIVIDUAL ENTRY (for building larger block)
            block = (
                f"    old {character_name} \"{escaped_original}\"\n"
                f"    new {character_name} \"{escaped_translated}\"\n\n"
            )
        else:
            # Simple format - original text in comment, direct translation line
            comment_original = escaped_original.replace('\n', '\\n')
            block = (
                f"    # {character_name} \"{comment_original}\"\n"
                f"    {character_name} \"{escaped_translated}\"\n\n"
            )
        
        return block
    
    def generate_menu_translation(self,
                                menu_options: List[Dict],
                                language_code: str,
                                menu_id: str = None) -> str:
        """Generate menu translation block - DEPRECATED. 
        
        Menu translations should use translate strings format instead.
        This method is kept for compatibility but menu items should be 
        included in the main strings block.
        """
        
        # Menu choices should be in translate strings block, not separate menu blocks
        # According to RenPy documentation: menu choices use "translate strings" format
        
        block = f"# NOTE: Menu choices should be in 'translate {language_code} strings:' block\n"
        block += f"# This is the old format and may not work properly in RenPy\n\n"
        
        if not menu_id:
            menu_id = f"menu_{self.sanitize_translation_id('_'.join([opt['original'] for opt in menu_options[:3]]))}"
        
        block += f"translate {language_code} {menu_id}:\n\n"
        
        for i, option in enumerate(menu_options):
            original = self.escape_renpy_string(option['original'])
            translated = self.escape_renpy_string(option['translated'])
            # Add each choice with real newlines
            block += f'    # "{original}"\n'
            block += f'    "{translated}"\n'
        
        block += "\n"
        return block
    
    def format_translation_file(self,
                              translation_results: List,
                              language_code: str,
                              source_file: Path = None,
                              include_header: bool = True,
                              output_format: str = "old_new") -> str:
        """Format complete translation file with SEPARATE blocks for each translation."""
        
        output_lines = []
        
        if include_header:
            header = self.generate_file_header(language_code, source_file)
            output_lines.append(header)
        
        # CRITICAL FIX: Create ONE translate strings block for ALL translations
        # This is the CORRECT Ren'Py format
        
        seen_translations = set()
        string_translations = []
        
        # Add the opening translate strings block
        string_translations.append(f"translate {language_code} strings:")
        string_translations.append("")
        
        for result in translation_results:
            if not result.success or not result.translated_text:
                continue
            
            # Avoid duplicates
            key = f"{result.original_text}_{result.translated_text}"
            if key in seen_translations:
                continue
            seen_translations.add(key)
            
            escaped_original = self.escape_renpy_string(result.original_text)
            escaped_translated = self.escape_renpy_string(result.translated_text)
            
            # Add translation pairs based on output format
            if output_format == "old_new":
                # OLD_NEW format - more explicit
                string_translations.append(f'    old "{escaped_original}"')
                string_translations.append(f'    new "{escaped_translated}"')
                string_translations.append("")  # Empty line between pairs
            else:
                # SIMPLE format - original text as comment, translated line only
                comment_original = escaped_original.replace('\n', '\\n')
                string_translations.append(f'    # "{comment_original}"')
                string_translations.append(f'    "{escaped_translated}"')
                string_translations.append("")  # Empty line between pairs
        
        # Combine header and strings
        output_lines.extend(string_translations)
        
        # Join sections with real newlines
        return "\n".join(output_lines)
    
    def generate_file_header(self, language_code: str, source_file: Path = None) -> str:
        """Generate file header with metadata."""
        from datetime import datetime
        
        header = f"""# Ren'Py Translation File
# Language: {language_code}
# Generated by: RenLocalizer v2.0.1
# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        if source_file:
            header += f"# Source file: {source_file}\\n"
        
        header += """
# This file contains automatic translations.
# Please review and edit as needed.

"""
        return header
    
    def save_translation_file(self,
                            translation_results: List,
                            output_path: Path,
                            language_code: str,
                            source_file: Path = None,
                            output_format: str = "simple") -> bool:
        """Save translations to file."""
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate content
            content = self.format_translation_file(
                translation_results,
                language_code,
                source_file,
                output_format=output_format
            )
            
            # Write file with UTF-8 encoding
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.info(f"Saved translation file: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving translation file {output_path}: {e}")
            return False
    
    def organize_output_files(self,
                            translation_results: List,
                            output_base_dir: Path,
                            language_code: str,
                            source_files: List[Path] = None,
                            output_format: str = "old_new",
                            create_renpy_structure: bool = True) -> List[Path]:
        """Organize translations into language-specific directories."""
        
        output_files = []
        
        # Determine if this is a Ren'Py project and create proper structure
        if create_renpy_structure:
            # Check if we're in a Ren'Py project (has game folder)
            game_dir = self._find_game_directory(output_base_dir)
            if game_dir:
                # Create Ren'Py translation structure: game/tl/[language]/
                lang_dir = game_dir / "tl" / language_code
                self.logger.info(f"Creating Ren'Py translation structure: {lang_dir}")
                
                # Create language initialization file for Ren'Py - do it immediately
                self._create_language_init_file(game_dir, language_code)
            else:
                # Not a Ren'Py project, create standard structure
                lang_dir = output_base_dir / language_code
                self.logger.info(f"Creating standard translation structure: {lang_dir}")
        else:
            # Create language directory
            lang_dir = output_base_dir / language_code
        
        lang_dir.mkdir(parents=True, exist_ok=True)
        
        # CRITICAL FIX: Create ONE translation file for all strings
        # This prevents duplicate string errors in Ren'Py
        
        # Global deduplication - remove duplicates across ALL files
        seen_strings = set()
        unique_results = []
        
        for result in translation_results:
            string_key = result.original_text.strip().lower()
            if string_key not in seen_strings:
                seen_strings.add(string_key)
                unique_results.append(result)
            else:
                self.logger.debug(f"Skipping duplicate string: {result.original_text[:50]}...")
        
        # Create single master translation file
        output_filename = f"translations_{language_code}.rpy"
        output_path = lang_dir / output_filename
        
        if self.save_translation_file(
            unique_results, 
            output_path, 
            language_code, 
            None,  # No specific source file
            output_format=output_format
        ):
            output_files.append(output_path)
            self.logger.info(f"Created master translation file: {output_path} with {len(unique_results)} unique strings")
        
        return output_files
    
    def _find_game_directory(self, base_path: Path) -> Path:
        """Find the game directory in a Ren'Py project."""
        # Check current directory and parent directories for 'game' folder
        current = Path(base_path).resolve()
        
        # Check if current path contains 'game' folder
        if (current / "game").exists() and (current / "game").is_dir():
            return current / "game"
        
        # Check parent directories
        for parent in current.parents:
            game_dir = parent / "game"
            if game_dir.exists() and game_dir.is_dir():
                # Verify it's a Ren'Py game directory by checking for common files
                if any((game_dir / file).exists() for file in ["options.rpy", "script.rpy", "gui.rpy"]):
                    return game_dir
        
        # Check if current directory itself is the game directory
        if any((current / file).exists() for file in ["options.rpy", "script.rpy", "gui.rpy"]):
            return current
        
        return None
    
    def _create_language_init_file(self, game_dir: Path, language_code: str):
        """RenPy dökümantasyonuna tam uyumlu, sade başlatıcı dosya üretimi."""
        try:
            init_file_path = game_dir / f"a0_{language_code}_language.rpy"
            init_content = f'define config.language = "{language_code}"\n'
            with open(init_file_path, 'w', encoding='utf-8') as f:
                f.write(init_content)
            self.logger.info(f"Created minimal language file: {init_file_path}")
        except Exception as e:
            self.logger.error(f"Error creating language init file: {e}")
