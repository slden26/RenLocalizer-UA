from pathlib import Path

from src.core.tl_parser import TLParser


def test_translation_id_roundtrip(tmp_path: Path):
    tl_content = """translate turkish strings:
    old "Hello"
    new ""
"""
    tl_file = tmp_path / "strings.rpy"
    tl_file.write_text(tl_content, encoding="utf-8")

    parser = TLParser()
    parsed = parser.parse_file(str(tl_file))
    assert parsed
    entry = parsed.entries[0]
    tid = entry.compute_id()

    updated = parser.update_translations(parsed, {tid: "Merhaba"})
    assert 'new "Merhaba"' in updated
