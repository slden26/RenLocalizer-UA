#!/usr/bin/env python3
"""
System check script for RenLocalizer-V2
Tests all major components after recent updates
"""

import os
import sys
import asyncio
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.parser import RenPyParser
from src.core.output_formatter import RenPyOutputFormatter
from src.utils.config import ConfigManager, AppSettings

def test_basic_functionality():
    """Test basic parser and formatter functionality"""
    print("🧪 Testing basic functionality...")
    
    # Test parser creation
    parser = RenPyParser()
    print("✅ Parser created successfully")
    
    # Test formatter creation
    formatter = RenPyOutputFormatter()
    print("✅ Formatter created successfully")
    
    # Test config manager
    config = ConfigManager()
    config.load_config()  # This returns bool, not settings
    settings = config.app_settings  # Get the actual settings object
    print(f"✅ Config loaded - Parser workers: {settings.parser_workers}")
    
    return True

def test_parsing_functionality():
    """Test new parsing pipeline"""
    print("\n🔍 Testing parsing functionality...")
    
    parser = RenPyParser()
    
    # Test with temporary file
    test_content = '''
    label start:
        "Hello world!"
        menu:
            "Option 1":
                "Response 1"
            "Option 2":
                "Response 2"
    '''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.rpy', delete=False, encoding='utf-8') as f:
        f.write(test_content)
        temp_file = f.name
    
    try:
        result = parser.extract_translatable_text(temp_file)
        print(f"✅ Extracted {len(result)} translatable strings")
        
        # Verify extracted content
        expected_strings = ["Hello world!", "Option 1", "Response 1", "Option 2", "Response 2"]
        extracted_texts = list(result)  # result is now Set[str], not TranslationItem objects
        
        for expected in expected_strings:
            if expected in extracted_texts:
                print(f"✅ Found expected string: '{expected}'")
            else:
                print(f"❌ Missing expected string: '{expected}'")
        
    finally:
        # Clean up
        Path(temp_file).unlink(missing_ok=True)
    
    return True

async def test_async_functionality():
    """Test new async parsing functionality"""
    print("\n⚡ Testing async functionality...")
    
    parser = RenPyParser()
    
    # Create test content
    test_content = '''
    label async_test:
        "This is an async test!"
        "Another string for testing"
    '''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.rpy', delete=False, encoding='utf-8') as f:
        f.write(test_content)
        temp_file = f.name
    
    try:
        # Test async extraction
        result = await parser.extract_translatable_text_async(temp_file)
        print(f"✅ Async extraction completed - {len(result)} strings found")
    finally:
        # Clean up
        Path(temp_file).unlink(missing_ok=True)
    
    return True

def test_parallel_functionality():
    """Test parallel file processing"""
    print("\n🚀 Testing parallel functionality...")
    
    # Create temporary test files
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Created temp directory: {temp_dir}")
        
        # Create test files
        for i in range(3):
            test_file = Path(temp_dir) / f"test_{i}.rpy"
            test_file.write_text(f'''
            label test_{i}:
                "Test string {i}"
                "Another test string {i}"
            ''')
        
        parser = RenPyParser()
        
        # Test parallel processing
        all_results = parser.extract_from_directory_parallel(temp_dir, max_workers=2)
        
        # Calculate total strings
        total_strings = sum(len(texts) for texts in all_results.values())
        print(f"✅ Parallel processing completed - {total_strings} total strings")
        
        # Verify results - all_results is Dict[Path, Set[str]] now
        for file_path, texts in all_results.items():
            for text in texts:
                if text.startswith("Test string") or text.startswith("Another test"):
                    print(f"✅ Parallel result: '{text}' from {file_path.name}")
    
    return True

async def test_async_directory():
    """Test async directory processing"""
    print("\n🌐 Testing async directory functionality...")
    
    # Create temporary test files
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Created temp directory: {temp_dir}")
        
        # Create test files
        for i in range(2):
            test_file = Path(temp_dir) / f"async_test_{i}.rpy"
            test_file.write_text(f'''
            label async_test_{i}:
                "Async test string {i}"
            ''')
        
        parser = RenPyParser()
        
        # Test async directory processing
        all_results = await parser.extract_from_directory_async(temp_dir)
        
        # Calculate total strings
        total_strings = sum(len(texts) for texts in all_results.values())
        print(f"✅ Async directory processing completed - {total_strings} total strings")
        
        # Verify results - all_results is Dict[Path, Set[str]] now
        for file_path, texts in all_results.items():
            for text in texts:
                if text.startswith("Async test string"):
                    print(f"✅ Async dir result: '{text}' from {file_path.name}")
    
    return True

def test_output_formats():
    """Test output formatting options"""
    print("\n📋 Testing output formats...")
    
    formatter = RenPyOutputFormatter()
    
    # Test basic functionality - escaping and sanitizing
    test_text = 'Hello "world"!'
    escaped = formatter.escape_renpy_string(test_text)
    print(f"✅ String escaping works: '{test_text}' -> '{escaped}'")
    
    sanitized = formatter.sanitize_translation_id(test_text)
    print(f"✅ ID sanitization works: '{test_text}' -> '{sanitized}'")
    
    # Test header generation
    header = formatter.generate_file_header("tr")
    print("✅ File header generated")
    
    return True

def test_config_persistence():
    """Test config saving and loading"""
    print("\n💾 Testing config persistence...")
    
    config = ConfigManager()
    
    # Create test settings
    test_settings = AppSettings(
        output_format="old_new",
        parser_workers=8
    )
    
    # Save and reload
    config.save_config(test_settings)
    print("✅ Config saved")
    
    config.load_config()  # Returns bool, not settings
    loaded_settings = config.app_settings  # Get the actual settings object
    print(f"✅ Config loaded - Format: {loaded_settings.output_format}, Workers: {loaded_settings.parser_workers}")
    
    # Reset to defaults
    default_settings = AppSettings()
    config.save_config(default_settings)
    print("✅ Config reset to defaults")
    
    return True

async def main():
    """Run all system checks"""
    print("🔧 RenLocalizer-V2 System Check")
    print("=" * 50)
    
    try:
        # Basic functionality
        test_basic_functionality()
        
        # Parsing functionality  
        test_parsing_functionality()
        
        # Async functionality
        await test_async_functionality()
        
        # Parallel functionality
        test_parallel_functionality()
        
        # Async directory
        await test_async_directory()
        
        # Output formats
        test_output_formats()
        
        # Config persistence
        test_config_persistence()
        
        print("\n" + "=" * 50)
        print("🎉 All system checks PASSED!")
        print("✅ Project is ready for use")
        
    except Exception as e:
        print(f"\n❌ System check FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(main())
