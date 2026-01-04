# -*- coding: utf-8 -*-
"""
RenLocalizer CLI Main Module
"""

import sys
import os
import argparse
import signal
import json
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QCoreApplication, QTimer, QObject, pyqtSlot

# Import core modules
from src.utils.config import ConfigManager
from src.core.translation_pipeline import TranslationPipeline, PipelineResult, PipelineStage
from src.core.translator import TranslationManager, TranslationEngine, PseudoTranslator
from src.core.proxy_manager import ProxyManager
from src.version import VERSION

# Import new tool modules
try:
    from src.tools.health_check import HealthChecker, run_health_check
    from src.tools.fuzzy_matcher import FuzzyMatcher, TranslationMemory, create_common_memory
    from src.tools.font_helper import FontHelper, check_font_for_project
    from src.tools.context_viewer import ContextAnalyzer
    from src.tools.deferred_loading import DeferredLoadingGenerator
    TOOLS_AVAILABLE = True
except ImportError as e:
    TOOLS_AVAILABLE = False
    print(f"Warning: Some tools not available: {e}")

class CliHandler(QObject):
    """Handles CLI events and pipeline signals."""
    
    def __init__(self, pipeline: TranslationPipeline, verbose: bool = False):
        super().__init__()
        self.pipeline = pipeline
        self.verbose = verbose
        
        # Connect signals
        self.pipeline.stage_changed.connect(self.on_stage_changed)
        self.pipeline.progress_updated.connect(self.on_progress_updated)
        self.pipeline.log_message.connect(self.on_log_message)
        self.pipeline.finished.connect(self.on_finished)
        self.pipeline.show_warning.connect(self.on_warning)
        
    @pyqtSlot(str, str)
    def on_stage_changed(self, stage: str, message: str):
        print(f"\n>> STAGE: {message} ({stage})")

    @pyqtSlot(int, int, str)
    def on_progress_updated(self, current: int, total: int, text: str):
        # Print a progress bar or status line
        percent = 0
        if total > 0:
            percent = int((current / total) * 100)
        
        # Clear line and print progress
        sys.stdout.write(f"\rProgress: [{current}/{total}] {percent}% - {text[:50].ljust(50)}")
        sys.stdout.flush()

    @pyqtSlot(str, str)
    def on_log_message(self, level: str, message: str):
        if self.verbose or level in ["warning", "error", "critical"]:
            print(f"\n[{level.upper()}] {message}")

    @pyqtSlot(str, str)
    def on_warning(self, title: str, message: str):
        print(f"\n[WARNING] {title}: {message}")

    @pyqtSlot(object)
    def on_finished(self, result: PipelineResult):
        print("\n" + "="*60)
        if result.success:
            print("SUCCESS")
            print(result.message)
            if result.stats:
                print("\nStatistics:")
                print(f"  Total items: {result.stats.get('total', 0)}")
                print(f"  Translated:  {result.stats.get('translated', 0)}")
                print(f"  Untranslated:{result.stats.get('untranslated', 0)}")
        else:
            print("FAILED")
            print(result.message)
            if result.error:
                print(f"Details: {result.error}")
        print("="*60)
        
        # Quit application
        QCoreApplication.quit()

def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

def load_config_override(config_path: str) -> dict:
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config file {config_path}: {e}")
        return {}


# ============================================================================
# NEW COMMAND HANDLERS
# ============================================================================

def run_health_check_command(args) -> int:
    """Run health check (static analysis) on a project."""
    if not TOOLS_AVAILABLE:
        print("Error: Health check tools not available")
        return 1
    
    print_header()
    print("\n  HEALTH CHECK")
    print("  " + "-"*40)
    
    input_path = os.path.abspath(args.input_path)
    if not os.path.exists(input_path):
        print(f"  Error: Path not found: {input_path}")
        return 1
    
    print(f"  Scanning: {input_path}")
    print()
    
    report = run_health_check(input_path, verbose=args.verbose)
    
    print("\n" + "="*60)
    print(report.summary())
    print("="*60)
    
    # Return non-zero if errors found
    return 0 if report.is_healthy else 1


def run_font_check_command(args) -> int:
    """Check font compatibility for a target language."""
    if not TOOLS_AVAILABLE:
        print("Error: Font check tools not available")
        return 1
    
    print_header()
    print("\n  FONT COMPATIBILITY CHECK")
    print("  " + "-"*40)
    
    input_path = os.path.abspath(args.input_path)
    if not os.path.exists(input_path):
        print(f"  Error: Path not found: {input_path}")
        return 1
    
    language = args.lang
    print(f"  Directory: {input_path}")
    print(f"  Language: {language}")
    print()
    
    summary = check_font_for_project(input_path, language, verbose=args.verbose)
    
    print("\n" + "="*60)
    print(f"Fonts checked: {summary['fonts_checked']}")
    print(f"Compatible: {summary['compatible_fonts']}")
    print(f"Incompatible: {summary['incompatible_fonts']}")
    print("="*60)
    
    return 0 if summary['incompatible_fonts'] == 0 else 1


def run_pseudo_command(args) -> int:
    """Generate pseudo-localized translations for UI testing."""
    print_header()
    print("\n  PSEUDO-LOCALIZATION")
    print("  " + "-"*40)
    
    input_path = os.path.abspath(args.input_path)
    if not os.path.exists(input_path):
        print(f"  Error: Path not found: {input_path}")
        return 1
    
    mode = args.mode
    print(f"  Input: {input_path}")
    print(f"  Mode: {mode}")
    
    # Determine output directory
    if args.output:
        output_dir = os.path.abspath(args.output)
    else:
        # Default to tl/pseudo
        if os.path.isfile(input_path):
            base = os.path.dirname(input_path)
        else:
            base = input_path
        output_dir = os.path.join(base, "game", "tl", "pseudo")
    
    print(f"  Output: {output_dir}")
    print()
    
    # Create PseudoTranslator
    translator = PseudoTranslator(mode=mode)
    
    # Find .rpy files to process
    rpy_files = []
    if os.path.isfile(input_path) and input_path.endswith('.rpy'):
        rpy_files = [input_path]
    else:
        game_dir = os.path.join(input_path, 'game')
        if os.path.isdir(game_dir):
            for root, dirs, files in os.walk(game_dir):
                # Skip tl folders
                if '/tl/' in root.replace('\\', '/') or '\\tl\\' in root:
                    continue
                for f in files:
                    if f.endswith('.rpy'):
                        rpy_files.append(os.path.join(root, f))
    
    if not rpy_files:
        print("  No .rpy files found to process.")
        print("  Hint: Run UnRen first if the game is still compiled.")
        return 1
    
    print(f"  Found {len(rpy_files)} .rpy files")
    print()
    
    # Process each file
    import re
    dialogue_pattern = re.compile(r'^(\s*)(\w+)?\s*"([^"]+)"', re.MULTILINE)
    translated_count = 0
    
    os.makedirs(output_dir, exist_ok=True)
    
    for rpy_file in rpy_files:
        rel_path = os.path.relpath(rpy_file, input_path)
        output_file = os.path.join(output_dir, rel_path)
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        try:
            with open(rpy_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract and pseudo-translate dialogues
            translations = []
            
            def pseudo_replace(match):
                nonlocal translated_count
                indent = match.group(1) or ""
                speaker = match.group(2) or ""
                text = match.group(3)
                
                # Apply pseudo-localization
                pseudo_text = translator._apply_pseudo(text)
                translated_count += 1
                
                if speaker:
                    return f'{indent}{speaker} "{pseudo_text}"'
                else:
                    return f'{indent}"{pseudo_text}"'
            
            # Transform content
            pseudo_content = dialogue_pattern.sub(pseudo_replace, content)
            
            # Write output
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(pseudo_content)
            
            if args.verbose:
                print(f"  ✓ {rel_path}")
        
        except Exception as e:
            print(f"  ✗ Error processing {rel_path}: {e}")
    
    print()
    print(f"  ✅ Pseudo-localized {translated_count} strings")
    print(f"  📁 Output: {output_dir}")
    print()
    print("  To test in game:")
    print("  1. Copy the 'pseudo' folder to your game's tl/ directory")
    print("  2. In game preferences, select 'pseudo' as language")
    print("  3. Look for [!!! markers !!!] and àccéntéd characters")
    
    return 0


def run_fuzzy_command(args) -> int:
    """Run fuzzy matching to recover translations."""
    if not TOOLS_AVAILABLE:
        print("Error: Fuzzy matching tools not available")
        return 1
    
    print_header()
    print("\n  FUZZY MATCHING (Smart Update)")
    print("  " + "-"*40)
    
    old_tl = os.path.abspath(args.old_tl)
    new_tl = os.path.abspath(args.new_tl)
    
    if not os.path.exists(old_tl):
        print(f"  Error: Old TL path not found: {old_tl}")
        return 1
    if not os.path.exists(new_tl):
        print(f"  Error: New TL path not found: {new_tl}")
        return 1
    
    threshold = args.threshold
    print(f"  Old translations: {old_tl}")
    print(f"  New translations: {new_tl}")
    print(f"  Auto-apply threshold: {threshold * 100:.0f}%")
    print()
    
    # Parse old translations
    from src.core.tl_parser import TLParser
    parser = TLParser()
    
    print("  Parsing old translations...")
    old_files = parser.parse_directory(os.path.dirname(old_tl), os.path.basename(old_tl))
    
    print("  Parsing new translations...")
    new_files = parser.parse_directory(os.path.dirname(new_tl), os.path.basename(new_tl))
    
    # Build entry dicts
    old_entries = {}
    for tl_file in old_files:
        for entry in tl_file.entries:
            if entry.translated_text:
                old_entries[entry.translation_id] = (entry.original_text, entry.translated_text)
    
    new_entries = {}
    new_entries_by_file = {}  # file_path -> {translation_id: entry}
    for tl_file in new_files:
        new_entries_by_file[tl_file.file_path] = {}
        for entry in tl_file.entries:
            new_entries[entry.translation_id] = entry.original_text
            new_entries_by_file[tl_file.file_path][entry.translation_id] = entry
    
    print(f"  Old entries: {len(old_entries)}")
    print(f"  New entries: {len(new_entries)}")
    print()
    
    # Run fuzzy matching
    matcher = FuzzyMatcher(auto_threshold=threshold)
    report = matcher.match_translations(new_entries, old_entries)
    
    print(report.summary())
    
    if args.verbose:
        print("\n  Matches found:")
        for match in report.matches[:20]:  # Show first 20
            status = "✓" if match.is_confident() else "?"
            print(f"    [{status}] {match.similarity_percent}%: \"{match.new_original[:40]}...\"")
    
    if args.apply and report.auto_apply_count > 0:
        print(f"\n  Applying {report.auto_apply_count} confident matches...")
        
        # Build a map of new_id -> suggested translation (only confident matches)
        suggestions = {}
        for match in report.matches:
            if match.is_confident(threshold):
                suggestions[match.new_id] = match.old_translation
        
        # Apply to files
        applied_count = 0
        for file_path, entries in new_entries_by_file.items():
            file_modified = False
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                for trans_id, entry in entries.items():
                    if trans_id in suggestions:
                        new_translation = suggestions[trans_id]
                        
                        # Find and replace in content
                        # Pattern: look for the translation block and replace the translated text
                        import re
                        
                        # Try to find the entry and update it
                        # Look for: "original_text" and replace the next quoted line
                        old_pattern = re.escape(entry.original_text)
                        
                        # If the file contains this original text followed by untranslated version
                        if entry.original_text in content:
                            # Simple replacement: find empty translation and fill it
                            # Look for patterns like:    old "text"\n    new "text"  -> new "translation"
                            pattern = rf'(old\s+"[^"]*"\s*\n\s*new\s+")({re.escape(entry.original_text)})(")'
                            replacement = rf'\g<1>{new_translation}\g<3>'
                            new_content, count = re.subn(pattern, replacement, content)
                            
                            if count > 0:
                                content = new_content
                                file_modified = True
                                applied_count += 1
                            else:
                                # Try simple format: # "original"\n    "original" -> "translation"
                                pattern2 = rf'(#\s*"{re.escape(entry.original_text)}"\s*\n\s*")({re.escape(entry.original_text)})(")'
                                replacement2 = rf'\g<1>{new_translation}\g<3>'
                                new_content, count = re.subn(pattern2, replacement2, content)
                                if count > 0:
                                    content = new_content
                                    file_modified = True
                                    applied_count += 1
                
                if file_modified:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    if args.verbose:
                        print(f"    ✓ Updated: {os.path.basename(file_path)}")
            
            except Exception as e:
                print(f"    ✗ Error updating {file_path}: {e}")
        
        print(f"\n  ✅ Applied {applied_count} translations")
        
        # Also export suggestions to JSON
        suggestions_file = os.path.join(new_tl, "fuzzy_suggestions.json")
        try:
            import json
            with open(suggestions_file, 'w', encoding='utf-8') as f:
                export_data = [
                    {
                        "new_id": m.new_id,
                        "new_original": m.new_original,
                        "suggested": m.old_translation,
                        "similarity": m.similarity_percent,
                        "auto_applied": m.is_confident(threshold)
                    }
                    for m in report.matches
                ]
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            print(f"  📁 Suggestions exported to: {suggestions_file}")
        except Exception as e:
            print(f"  ⚠ Could not export suggestions: {e}")
    
    elif report.auto_apply_count > 0:
        print(f"\n  💡 {report.auto_apply_count} translations can be auto-applied.")
        print("  Use --apply flag to apply them:")
        print(f"    python run_cli.py fuzzy {args.old_tl} {args.new_tl} --apply")
    
    return 0

def run_extract_glossary_command(args) -> int:
    """Run glossary extraction."""
    try:
        from src.tools.glossary_extractor import GlossaryExtractor
    except ImportError:
        print("Error: Glossary extractor tool not found.")
        return 1
        
    print_header()
    print("\n  GLOSSARY EXTRACTOR")
    print("  " + "-"*40)
    
    input_path = os.path.abspath(args.input_path)
    if not os.path.exists(input_path):
        print(f"  Error: Path not found: {input_path}")
        return 1
        
    print(f"  Scanning: {input_path}")
    
    extractor = GlossaryExtractor()
    terms = extractor.extract_from_directory(input_path, min_occurrence=args.min_count)
    
    if not terms:
        print("\n  No terms found.")
        return 0
        
    print(f"\n  Found {len(terms)} potential terms.")
    
    # Save output
    output_file = args.output
    if not output_file:
        output_file = os.path.join(os.getcwd(), "glossary_extracted.json")
        
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(terms, f, ensure_ascii=False, indent=2)
        print(f"  ✅ Saved to: {output_file}")
    except Exception as e:
        print(f"  ✗ Error saving file: {e}")
        return 1
        
    return 0

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    """Print the CLI header."""
    print("\n" + "="*60)
    print(f"       RenLocalizer CLI v{VERSION}")
    print("       Ren'Py Game Translation Tool")
    print("="*60)

def print_menu(title: str, options: list, show_back: bool = True) -> int:
    """Display a menu and get user selection."""
    print(f"\n  {title}")
    print("  " + "-"*40)
    for i, option in enumerate(options, 1):
        print(f"    [{i}] {option}")
    if show_back:
        print(f"    [0] Back")
    print()
    
    while True:
        try:
            choice = input("  Your choice: ").strip()
            if choice == '0' and show_back:
                return 0
            num = int(choice)
            if 1 <= num <= len(options):
                return num
            print("  Invalid choice")
        except ValueError:
            print("  Please enter a number")

def get_input(prompt: str, default: str = "") -> str:
    """Get text input from user with optional default."""
    if default:
        result = input(f"  {prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"  {prompt}: ").strip()

def interactive_mode() -> dict:
    """Run interactive setup wizard."""
    config = {
        'input_path': '',
        'target_lang': 'tr',
        'source_lang': 'auto',
        'engine': 'google',
        'mode': 'auto',
        'proxy': False,
        'verbose': False
    }
    
    clear_screen()
    print_header()
    
    # Main Menu
    while True:
        choice = print_menu("MAIN MENU", [
            "Full Translation (Game EXE/Project)",
            "Translate Existing TL Folder",
            "Settings",
            "Help",
            "Exit"
        ], show_back=False)
        
        if choice == 1:  # Full Translation
            # Get input path
            print("\n  STEP 1: File/Folder Selection")
            print("  " + "-"*40)
            print("  Enter the game EXE or project folder path.")
            print()
            
            path = get_input("Path")
            if not path:
                print("\n  [!] Path cannot be empty")
                continue
                
            if not os.path.exists(path):
                print(f"\n  [!] File/folder not found: {path}")
                continue
            
            config['input_path'] = os.path.abspath(path)
            
            # Get target language
            print("\n  STEP 2: Target Language")
            print("  " + "-"*40)
            lang_choice = print_menu("Select target language", [
                "Turkish (tr)",
                "English (en)",
                "French (fr)",
                "German (de)",
                "Spanish (es)",
                "Russian (ru)",
                "Japanese (ja)",
                "Korean (ko)",
                "Chinese (zh)",
                "Other (enter manually)"
            ], show_back=True)
            
            if lang_choice == 0:
                continue
            
            lang_codes = ['tr', 'en', 'fr', 'de', 'es', 'ru', 'ja', 'ko', 'zh']
            if lang_choice <= 9:
                config['target_lang'] = lang_codes[lang_choice - 1]
            else:
                config['target_lang'] = get_input("Language code", "tr")
            
            # Get mode
            print("\n  STEP 3: Operation Mode")
            print("  " + "-"*40)
            mode_choice = print_menu("Select mode", [
                "Auto (Recommended)",
                "Full (UnRen + Translation - Windows Only)",
                "Translate Only"
            ], show_back=True)
            
            if mode_choice == 0:
                continue
            
            modes = ['auto', 'full', 'translate']
            config['mode'] = modes[mode_choice - 1]
            
            # Confirm and start
            clear_screen()
            print_header()
            print("\n  SUMMARY")
            print("  " + "-"*40)
            print(f"    Path:            {config['input_path']}")
            print(f"    Target Language: {config['target_lang']}")
            print(f"    Source Language: {config['source_lang']}")
            print(f"    Engine:          {config['engine']}")
            print(f"    Mode:            {config['mode']}")
            print()
            
            confirm = get_input("Start translation? (y/n)", "y")
            if confirm.lower() in ['y', 'yes']:
                return config
        
        elif choice == 2:  # Translate TL Folder
            print("\n  TRANSLATE EXISTING TL FOLDER")
            print("  " + "-"*40)
            print("  Enter the path to your game's tl folder")
            print("  Example: C:\\Games\\MyGame\\game\\tl\\turkish")
            print()
            
            path = get_input("TL Folder Path")
            if not path:
                print("\n  [!] Path cannot be empty")
                continue
                
            if not os.path.exists(path):
                print(f"\n  [!] Folder not found: {path}")
                continue
            
            config['input_path'] = os.path.abspath(path)
            config['mode'] = 'translate'  # Force translate mode for TL folders
            
            # Get target language
            print("\n  Target Language")
            print("  " + "-"*40)
            lang_choice = print_menu("Select target language", [
                "Turkish (tr)",
                "English (en)",
                "French (fr)",
                "German (de)",
                "Spanish (es)",
                "Russian (ru)",
                "Japanese (ja)",
                "Korean (ko)",
                "Chinese (zh)",
                "Other (enter manually)"
            ], show_back=True)
            
            if lang_choice == 0:
                continue
            
            lang_codes = ['tr', 'en', 'fr', 'de', 'es', 'ru', 'ja', 'ko', 'zh']
            if lang_choice <= 9:
                config['target_lang'] = lang_codes[lang_choice - 1]
            else:
                config['target_lang'] = get_input("Language code", "tr")
            
            # Confirm and start
            clear_screen()
            print_header()
            print("\n  SUMMARY")
            print("  " + "-"*40)
            print(f"    TL Folder:       {config['input_path']}")
            print(f"    Target Language: {config['target_lang']}")
            print(f"    Source Language: {config['source_lang']}")
            print(f"    Engine:          {config['engine']}")
            print(f"    Mode:            translate (TL folder)")
            print()
            
            confirm = get_input("Start translation? (y/n)", "y")
            if confirm.lower() in ['y', 'yes']:
                return config
            
        elif choice == 3:  # Settings
            while True:
                settings_choice = print_menu("SETTINGS", [
                    f"Source Language: {config['source_lang']}",
                    f"Translation Engine: {config['engine']}",
                    f"Proxy: {'On' if config['proxy'] else 'Off'}",
                    f"Verbose Logging: {'On' if config['verbose'] else 'Off'}"
                ])
                
                if settings_choice == 0:
                    break
                elif settings_choice == 1:
                    config['source_lang'] = get_input("Source language code", config['source_lang'])
                elif settings_choice == 2:
                    eng_choice = print_menu("Select engine", ["Google Translate", "DeepL"])
                    if eng_choice == 1:
                        config['engine'] = 'google'
                    elif eng_choice == 2:
                        config['engine'] = 'deepl'
                elif settings_choice == 3:
                    config['proxy'] = not config['proxy']
                elif settings_choice == 4:
                    config['verbose'] = not config['verbose']
                    
        elif choice == 4:  # Help
            clear_screen()
            print_header()
            print("""
  HELP
  ─────────────────────────────────────────
  
  RenLocalizer CLI automatically translates
  Ren'Py visual novel games.
  
  TRANSLATION MODES:
  
  1. Full Translation (Game EXE/Project)
     - For games with .exe or project folders
     - On Windows: Can run UnRen automatically
     - On Mac/Linux: Use with pre-extracted files
  
  2. Translate Existing TL Folder
     - For already generated tl/<lang> folders
     - Useful when you have .rpy translation files
     - Works on all platforms
  
  COMMAND LINE USAGE:
  python run_cli.py <path> --target-lang tr --mode auto
  
  For more info: docs/CLI_USAGE.md
  ─────────────────────────────────────────
            """)
            input("\n  Press Enter to continue...")
            
        elif choice == 5:  # Exit
            print("\n  Goodbye!\n")
            sys.exit(0)
    
    return config

def main() -> int:
    parser = argparse.ArgumentParser(description=f"RenLocalizer V{VERSION} CLI")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # TRANSLATE command (default)
    translate_parser = subparsers.add_parser('translate', help='Translate a game or project')
    translate_parser.add_argument("input_path", nargs='?', default=None, 
                        help="Path to game executable, project directory, or translation file")
    translate_parser.add_argument("--config", help="Path to JSON configuration file")
    translate_parser.add_argument("--target-lang", "-t", default="tr", help="Target language code (default: tr)")
    translate_parser.add_argument("--source-lang", "-s", default="auto", help="Source language code (default: auto)")
    translate_parser.add_argument("--engine", "-e", default="google", choices=["google", "deepl", "pseudo"], help="Translation engine (pseudo for UI testing)")
    translate_parser.add_argument("--mode", choices=["auto", "full", "translate"], default="auto", 
                        help="Operation mode: 'auto' (detect), 'full' (UnRen+Trans), 'translate' (Trans only)")
    translate_parser.add_argument("--proxy", action="store_true", help="Enable proxy")
    translate_parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    translate_parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive menu mode")
    translate_parser.add_argument("--deep-scan", "-d", action="store_true", help="Enable deep scanning (AST/RPYC analysis)")
    
    # HEALTH-CHECK command
    health_parser = subparsers.add_parser('health-check', help='Run static analysis on project')
    health_parser.add_argument("input_path", help="Path to game directory or .rpy file")
    health_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    health_parser.add_argument("--include-tl", action="store_true", help="Also check tl/ folder")
    
    # FONT-CHECK command
    font_parser = subparsers.add_parser('font-check', help='Check font compatibility for a language')
    font_parser.add_argument("input_path", help="Path to game directory")
    font_parser.add_argument("--lang", "-l", default="tr", help="Target language code (default: tr)")
    font_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    
    # PSEUDO command (quick pseudo-localization)
    pseudo_parser = subparsers.add_parser('pseudo', help='Generate pseudo-localized text for UI testing')
    pseudo_parser.add_argument("input_path", help="Path to game directory or tl folder")
    pseudo_parser.add_argument("--mode", choices=["expand", "accent", "both"], default="both",
                               help="Pseudo mode: expand ([!!! !!!]), accent (àccénts), or both")
    pseudo_parser.add_argument("--output", "-o", help="Output directory (default: tl/pseudo)")
    
    # FUZZY command (smart update)
    fuzzy_parser = subparsers.add_parser('fuzzy', help='Recover translations using fuzzy matching')
    fuzzy_parser.add_argument("old_tl", help="Path to old translation files")
    fuzzy_parser.add_argument("new_tl", help="Path to new translation files")
    fuzzy_parser.add_argument("--threshold", type=float, default=0.9, help="Auto-apply threshold (default: 0.9)")
    fuzzy_parser.add_argument("--apply", action="store_true", help="Apply suggestions automatically")
    fuzzy_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    
    # EXTRACT-GLOSSARY command
    glossary_parser = subparsers.add_parser('extract-glossary', help='Extract potential glossary terms from project')
    glossary_parser.add_argument("input_path", help="Path to game directory")
    glossary_parser.add_argument("--min-count", type=int, default=3, help="Minimum occurrence for common terms")
    glossary_parser.add_argument("--output", "-o", help="Output JSON file (default: glossary_extracted.json)")
    
    # Legacy support: Add arguments directly to main parser for backwards compatibility
    # These are used when no subcommand is specified
    parser.add_argument("input_path", nargs='?', default=None, 
                        help="Path to game executable, project directory, or translation file")
    parser.add_argument("--config", help="Path to JSON configuration file to override settings")
    parser.add_argument("--target-lang", "-t", default="tr", help="Target language code (default: tr)")
    parser.add_argument("--source-lang", "-s", default="auto", help="Source language code (default: auto)")
    parser.add_argument("--engine", "-e", default="google", choices=["google", "deepl", "pseudo"], help="Translation engine")
    parser.add_argument("--mode", choices=["auto", "full", "translate"], default="auto", 
                        help="Operation mode: 'auto' (detect), 'full' (UnRen+Trans), 'translate' (Trans only)")
    parser.add_argument("--proxy", action="store_true", help="Enable proxy")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive menu mode")
    parser.add_argument("--deep-scan", action="store_true", help="Enable deep scanning")
    parser.add_argument("--rpyc", action="store_true", help="Enable RPYC reader (experimental)")
    
    args = parser.parse_args()
    
    # Handle subcommands
    if args.command == 'translate':
        # Translate subcommand uses same logic as legacy mode
        pass  # Fall through to main translation logic
    elif args.command == 'health-check':
        return run_health_check_command(args)
    elif args.command == 'font-check':
        return run_font_check_command(args)
    elif args.command == 'pseudo':
        return run_pseudo_command(args)
    elif args.command == 'fuzzy':
        return run_fuzzy_command(args)
    elif args.command == 'extract-glossary':
        return run_extract_glossary_command(args)
    
    # If no input_path provided or --interactive flag, run interactive mode
    if args.input_path is None or args.interactive:
        interactive_config = interactive_mode()
        args.input_path = interactive_config['input_path']
        args.target_lang = interactive_config['target_lang']
        args.source_lang = interactive_config['source_lang']
        args.engine = interactive_config['engine']
        args.mode = interactive_config['mode']
        args.proxy = interactive_config['proxy']
        args.verbose = interactive_config['verbose']

    # Create config manager
    config_manager = ConfigManager()
    
    # Apply CLI args to config
    # 1. Load external config if provided
    if args.config:
        overrides = load_config_override(args.config)
        # Apply overrides to internal config structures
        # This is a basic implementation - for deeper nesting, might need recursion
        if 'translation_settings' in overrides:
            for k, v in overrides['translation_settings'].items():
                if hasattr(config_manager.translation_settings, k):
                    setattr(config_manager.translation_settings, k, v)
        if 'app_settings' in overrides:
            for k, v in overrides['app_settings'].items():
                if hasattr(config_manager.app_settings, k):
                    setattr(config_manager.app_settings, k, v)
    
    # 2. Apply explicit CLI args (priority over config file)
    config_manager.translation_settings.target_language = args.target_lang
    config_manager.translation_settings.source_language = args.source_lang
    
    # Update both translation settings and proxy settings
    config_manager.translation_settings.enable_proxy = args.proxy
    config_manager.proxy_settings.enabled = args.proxy
    
    # Setup Logging
    setup_logging(args.verbose)
    
    # Setup QCoreApplication
    app = QCoreApplication(sys.argv)
    app.setApplicationName("RenLocalizerCLI")
    app.setApplicationVersion(VERSION)

    # Initialize Managers
    # Entegrasyon: Proxy desteği eklendi
    proxy_manager = ProxyManager()
    # Configure proxy manager from loaded settings
    proxy_manager.configure_from_settings(config_manager.proxy_settings)
    
    # Pass proxy_manager to TranslationManager
    translation_manager = TranslationManager(proxy_manager=proxy_manager)
    pipeline = TranslationPipeline(config_manager, translation_manager)
    
    # Create CLI Handler
    handler = CliHandler(pipeline, verbose=args.verbose)
    
    # Determine Mode
    input_path = os.path.abspath(args.input_path)
    if not os.path.exists(input_path):
        print(f"Error: Input path does not exist: {input_path}")
        return 1
        
    # Validating Mode vs OS
    is_windows = sys.platform == "win32"
    mode = args.mode
    is_exe_file = os.path.isfile(input_path) and input_path.lower().endswith(".exe")
    
    if mode == "auto":
        # Heuristic detection
        if is_exe_file:
            mode = "full" if is_windows else "translate"
        else:
            mode = "translate"
    
    # If user provided EXE but selected translate mode, we need to handle this
    if is_exe_file and mode == "translate":
        if is_windows:
            print("Note: EXE file provided with 'translate' mode. Switching to 'full' mode.")
            mode = "full"
        else:
            print("Error: EXE files require 'full' mode which is only available on Windows.")
            print("Please extract the game files first and provide the game folder path.")
            return 1
            
    if mode == "full" and not is_windows:
        print("Warning: 'full' mode (UnRen) is only supported on Windows. Switching to 'translate' mode.")
        mode = "translate"
        
    print(f"RenLocalizer CLI v{VERSION}")
    print(f"Input: {input_path}")
    print(f"Mode: {mode}")
    print(f"Target: {args.target_lang}")
    print("-" * 40)
    
    # Configure Pipeline
    engine_enum = TranslationEngine.GOOGLE
    if args.engine.lower() == "deepl":
        engine_enum = TranslationEngine.DEEPL

    # Setup pipeline based on mode
    if mode == "full":
        # Full pipeline expects an EXE path usually
        pipeline.configure(
            game_exe_path=input_path,
            target_language=args.target_lang,
            source_language=args.source_lang,
            engine=engine_enum,
            auto_unren=True,
            use_proxy=args.proxy,
            include_deep_scan=getattr(args, 'deep_scan', False),
            include_rpyc=getattr(args, 'rpyc', False)
        )
        QTimer.singleShot(0, pipeline.run)
        
    elif mode == "translate":
        # Translate only mode - usage depends on what input_path is
        # If it's a directory, assume it's the game root or tl folder
        # pipeline has a method `translate_existing_tl` but it needs to be called carefully
        
        # We need to adapt the pipeline usage for pure translation without full UnRen flow
        # The pipeline class has `translate_existing_tl` method
        
        def run_translation_wrapper():
            # Apply feature flags manually since translate_existing_tl doesn't use configure()
            pipeline.include_deep_scan = getattr(args, 'deep_scan', False)
            pipeline.include_rpyc = getattr(args, 'rpyc', False)
            pipeline.use_proxy = args.proxy
            # translate_existing_tl returns a PipelineResult directly
            try:
                result = pipeline.translate_existing_tl(
                    tl_root_path=input_path,
                    target_language=args.target_lang,
                    source_language=args.source_lang,
                    engine=engine_enum,
                    use_proxy=args.proxy
                )
                handler.on_finished(result)
            except Exception as e:
                import traceback
                print(f"Error during translation: {e}")
                traceback.print_exc()
                QCoreApplication.quit()

        QTimer.singleShot(0, run_translation_wrapper)

    # Setup signal handling for graceful exit (Ctrl+C)
    signal.signal(signal.SIGINT, lambda *args: QCoreApplication.quit())
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
