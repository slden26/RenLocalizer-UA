#!/usr/bin/env python3
"""Tests for ASTTextExtractor in rpyc_reader.py"""

import sys
from pathlib import Path
import tempfile

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.rpyc_reader import ASTTextExtractor


def run_code_test(code_str, expected_texts):
    extr = ASTTextExtractor()
    extr.current_file = str(Path('tmp.rpyc'))
    extr.extracted = []
    extr._extract_strings_from_code(code_str, 1)
    found = {t.text for t in extr.extracted}
    print(f"--- Found {len(found)} strings: {found}")
    missing = [t for t in expected_texts if t not in found]
    if missing:
        print(f"MISSING: {missing}")
        return False
    print("✅ PASS")
    return True


def run_line_test(line, expected_texts):
    extr = ASTTextExtractor()
    extr.current_file = str(Path('tmp.rpyc'))
    extr.extracted = []
    extr._extract_strings_from_line(line, 1)
    found = {t.text for t in extr.extracted}
    print(f"--- Found {len(found)} strings: {found}")
    missing = [t for t in expected_texts if t not in found]
    if missing:
        print(f"MISSING: {missing}")
        return False
    print("✅ PASS")
    return True


def main():
    print("RPYC code extract tests")
    all_passed = True

    # Code tests: lists and dicts
    ok = run_code_test('items = ["Sword", "Shield"]', ['Sword', 'Shield'])
    all_passed = all_passed and ok

    ok = run_code_test('quest = {"desc": "Go east"}', ['Go east'])
    all_passed = all_passed and ok

    # Line tests: simple list on one line
    ok = run_line_test('tips = ["Run fast", "Eat food"]', ['Run fast', 'Eat food'])
    all_passed = all_passed and ok

    # f-string test in code
    ok = run_code_test('greeting = f"Hello {player_name}"', ['Hello {player_name}'])
    all_passed = all_passed and ok

    print('\nAll RPYC tests passed: ', all_passed)
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
