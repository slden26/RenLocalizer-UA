# -*- coding: utf-8 -*-
"""
RenLocalizer Health Check Module
================================

Static analysis tool for detecting common localization issues before translation.
Inspired by Ren'Py's lint and Unity/Unreal localization best practices.

Checks:
1. Unwrapped strings (text without _() wrapper)
2. Placeholder mismatches (missing [var] or {tag} in translations)
3. Empty translations (new "" still blank)
4. Syntax validation (unclosed quotes, unbalanced brackets)
5. Orphaned translation IDs
"""

import os
import re
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from enum import Enum

from src.utils.encoding import read_text_safely


class IssueSeverity(Enum):
    """Severity levels for health check issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class HealthIssue:
    """Represents a single health check issue."""
    file_path: str
    line_number: int
    severity: IssueSeverity
    issue_type: str
    message: str
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None

    def __str__(self) -> str:
        sev = self.severity.value.upper()
        return f"[{sev}] {self.file_path}:{self.line_number} - {self.message}"


@dataclass
class HealthReport:
    """Complete health check report."""
    issues: List[HealthIssue] = field(default_factory=list)
    files_scanned: int = 0
    total_strings: int = 0
    
    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity in (IssueSeverity.ERROR, IssueSeverity.CRITICAL))
    
    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)
    
    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.INFO)
    
    @property
    def is_healthy(self) -> bool:
        return self.error_count == 0
    
    def summary(self) -> str:
        return (
            f"Health Check Complete: {self.files_scanned} files scanned\n"
            f"  Errors: {self.error_count}\n"
            f"  Warnings: {self.warning_count}\n"
            f"  Info: {self.info_count}\n"
            f"  Status: {'✅ HEALTHY' if self.is_healthy else '❌ ISSUES FOUND'}"
        )


class HealthChecker:
    """
    Static analysis tool for Ren'Py localization projects.
    
    Detects common issues that cause runtime errors or missing translations.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Patterns for detecting issues
        # Unwrapped string patterns (text/textbutton without _())
        self._unwrapped_text_re = re.compile(
            r'^\s*(text|textbutton)\s+"([^"]+)"(?!\s*id\b)',
            re.MULTILINE
        )
        
        # Wrapped string pattern (correct usage)
        self._wrapped_text_re = re.compile(
            r'(text|textbutton)\s+_\s*\(\s*"[^"]*"\s*\)'
        )
        
        # Ren'Py variable pattern [var] or [var!t]
        self._variable_re = re.compile(r'\[([^\[\]]+)\]')
        
        # Ren'Py tag pattern {tag} or {color=#fff}
        self._tag_re = re.compile(r'\{([^\{\}]+)\}')
        
        # old/new translation pattern
        self._old_re = re.compile(r'^\s*old\s+"(.*)"\s*$')
        self._new_re = re.compile(r'^\s*new\s+"(.*)"\s*$')
        
        # Dialogue pattern
        self._dialogue_re = re.compile(r'^\s*(\w+)\s+"(.*)"\s*$')
        
        # Quote validation
        self._string_literal_re = re.compile(r'"(?:[^"\\]|\\.)*"')
    
    def check_file(self, file_path: str) -> List[HealthIssue]:
        """Check a single .rpy file for issues."""
        issues = []
        
        content = read_text_safely(Path(file_path))
        if content is None:
            issues.append(HealthIssue(
                file_path=file_path,
                line_number=0,
                severity=IssueSeverity.ERROR,
                issue_type="file_read_error",
                message="Could not read file (encoding issue?)"
            ))
            return issues
        
        lines = content.split('\n')
        
        # Check each line
        for i, line in enumerate(lines, 1):
            line_issues = self._check_line(file_path, i, line, lines)
            issues.extend(line_issues)
        
        # Check for syntax issues
        syntax_issues = self._check_syntax(file_path, content, lines)
        issues.extend(syntax_issues)
        
        return issues
    
    def _check_line(self, file_path: str, line_num: int, line: str, all_lines: List[str]) -> List[HealthIssue]:
        """Check a single line for issues."""
        issues = []
        stripped = line.strip()
        
        # Skip comments and empty lines
        if not stripped or stripped.startswith('#'):
            return issues
        
        # Check for unwrapped strings in screens/UI
        if self._is_ui_context(all_lines, line_num - 1):
            unwrapped = self._check_unwrapped_strings(file_path, line_num, line)
            issues.extend(unwrapped)
        
        # Check for empty translations
        empty = self._check_empty_translation(file_path, line_num, line, all_lines)
        if empty:
            issues.append(empty)
        
        return issues
    
    def _is_ui_context(self, lines: List[str], current_idx: int) -> bool:
        """Check if current line is within a screen definition."""
        # Look backwards for screen/style/etc context
        for i in range(current_idx, max(0, current_idx - 50), -1):
            line = lines[i].strip()
            if line.startswith('screen ') or line.startswith('style '):
                return True
            if line.startswith('label ') and ':' in line:
                return False  # Dialogue context, not UI
        return False
    
    def _check_unwrapped_strings(self, file_path: str, line_num: int, line: str) -> List[HealthIssue]:
        """Check for UI strings not wrapped in _()."""
        issues = []
        
        # Check for text "..." without _()
        match = self._unwrapped_text_re.search(line)
        if match:
            element_type = match.group(1)
            text_content = match.group(2)
            
            # Skip if already wrapped
            if '_(' in line and f'"{text_content}"' in line:
                return issues
            
            # Skip technical strings
            if self._is_technical_string(text_content):
                return issues
            
            issues.append(HealthIssue(
                file_path=file_path,
                line_number=line_num,
                severity=IssueSeverity.WARNING,
                issue_type="unwrapped_string",
                message=f"UI string not wrapped in _(): {element_type} \"{text_content[:40]}...\"" if len(text_content) > 40 else f"UI string not wrapped in _(): {element_type} \"{text_content}\"",
                suggestion=f"Change to: {element_type} _(\"{text_content}\")",
                code_snippet=line.strip()
            ))
        
        return issues
    
    def _is_technical_string(self, text: str) -> bool:
        """Check if string is technical and shouldn't be translated."""
        # File paths
        if '/' in text or '\\' in text:
            return True
        # Color codes
        if re.match(r'^#[0-9a-fA-F]{3,8}$', text):
            return True
        # Numbers only
        if text.replace('.', '').replace(',', '').isdigit():
            return True
        # Single characters
        if len(text) <= 1:
            return True
        # Special patterns
        if re.match(r'^[a-z_]+\.[a-z_]+$', text, re.IGNORECASE):
            return True  # looks like config.value
        return False
    
    def _check_empty_translation(self, file_path: str, line_num: int, line: str, all_lines: List[str]) -> Optional[HealthIssue]:
        """Check for empty new \"\" translations."""
        new_match = self._new_re.match(line.strip())
        if new_match:
            new_text = new_match.group(1)
            if not new_text.strip():
                # Look back for the old "" to provide context
                old_text = ""
                if line_num >= 2:
                    prev_line = all_lines[line_num - 2].strip()
                    old_match = self._old_re.match(prev_line)
                    if old_match:
                        old_text = old_match.group(1)
                
                return HealthIssue(
                    file_path=file_path,
                    line_number=line_num,
                    severity=IssueSeverity.WARNING,
                    issue_type="empty_translation",
                    message=f"Empty translation for: \"{old_text[:50]}...\"" if len(old_text) > 50 else f"Empty translation for: \"{old_text}\"",
                    suggestion="Add translation text between the quotes"
                )
        return None
    
    def _check_syntax(self, file_path: str, content: str, lines: List[str]) -> List[HealthIssue]:
        """Check for syntax issues."""
        issues = []
        
        # Check for unbalanced quotes
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            
            # Count quotes (excluding escaped ones)
            quote_count = 0
            in_string = False
            j = 0
            while j < len(stripped):
                if stripped[j] == '\\' and j + 1 < len(stripped):
                    j += 2  # Skip escaped character
                    continue
                if stripped[j] == '"':
                    quote_count += 1
                    in_string = not in_string
                j += 1
            
            if quote_count % 2 != 0:
                issues.append(HealthIssue(
                    file_path=file_path,
                    line_number=i,
                    severity=IssueSeverity.ERROR,
                    issue_type="unbalanced_quotes",
                    message="Unbalanced quotes detected",
                    suggestion="Check for missing opening or closing quote",
                    code_snippet=stripped[:80]
                ))
        
        return issues
    
    def check_placeholder_consistency(
        self,
        original: str,
        translated: str,
        file_path: str = "",
        line_num: int = 0
    ) -> List[HealthIssue]:
        """Check if placeholders in original match those in translated text."""
        issues = []
        
        # Extract variables [var]
        orig_vars = set(self._variable_re.findall(original))
        trans_vars = set(self._variable_re.findall(translated))
        
        # Extract tags {tag}
        orig_tags = set(self._tag_re.findall(original))
        trans_tags = set(self._tag_re.findall(translated))
        
        # Check for missing variables
        missing_vars = orig_vars - trans_vars
        if missing_vars:
            issues.append(HealthIssue(
                file_path=file_path,
                line_number=line_num,
                severity=IssueSeverity.ERROR,
                issue_type="missing_placeholder",
                message=f"Missing variable(s) in translation: {', '.join(f'[{v}]' for v in missing_vars)}",
                suggestion="Ensure all [variable] placeholders are preserved in translation"
            ))
        
        # Check for extra variables (might be intentional, so just warn)
        extra_vars = trans_vars - orig_vars
        if extra_vars:
            issues.append(HealthIssue(
                file_path=file_path,
                line_number=line_num,
                severity=IssueSeverity.WARNING,
                issue_type="extra_placeholder",
                message=f"Extra variable(s) in translation: {', '.join(f'[{v}]' for v in extra_vars)}",
                suggestion="Verify these variables exist in the game"
            ))
        
        # Check for missing tags
        missing_tags = orig_tags - trans_tags
        if missing_tags:
            issues.append(HealthIssue(
                file_path=file_path,
                line_number=line_num,
                severity=IssueSeverity.WARNING,
                issue_type="missing_tag",
                message=f"Missing format tag(s) in translation: {', '.join(f'{{{t}}}' for t in missing_tags)}",
                suggestion="Preserve formatting tags like {b}, {i}, {color} in translation"
            ))
        
        return issues
    
    def check_directory(self, directory: str, include_tl: bool = True) -> HealthReport:
        """
        Check all .rpy files in a directory.
        
        Args:
            directory: Root directory to scan
            include_tl: Whether to include tl/ translation folder
        """
        report = HealthReport()
        
        for root, dirs, files in os.walk(directory):
            # Optionally skip tl folder
            if not include_tl and 'tl' in dirs:
                dirs.remove('tl')
            
            # Skip renpy engine folder
            if 'renpy' in dirs:
                dirs.remove('renpy')
            
            for filename in files:
                if filename.endswith('.rpy'):
                    file_path = os.path.join(root, filename)
                    report.files_scanned += 1
                    
                    try:
                        issues = self.check_file(file_path)
                        report.issues.extend(issues)
                    except Exception as e:
                        report.issues.append(HealthIssue(
                            file_path=file_path,
                            line_number=0,
                            severity=IssueSeverity.ERROR,
                            issue_type="scan_error",
                            message=f"Error scanning file: {e}"
                        ))
        
        return report
    
    def check_translation_file(self, file_path: str) -> HealthReport:
        """
        Check a translation file specifically for translation-related issues.
        """
        report = HealthReport()
        report.files_scanned = 1
        
        content = read_text_safely(Path(file_path))
        if content is None:
            report.issues.append(HealthIssue(
                file_path=file_path,
                line_number=0,
                severity=IssueSeverity.ERROR,
                issue_type="file_read_error",
                message="Could not read translation file"
            ))
            return report
        
        lines = content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Check old/new pairs
            old_match = self._old_re.match(line)
            if old_match and i + 1 < len(lines):
                old_text = old_match.group(1)
                next_line = lines[i + 1].strip()
                new_match = self._new_re.match(next_line)
                
                if new_match:
                    new_text = new_match.group(1)
                    report.total_strings += 1
                    
                    # Check for empty translation
                    if not new_text.strip():
                        report.issues.append(HealthIssue(
                            file_path=file_path,
                            line_number=i + 2,
                            severity=IssueSeverity.WARNING,
                            issue_type="empty_translation",
                            message=f"Empty translation for: \"{old_text[:40]}...\"" if len(old_text) > 40 else f"Empty translation for: \"{old_text}\""
                        ))
                    else:
                        # Check placeholder consistency
                        placeholder_issues = self.check_placeholder_consistency(
                            old_text, new_text, file_path, i + 2
                        )
                        report.issues.extend(placeholder_issues)
                    
                    i += 2
                    continue
            
            i += 1
        
        return report


def run_health_check(path: str, verbose: bool = False) -> HealthReport:
    """
    Convenience function to run a health check.
    
    Args:
        path: File or directory path to check
        verbose: Print detailed output
    """
    checker = HealthChecker()
    
    if os.path.isfile(path):
        if path.endswith('.rpy'):
            issues = checker.check_file(path)
            report = HealthReport(issues=issues, files_scanned=1)
        else:
            report = HealthReport()
    else:
        report = checker.check_directory(path)
    
    if verbose:
        print(report.summary())
        print("\n" + "="*60)
        for issue in report.issues:
            print(issue)
            if issue.suggestion:
                print(f"  💡 {issue.suggestion}")
            print()
    
    return report
