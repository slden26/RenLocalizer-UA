"""Scan a target directory for .csv/.json/.txt and report extraction stats.
Usage: python src/tools/run_data_formats_diagnostics.py summertimesaga
"""
import sys
from pathlib import Path
import json
from collections import Counter
from src.core.parser import RenPyParser


def is_potential_false_positive(text):
    import re
    if text is None:
        return True
    s = text.strip()
    if not s:
        return True
    if len(s) < 4 and not re.search(r'[A-Za-zÇĞİÖŞÜçğıöşü]', s):
        return True
    cleaned = re.sub(r'(\[[^\]]+\]|\{[^}]+\})', '', s).strip()
    if len(re.findall(r'[A-Za-zÇĞİÖŞÜçğıöşü]', cleaned)) < 2:
        return True
    return False


def main():
    if len(sys.argv) < 2:
        print('Usage: python src/tools/run_data_formats_diagnostics.py <target_dir>')
        return
    target = Path(sys.argv[1])
    if not target.exists():
        print('Target not found:', target)
        return

    parser = RenPyParser()
    stats = {
        'csv_files': 0,
        'json_files': 0,
        'txt_files': 0,
        'csv_extracted': 0,
        'json_extracted': 0,
        'txt_extracted': 0,
        'csv_fp': 0,
        'json_fp': 0,
        'txt_fp': 0,
    }
    collected = []
    # CSV
    for f in target.rglob('*.csv'):
        stats['csv_files'] += 1
        entries = parser.extract_from_csv(f)
        stats['csv_extracted'] += len(entries)
        for e in entries:
            collected.append({'file': str(f), 'text': e.get('text'), 'line_number': e.get('line_number'), 'source': 'csv'})
            if is_potential_false_positive(e.get('text')):
                stats['csv_fp'] += 1
    # JSON
    for f in target.rglob('*.json'):
        stats['json_files'] += 1
        entries = parser.extract_from_json(f)
        stats['json_extracted'] += len(entries)
        for e in entries:
            collected.append({'file': str(f), 'text': e.get('text'), 'line_number': e.get('line_number'), 'source': 'json'})
            if is_potential_false_positive(e.get('text')):
                stats['json_fp'] += 1
    # TXT
    for f in target.rglob('*.txt'):
        stats['txt_files'] += 1
        entries = parser.extract_from_txt(f)
        stats['txt_extracted'] += len(entries)
        for e in entries:
            collected.append({'file': str(f), 'text': e.get('text'), 'line_number': e.get('line_number'), 'source': 'txt'})
            if is_potential_false_positive(e.get('text')):
                stats['txt_fp'] += 1

    out = {'target': str(target), 'stats': stats, 'samples': collected[:500]}
    outp = Path('diagnostics') / f'{target.name}_data_diagnostic.json'
    outp.parent.mkdir(exist_ok=True)
    with open(outp, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print('Wrote', outp)
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()
