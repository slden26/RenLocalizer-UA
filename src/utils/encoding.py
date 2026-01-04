"""
Encoding helpers to read/write text defensively without crashing on bad bytes.
"""

from __future__ import annotations

import chardet
from pathlib import Path
from typing import Optional, Tuple


def read_text_safely(path: Path, preferred: Tuple[str, ...] = ("utf-8-sig", "utf-8")) -> Optional[str]:
    """
    Read file as text with tolerant fallbacks:
    - try preferred encodings first
    - then chardet detection with errors='replace'
    Returns None on I/O failure.
    """
    try:
        raw = path.read_bytes()
    except Exception:
        return None

    for enc in preferred:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue

    detected = chardet.detect(raw)
    enc = detected.get("encoding") or "utf-8"
    try:
        return raw.decode(enc, errors="replace")
    except Exception:
        return None


def normalize_to_utf8_sig(path: Path) -> bool:
    """
    Rewrite file to UTF-8-SIG with LF newlines.
    Returns True if rewrite succeeded.
    """
    text = read_text_safely(path)
    if text is None:
        return False
    try:
        path.write_text(text, encoding="utf-8-sig", newline="\n")
        return True
    except Exception:
        return False
