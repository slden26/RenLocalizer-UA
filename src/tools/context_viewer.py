# -*- coding: utf-8 -*-
"""
RenLocalizer Context Viewer Module
==================================

Provides context information for translation entries.
Shows WHERE each string appears in the game (screen, label, menu, etc.)
to help translators understand the usage context.

This helps with:
1. Disambiguating identical strings in different contexts
2. Understanding if text is dialogue, UI, or system message
3. Providing better translations with context awareness
"""

import os
import re
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum

from src.utils.encoding import read_text_safely


class ContextType(Enum):
    """Types of contexts where text can appear."""
    DIALOGUE = "dialogue"
    MENU = "menu"
    SCREEN = "screen"
    LABEL = "label"
    PYTHON = "python"
    NARRATOR = "narrator"
    TEXTBUTTON = "textbutton"
    TEXT = "text"
    CONFIG = "config"
    UNKNOWN = "unknown"


@dataclass
class TranslationContext:
    """Context information for a translation entry."""
    file_path: str
    line_number: int
    context_type: ContextType
    context_path: List[str]  # e.g., ["screen:main_menu", "vbox", "textbutton"]
    character: Optional[str] = None  # For dialogue
    parent_label: Optional[str] = None
    parent_screen: Optional[str] = None
    original_text: str = ""
    
    @property
    def context_string(self) -> str:
        """Human-readable context string."""
        parts = []
        
        if self.parent_screen:
            parts.append(f"screen:{self.parent_screen}")
        if self.parent_label:
            parts.append(f"label:{self.parent_label}")
        if self.character:
            parts.append(f"char:{self.character}")
        
        parts.append(self.context_type.value)
        
        return " > ".join(parts)
    
    @property
    def short_context(self) -> str:
        """Short context description."""
        if self.context_type == ContextType.DIALOGUE:
            return f"{self.character or 'narrator'} dialogue"
        elif self.context_type == ContextType.MENU:
            return "menu choice"
        elif self.context_type == ContextType.SCREEN:
            return f"screen:{self.parent_screen or 'unknown'}"
        elif self.context_type == ContextType.TEXTBUTTON:
            return "button text"
        elif self.context_type == ContextType.TEXT:
            return "UI text"
        else:
            return self.context_type.value
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'file': os.path.basename(self.file_path),
            'line': self.line_number,
            'type': self.context_type.value,
            'path': self.context_path,
            'character': self.character,
            'label': self.parent_label,
            'screen': self.parent_screen,
            'text_preview': self.original_text[:50] + "..." if len(self.original_text) > 50 else self.original_text
        }


class ContextAnalyzer:
    """
    Analyzes Ren'Py scripts to extract context information.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Regex patterns for context detection
        self._label_re = re.compile(r'^label\s+(\w+)\s*(?:\(.*\))?\s*:')
        self._screen_re = re.compile(r'^screen\s+(\w+)\s*(?:\(.*\))?\s*:')
        self._menu_re = re.compile(r'^\s*menu\s*(?:\w+)?\s*:')
        self._textbutton_re = re.compile(r'^\s*textbutton\s+[_]?\s*["\'](.+?)["\']')
        self._text_re = re.compile(r'^\s*text\s+[_]?\s*["\'](.+?)["\']')
        self._dialogue_re = re.compile(r'^\s*(\w+)\s+["\'](.+?)["\']')
        self._narrator_re = re.compile(r'^\s*["\'](.+?)["\']')
        self._python_re = re.compile(r'^\s*(init\s+)?python(\s+early)?\s*:')
    
    def analyze_file(self, file_path: str) -> List[TranslationContext]:
        """
        Analyze a .rpy file and extract context for all translatable text.
        
        Args:
            file_path: Path to .rpy file
        
        Returns:
            List of TranslationContext objects
        """
        contexts = []
        
        content = read_text_safely(Path(file_path))
        if content is None:
            self.logger.error(f"Could not read file: {file_path}")
            return contexts
        
        lines = content.split('\n')
        
        # Track current context
        current_label = None
        current_screen = None
        in_menu = False
        in_python = False
        indent_stack = []  # (indent_level, context_type, name)
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped:
                continue
            
            # Calculate indentation
            indent = len(line) - len(line.lstrip())
            
            # Update indent stack
            while indent_stack and indent <= indent_stack[-1][0]:
                popped = indent_stack.pop()
                if popped[1] == 'label':
                    current_label = None
                elif popped[1] == 'screen':
                    current_screen = None
                elif popped[1] == 'menu':
                    in_menu = False
                elif popped[1] == 'python':
                    in_python = False
            
            # Check for label
            label_match = self._label_re.match(stripped)
            if label_match:
                current_label = label_match.group(1)
                indent_stack.append((indent, 'label', current_label))
                continue
            
            # Check for screen
            screen_match = self._screen_re.match(stripped)
            if screen_match:
                current_screen = screen_match.group(1)
                indent_stack.append((indent, 'screen', current_screen))
                continue
            
            # Check for menu
            menu_match = self._menu_re.match(line)
            if menu_match:
                in_menu = True
                indent_stack.append((indent, 'menu', 'menu'))
                continue
            
            # Check for python block
            python_match = self._python_re.match(stripped)
            if python_match:
                in_python = True
                indent_stack.append((indent, 'python', 'python'))
                continue
            
            # Skip comments
            if stripped.startswith('#'):
                continue
            
            # Skip if in python block (handled separately)
            if in_python:
                continue
            
            # Check for textbutton
            textbutton_match = self._textbutton_re.match(line)
            if textbutton_match:
                text = textbutton_match.group(1)
                contexts.append(TranslationContext(
                    file_path=file_path,
                    line_number=i,
                    context_type=ContextType.TEXTBUTTON,
                    context_path=self._build_context_path(indent_stack),
                    parent_label=current_label,
                    parent_screen=current_screen,
                    original_text=text
                ))
                continue
            
            # Check for text
            text_match = self._text_re.match(line)
            if text_match:
                text = text_match.group(1)
                contexts.append(TranslationContext(
                    file_path=file_path,
                    line_number=i,
                    context_type=ContextType.TEXT,
                    context_path=self._build_context_path(indent_stack),
                    parent_label=current_label,
                    parent_screen=current_screen,
                    original_text=text
                ))
                continue
            
            # Check for dialogue (character "text")
            dialogue_match = self._dialogue_re.match(line)
            if dialogue_match and not in_menu:
                char = dialogue_match.group(1)
                text = dialogue_match.group(2)
                
                # Skip if it looks like a keyword
                if char.lower() in ('if', 'elif', 'else', 'while', 'for', 'return', 
                                    'pass', 'menu', 'label', 'screen', 'define', 
                                    'default', 'image', 'transform', 'style'):
                    continue
                
                contexts.append(TranslationContext(
                    file_path=file_path,
                    line_number=i,
                    context_type=ContextType.DIALOGUE,
                    context_path=self._build_context_path(indent_stack),
                    character=char,
                    parent_label=current_label,
                    parent_screen=current_screen,
                    original_text=text
                ))
                continue
            
            # Check for narrator (just "text") or menu choice
            narrator_match = self._narrator_re.match(line)
            if narrator_match:
                text = narrator_match.group(1)
                
                if in_menu:
                    context_type = ContextType.MENU
                else:
                    context_type = ContextType.NARRATOR
                
                contexts.append(TranslationContext(
                    file_path=file_path,
                    line_number=i,
                    context_type=context_type,
                    context_path=self._build_context_path(indent_stack),
                    parent_label=current_label,
                    parent_screen=current_screen,
                    original_text=text
                ))
        
        return contexts
    
    def _build_context_path(self, indent_stack: List[Tuple[int, str, str]]) -> List[str]:
        """Build context path from indent stack."""
        return [f"{ctx_type}:{name}" for _, ctx_type, name in indent_stack]
    
    def analyze_directory(self, directory: str) -> Dict[str, List[TranslationContext]]:
        """
        Analyze all .rpy files in a directory.
        
        Args:
            directory: Path to directory
        
        Returns:
            Dict mapping file paths to their contexts
        """
        results = {}
        
        for root, dirs, files in os.walk(directory):
            # Skip renpy engine folder
            if 'renpy' in dirs:
                dirs.remove('renpy')
            
            for filename in files:
                if filename.endswith('.rpy'):
                    file_path = os.path.join(root, filename)
                    contexts = self.analyze_file(file_path)
                    if contexts:
                        results[file_path] = contexts
        
        return results
    
    def get_context_summary(self, contexts: List[TranslationContext]) -> Dict[str, int]:
        """
        Get summary of context types.
        
        Args:
            contexts: List of contexts
        
        Returns:
            Dict mapping context type to count
        """
        summary = {}
        for ctx in contexts:
            ctx_type = ctx.context_type.value
            summary[ctx_type] = summary.get(ctx_type, 0) + 1
        return summary


class ContextEnhancedEntry:
    """
    A translation entry enhanced with context information.
    """
    
    def __init__(
        self,
        original_text: str,
        translated_text: str,
        context: Optional[TranslationContext] = None
    ):
        self.original_text = original_text
        self.translated_text = translated_text
        self.context = context
    
    @property
    def context_string(self) -> str:
        if self.context:
            return self.context.context_string
        return "unknown"
    
    @property
    def disambiguation_key(self) -> str:
        """
        Key for disambiguating identical strings.
        Same text in different contexts gets different keys.
        """
        if self.context:
            return f"{self.original_text}|{self.context.context_string}"
        return self.original_text
    
    def to_table_row(self) -> Tuple[str, str, str]:
        """Return tuple for table display: (original, translation, context)"""
        return (
            self.original_text[:50] + "..." if len(self.original_text) > 50 else self.original_text,
            self.translated_text[:50] + "..." if len(self.translated_text) > 50 else self.translated_text,
            self.context.short_context if self.context else "unknown"
        )


def enhance_with_context(
    entries: List[Dict],
    source_dir: str
) -> List[ContextEnhancedEntry]:
    """
    Enhance translation entries with context information.
    
    Args:
        entries: List of dicts with 'original' and 'translated' keys
        source_dir: Path to source .rpy files for context analysis
    
    Returns:
        List of ContextEnhancedEntry objects
    """
    analyzer = ContextAnalyzer()
    
    # Build context map from source files
    all_contexts = analyzer.analyze_directory(source_dir)
    
    # Flatten to text -> context mapping
    text_to_context = {}
    for file_path, contexts in all_contexts.items():
        for ctx in contexts:
            # Use first occurrence of each text
            if ctx.original_text not in text_to_context:
                text_to_context[ctx.original_text] = ctx
    
    # Enhance entries
    enhanced = []
    for entry in entries:
        original = entry.get('original', entry.get('original_text', ''))
        translated = entry.get('translated', entry.get('translated_text', ''))
        
        context = text_to_context.get(original)
        
        enhanced.append(ContextEnhancedEntry(
            original_text=original,
            translated_text=translated,
            context=context
        ))
    
    return enhanced
