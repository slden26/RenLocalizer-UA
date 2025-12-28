"""Run parser extraction on example .rpy files and write a diagnostic JSON.

Usage: run from project root with PYTHONPATH so imports work.
"""
from pathlib import Path
from src.core.parser import RenPyParser
from src.core.diagnostics import DiagnosticReport
import json


def main():
    examples = list(Path('examples').glob('*.rpy'))
    parser = RenPyParser()
    diag = DiagnosticReport(project='examples', target_language='sample')

    for f in examples:
        try:
            entries = parser.extract_text_entries(f)
        except Exception as e:
            print(f"Error parsing {f}: {e}")
            continue
        for e in entries:
            # Compute a tentative translation_id when raw_text is available
            try:
                from src.core.tl_parser import TLParser
                tid = TLParser.make_translation_id(str(f), e.get('line_number', 0) or 0, e.get('text') or '', e.get('context_path', []), e.get('raw_text'))
            except Exception:
                tid = None
            diag.add_extracted(str(f), {
                'text': e.get('text'),
                'raw_text': e.get('raw_text'),
                'translation_id': tid,
                'line_number': e.get('line_number'),
                'context_path': e.get('context_path', [])
            })

    out = Path('examples') / 'diagnostic_sample.json'
    diag.write(str(out))
    print(f"Wrote diagnostic: {out}")
    print(json.dumps({'total_extracted': diag.total_extracted, 'files': len(diag.files)}, indent=2))


if __name__ == '__main__':
    main()
