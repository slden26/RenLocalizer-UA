import json
import sys

if len(sys.argv) < 2:
    print('Usage: python src/tools/list_false_positives.py <diagnostic.json>')
    sys.exit(1)

p = sys.argv[1]
with open(p, encoding='utf-8') as f:
    j = json.load(f)
    fps = [s for s in j.get('samples', []) if s.get('potential_false_positive')]
    print(len(fps))
    for s in fps:
        print('---')
        print(s.get('file'), s.get('line_number'))
        print(s.get('text'))
