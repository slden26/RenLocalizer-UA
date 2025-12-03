"""
Simple RenPy Parser - Working Version
"""

import re
import logging
from pathlib import Path
from typing import Set, Union
import chardet

class RenPyParser:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Core dialogue patterns
        self.char_dialog_re = re.compile(r'^(?P<indent>\s*)(?P<char>[A-Za-z_]\w*)\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
        self.narrator_re = re.compile(r'^(?P<indent>\s*)(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*(?:#.*)?$')
        
        # Menu and choice patterns
        self.menu_choice_re = re.compile(r'^\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')\s*:\s*')
        self.menu_title_re = re.compile(r'^\s*menu\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')?:')
        
        # UI element patterns
        self.screen_text_re = re.compile(r'^\s*(?:text|label|tooltip)\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
        self.textbutton_re = re.compile(r'^\s*textbutton\s+(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
        
        # Config and GUI patterns  
        self.config_string_re = re.compile(r'^\s*config\.(?:name|version|about|menu_|window_title|save_name)\s*=\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
        self.gui_text_re = re.compile(r'^\s*gui\.(?:text|button|label|title|heading|caption|tooltip|confirm)(?:_[a-z_]*)?(?:\[[^\]]*\])?\s*=\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')          # Style property assignments
        self.style_property_re = re.compile(r'^\s*style\s*\.\s*[a-zA-Z_]\w*\s*=\s*(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
        
        # Python expressions with $ prefix
        self.python_renpy_re = re.compile(r'^\s*\$\s+.*?(?:renpy\.)?(?:input|notify)\s*\([^)]*?(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
        
        # RenPy function calls
        self.renpy_function_re = re.compile(r'^\s*(?:renpy\.)?(?:input|notify)\s*\([^)]*?(?P<quote>"(?:[^"\\]|\\.)*"|\'(?:[^\\\']|\\.)*\')')
        
        # Technical terms to exclude
        self.renpy_technical_terms = {
            'left', 'right', 'center', 'top', 'bottom', 'gui', 'config',
            'true', 'false', 'none', 'auto', 'png', 'jpg', 'mp3', 'ogg'
        }
        
    def extract_translatable_text(self, file_path: Union[str, Path]) -> Set[str]:
        """Extract translatable text from a .rpy file."""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                detected = chardet.detect(raw_data)
                encoding = detected.get('encoding', 'utf-8')
            
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                content = f.read()
            
            lines = content.splitlines()
            translatable_texts = set()
            
            for line_num, line in enumerate(lines, 1):
                patterns = [
                    self.char_dialog_re,
                    self.narrator_re,
                    self.menu_choice_re,
                    self.menu_title_re,
                    self.screen_text_re,
                    self.textbutton_re,
                    self.config_string_re,
                    self.gui_text_re,
                    self.style_property_re,
                    self.python_renpy_re,
                    self.renpy_function_re
                ]
                
                for pattern in patterns:
                    match = pattern.match(line)
                    if match:
                        for group_name in match.groupdict():
                            if 'quote' in group_name and match.group(group_name):
                                text = self._extract_string_content(match.group(group_name))
                                if text and self.is_meaningful_text(text):
                                    translatable_texts.add(text)
                        break
                        
            return translatable_texts
            
        except Exception as e:
            self.logger.error(f"Error parsing {file_path}: {e}")
            return set()
    
    def _extract_string_content(self, quoted_string: str) -> str:
        """Extract content from a quoted string."""
        if not quoted_string:
            return ""
        
        if quoted_string.startswith('"') and quoted_string.endswith('"'):
            content = quoted_string[1:-1]
        elif quoted_string.startswith("'") and quoted_string.endswith("'"):
            content = quoted_string[1:-1]
        else:
            content = quoted_string
        
        content = content.replace('\\"', '"').replace("\\'", "'")
        content = content.replace('\\n', '\n').replace('\\t', '\t')
        
        return content.strip()
    
    def is_meaningful_text(self, text: str) -> bool:
        """Check if text is meaningful dialogue/story content."""
        if not text or len(text.strip()) < 2:
            return False
        
        text_lower = text.lower().strip()
        
        if text_lower in self.renpy_technical_terms:
            return False
        
        if any(ext in text_lower for ext in ['.png', '.jpg', '.mp3', '.ogg']):
            return False
        
        # Skip pure numbers but allow version numbers (contain dots)
        if re.match(r'^[-+]?\d+$', text.strip()):
            return False
        
        # Allow version-like strings (numbers with dots, e.g., "1.0.0", "2.1")
        if re.match(r'^\d+(?:\.\d+)+$', text.strip()):
            return True
        
        if re.search(r'[a-zA-ZçğıöşüÇĞIİÖŞÜ]', text) and len(text.strip()) >= 2:
            return True
        
        return False
    
    def determine_text_type(self, text: str, context_line: str = "") -> str:
        """Determine the type of text based on content and context."""
        if not context_line:
            return 'dialogue'
        
        context_lower = context_line.lower()
        
        if 'textbutton' in context_lower:
            return 'button'
        elif 'menu' in context_lower:
            return 'menu'
        elif 'screen' in context_lower:
            return 'ui'
        elif 'config.' in context_lower:
            return 'config'
        elif 'gui.' in context_lower:
            return 'gui'
        elif 'style.' in context_lower:
            return 'style'
        else:
            return 'dialogue'
