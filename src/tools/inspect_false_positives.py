"""Analyze a diagnostic JSON and print most frequent potential false positives."""
import sys
import json
from collections import Counter

if len(sys.argv) < 2:
    print('Usage: python src/tools/inspect_false_positives.py <diagnostic.json> [topN]')
    sys.exit(1)

path = sys.argv[1]
topn = int(sys.argv[2]) if len(sys.argv) > 2 else 50

with open(path, 'r', encoding='utf-8') as fh:
    data = json.load(fh)

counter = Counter()
for s in data.get('samples', []):
    if s.get('potential_false_positive'):
        text = s.get('text') or ''
        counter[text] += 1

print(f"Total potential false positives in samples: {sum(counter.values())}")
for text, cnt in counter.most_common(topn):
    print(f"{cnt:5d}  {text}")
