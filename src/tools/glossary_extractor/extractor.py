
# -*- coding: utf-8 -*-
"""
Glossary Extractor Tool
=======================

Extracts potential glossary terms (character names, common nouns) from Ren'Py scripts.
"""

import os
import re
from collections import Counter
from typing import Dict, List, Set, Tuple

class GlossaryExtractor:
    """Analyzes Ren'Py files to find potential glossary terms."""
    
    def __init__(self):
        # Regex for character definitions: define e = Character("Eileen")
        self.char_def_pattern = re.compile(r'define\s+(\w+)\s*=\s*Character\s*\(\s*(?:_\()?"([^"]+)"')
        
        # Regex for character speaking: e "Hello"
        self.dialogue_pattern = re.compile(r'^\s*(\w+)\s+"', re.MULTILINE)
        
        # Regex for capitalized words in text (potential proper nouns)
        # Excludes beginning of sentences roughly
        self.proper_noun_pattern = re.compile(r'(?<!^)(?<!\.\s)(?<!\?\s)(?<!\!\s)(?<!\"\s)\b([A-Z][a-z]+)\b')

    def extract_from_directory(self, project_path: str, min_occurrence: int = 3) -> Dict[str, str]:
        """
        Scan directory and return a dict of {source_term: translation_stub}.
        """
        project_path = os.path.abspath(project_path)
        game_dir = os.path.join(project_path, "game") if os.path.isdir(os.path.join(project_path, "game")) else project_path
        
        character_map = {}  # var_name -> display_name
        term_counter = Counter()
        
        # 1. Scan for character definitions
        for root, _, files in os.walk(game_dir):
            for file in files:
                if file.endswith('.rpy'):
                    file_path = os.path.join(root, file)
                    self._scan_file(file_path, character_map, term_counter)
        
        # 2. Build result dictionary
        results = {}
        
        # Add characters (High priority)
        for var_name, display_name in character_map.items():
            if display_name not in results:
                results[display_name] = ""  # Empty translation by default
        
        # Add common terms
        for term, count in term_counter.most_common(50):
            if count >= min_occurrence and term not in results:
                # Filter out likely common words (very basic filter)
                if len(term) > 3: 
                    results[term] = ""
                    
        return results

    def _scan_file(self, file_path: str, char_map: Dict, term_counter: Counter):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Find definitions
            for match in self.char_def_pattern.finditer(content):
                var_name = match.group(1)
                display_name = match.group(2)
                char_map[var_name] = display_name
                
            # Find potential proper nouns in dialogue
            # This is tricky; for now we rely on explicit character defs mostly.
            # But let's look for repeated capitalized words in strings
            
            # Simple string extraction
            strings = re.findall(r'"([^"]+)"', content)
            for s in strings:
                # Find capitalized words inside strings
                matches = self.proper_noun_pattern.findall(s)
                for m in matches:
                    term_counter[m] += 1
                    
        except Exception as e:
            print(f"Error scanning {file_path}: {e}")

