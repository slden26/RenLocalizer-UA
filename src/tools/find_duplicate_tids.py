"""Find duplicate translation IDs in a diagnostic JSON and write a small report."""
import json
from collections import Counter, defaultdict
from pathlib import Path

p = Path('diagnostics') / 'summertimesaga_diagnostic.json'
if not p.exists():
    print('Diagnostic not found:', p)
    raise SystemExit(1)

j = json.load(open(p, encoding='utf-8'))
rows = j.get('samples', [])

counter = Counter()
by_tid = defaultdict(list)
for r in rows:
    tid = r.get('translation_id')
    counter[tid] += 1
    by_tid[tid].append(r)

# duplicates (tid is not None)
dups = {tid: cnt for tid, cnt in counter.items() if tid and cnt > 1}
print('Total rows:', len(rows))
print('Unique tids:', len([t for t in counter.keys() if t]))
print('Duplicate tids count:', len(dups))

out = {'total_rows': len(rows), 'unique_tids': len([t for t in counter.keys() if t]), 'duplicate_count': len(dups), 'duplicates': []}
for tid, cnt in sorted(dups.items(), key=lambda x: -x[1])[:200]:
    samples = by_tid[tid][:5]
    out['duplicates'].append({'translation_id': tid, 'count': cnt, 'examples': samples})

outp = Path('diagnostics') / 'summertimesaga_duplicate_tids.json'
with open(outp, 'w', encoding='utf-8') as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)
print('Wrote', outp)
print('Top duplicates written to report.')
