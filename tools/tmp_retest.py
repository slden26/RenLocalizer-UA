import re
pattern=re.compile(r'''(?P<quote>(?:[rRuUbBfF]{,2})?(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'))''')
code='greeting = f"Hello {player_name}"'
matches=list(pattern.finditer(code))
print(len(matches))
print([m.group('quote') for m in matches])
