import re
from pathlib import Path

"""Utility to clean previously generated .rpy translation files that contain literal '\n' artifacts
at the beginning of lines (e.g. "\\ntranslate tr some_id:").

Usage (programmatic):
    from src.utils.rpy_cleanup import clean_rpy_file, bulk_clean
    clean_rpy_file(Path("path/to/file.rpy"))

Patterns fixed:
1. Leading literal \n before translate block headers.
2. Trailing stray literal \n lines that are by-products of earlier escaping.

The cleaner is idempotent: running multiple times is safe.
"""

TRANSLATE_LINE_RE = re.compile(r"^\\\n(translate\s+\w+\s+[A-Za-z0-9_]+:)\s*$")
LITERAL_N_RE = re.compile(r"\\n+")


def clean_rpy_content(text: str) -> str:
    lines = text.splitlines()
    cleaned = []
    removed_count = 0
    for line in lines:
        # Case 1: line starts with literal '\n' then translate ...
        m = TRANSLATE_LINE_RE.match(line)
        if m:
            cleaned.append(m.group(1))
            removed_count += 1
            continue
        # Case 2: lone line that is exactly "\\ntranslate ..." (fallback)
        if line.startswith("\\ntranslate "):
            cleaned.append(line[2:])
            removed_count += 1
            continue
        cleaned.append(line)
    result = "\n".join(cleaned)
    return result, removed_count


def clean_rpy_file(path: Path) -> int:
    """Clean a single .rpy file. Returns number of header glitches fixed."""
    if not path.exists() or not path.is_file():
        return 0
    original = path.read_text(encoding='utf-8', errors='ignore')
    new_text, fixed = clean_rpy_content(original)
    if fixed > 0:
        backup = path.with_suffix(path.suffix + '.bak')
        if not backup.exists():
            backup.write_text(original, encoding='utf-8')
        path.write_text(new_text, encoding='utf-8')
    return fixed


def bulk_clean(root: Path) -> dict:
    """Recursively clean all .rpy files under root. Returns stats."""
    stats = {"files": 0, "fixed_files": 0, "total_fixes": 0}
    for p in root.rglob('*.rpy'):
        stats["files"] += 1
        fixed = clean_rpy_file(p)
        if fixed:
            stats["fixed_files"] += 1
            stats["total_fixes"] += fixed
    return stats

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Clean literal\\n artifacts in Ren'Py translation files")
    parser.add_argument('directory', nargs='?', default='.', help='Root directory to scan')
    args = parser.parse_args()
    stats = bulk_clean(Path(args.directory).resolve())
    print(f"Scanned {stats['files']} .rpy files | Fixed {stats['fixed_files']} files | Total header fixes: {stats['total_fixes']}")
