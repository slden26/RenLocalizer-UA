#!/usr/bin/env python3
"""Tests for deep_scan_strings in parser.py"""

import tempfile
import os
import sys
from pathlib import Path
import json

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.parser import RenPyParser


def make_rpy(content: str, path: Path):
    path.write_text(content, encoding="utf-8")


def run_test_case(content: str, expected_texts):
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        f = tmp_dir / "test_file.rpy"
        make_rpy(content, f)
        parser = RenPyParser()
        results = parser.extract_with_deep_scan(f, include_deep_scan=True)
        texts = {e['text'] for e in results}
        missing = [t for t in expected_texts if t not in texts]
        print(f"Input file: {f}")
        print(f"Found texts: {texts}")
        if missing:
            print(f"MISSING: {missing}")
            return False
        print("✅ PASS")
        return True


def main():
    cases = []

    # 1. Multi-line list
    cases.append((
        '''init python:
    tips = [
        "Run fast",
        "Eat food",
        "Sleep"
    ]
''', ['Run fast', 'Eat food', 'Sleep']))

    # 2. Function arg string
    cases.append((
        '''init python:
    renpy.notify("Item purchased!")
''', ['Item purchased!']))

    # 3. f-string (should preserve placeholder)
    cases.append((
        '''init python:
    player_name = "Player"
    greeting = f"Hello {player_name}"
''', ['Hello {player_name}']))

    # 4. dict value
    cases.append((
        '''init python:
    quest = {"desc": "Go east"}
''', ['Go east']))

    all_passed = True
    for idx, (content, expected) in enumerate(cases, 1):
        print(f"\nTest case {idx}")
        ok = run_test_case(content, expected)
        all_passed = all_passed and ok

    print('\nAll tests passed: ', all_passed)
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
