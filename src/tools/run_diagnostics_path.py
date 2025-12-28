"""Run parser extraction on a target directory and write detailed diagnostic JSON.

Usage: python src/tools/run_diagnostics_path.py <target_dir>
"""
import sys
from pathlib import Path
import json
from src.core.parser import RenPyParser
from src.core.diagnostics import DiagnosticReport


def is_potential_false_positive(text):
    if text is None:
        return True
    s = text.strip()
    if not s:
        return True
    # Language-independent checks using Unicode letters
    # Short strings that don't contain letters are likely not translatable
    if len(s) < 4 and not any(ch.isalpha() for ch in s):
        return True
    # Remove placeholders/tags and check remaining letters
    import re
    cleaned = re.sub(r'(\[[^\]]+\]|\{[^}]+\})', '', s).strip()
    if sum(1 for ch in cleaned if ch.isalpha()) < 2:
        return True
    # Technical prefixes
    lw = s.lower()
    # Treat explicit code-like prefixes carefully: only flag when original
    # text appears to be lowercase/technical. Avoid flagging UI labels like
    # "Show quick menu" which start with a capitalized word.
    if lw.startswith(('label ', 'scene ')) and s[0].islower():
        return True
    if s.startswith('$'):
        return True
    return False


def main():
    if len(sys.argv) < 2:
        print('Usage: python src/tools/run_diagnostics_path.py <target_dir>')
        return
    target = Path(sys.argv[1])
    if not target.exists():
        print('Target does not exist:', target)
        return

    parser = RenPyParser()
    diag = DiagnosticReport(project=str(target), target_language='sample')

    rpy_files = list(target.rglob('*.rpy'))
    stats = {
        'files_scanned': 0,
        'total_extracted': 0,
        'with_raw_text': 0,
        'translation_id_present': 0,
        'translation_id_none': 0,
        'unique_translation_ids': 0,
        'potential_false_positives': 0,
    }

    collected = []
    for f in rpy_files:
        stats['files_scanned'] += 1
        try:
            entries = parser.extract_text_entries(f)
        except Exception as e:
            print(f"Error parsing {f}: {e}")
            continue
        for e in entries:
            stats['total_extracted'] += 1
            if e.get('raw_text'):
                stats['with_raw_text'] += 1
            try:
                from src.core.tl_parser import TLParser
                tid = TLParser.make_translation_id(str(f), e.get('line_number', 0) or 0, e.get('text') or '', e.get('context_path', []), e.get('raw_text'))
            except Exception:
                tid = None
            if tid:
                stats['translation_id_present'] += 1
            else:
                stats['translation_id_none'] += 1
            collected.append({
                'file': str(f),
                'text': e.get('text'),
                'raw_text': e.get('raw_text'),
                'line_number': e.get('line_number'),
                'translation_id': tid,
                'potential_false_positive': is_potential_false_positive(e.get('text'))
            })
            if is_potential_false_positive(e.get('text')):
                stats['potential_false_positives'] += 1

    tids = [c['translation_id'] for c in collected if c['translation_id']]
    stats['unique_translation_ids'] = len(set(tids))

    out = Path('diagnostics')
    out.mkdir(exist_ok=True)
    diag_file = out / f'{target.name}_diagnostic.json'
    report = {
        'target': str(target),
        'stats': stats,
        'samples': collected[:200]
    }
    with open(diag_file, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print(f'Wrote diagnostic: {diag_file}')
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()
