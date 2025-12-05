"""Test pattern matching for _make_source_translatable"""
import re

# Patterns from translation_pipeline.py - supporting both single and double quotes
patterns = [
    # textbutton "text" or textbutton 'text' -> textbutton _("text")
    (r"(textbutton\s+)(['\"])([^'\"]+)\2(\s*:|\s+action|\s+style|\s+xalign|\s+yalign|\s+at\s)", 
     r'\1_(\2\3\2)\4'),
    
    # text "..." or text '...' with size/color/etc
    (r"(\btext\s+)(['\"])([^'\"\[\]{}]+)\2(\s*:|\s+size|\s+color|\s+xpos|\s+ypos|\s+xalign|\s+yalign|\s+outlines|\s+at\s|\s+font|\s+style)", 
     r'\1_(\2\3\2)\4'),
    
    # tooltip "text" or tooltip 'text'
    (r"(tooltip\s+)(['\"])([^'\"]+)\2", 
     r'\1_(\2\3\2)'),
    
    # renpy.notify("text") or renpy.notify('text')
    (r"(renpy\.notify\s*\(\s*)(['\"])([^'\"]+)\2(\s*\))", 
     r'\1_(\2\3\2)\4'),
    
    # action Notify("text") or Notify('text')
    (r"(Notify\s*\(\s*)(['\"])([^'\"]+)\2(\s*\))", 
     r'\1_(\2\3\2)\4'),
]

# Skip patterns - supporting both quote types
skip_patterns = [
    r'_\s*\(\s*[\'"]',    # Already translatable
    r'[\'\"]\s*\+\s*[\'"]',    # String concatenation
    r'^\s*#',             # Comment
    r'^\s*$',             # Empty line
    r'define\s+',         # define statements
    r'default\s+',        # default statements
    r'=\s*[\'"][^\'"]*[\'"]\s*$',  # Simple assignment
    r'[\'"][^\'"]*\[[^\]]+\][^\'"]*[\'"]',  # Contains variable
    r'[\'"][^\'"]*\{[^\}]+\}[^\'"]*[\'"]',  # Contains tag
]

# Test cases - both single and double quotes
test_lines = [
    # Double quote tests
    ('textbutton "Nap":', True, 'textbutton with double quotes'),
    ('textbutton "Sleep till morning" action Jump("morning")', True, 'textbutton with action'),
    ('text "LOCKED" color "#FF6666" size 50', True, 'text with color/size'),
    ('text "Massage Course" size 60 color "#F9F5F7"', True, 'text with size/color'),
    ('text "[current_time]" size 50 color "#ffffff"', False, 'text with variable should NOT change'),
    ('tooltip "Dev Console (Toggle)"', True, 'tooltip should be wrapped'),
    ('renpy.notify("Item purchased!")', True, 'renpy.notify should be wrapped'),
    ('textbutton _("Already OK"):', False, 'already wrapped should NOT change'),
    ('text "{b}Bold text{/b}" size 50', False, 'text with tags should NOT change'),
    ('define config.name = "My Game"', False, 'define should NOT change'),
    
    # Single quote tests (same as above but with single quotes)
    ("textbutton 'Nap':", True, 'textbutton with single quotes'),
    ("textbutton 'Sleep till morning' action Jump('morning')", True, 'textbutton single with action'),
    ("text 'LOCKED' color '#FF6666' size 50", True, 'text single with color/size'),
    ("text 'Current Quest' size 30 color '#FFCC00'", True, 'text single with size/color'),
    ("text '[current_time]' size 50 color '#ffffff'", False, 'text single with variable should NOT'),
    ("tooltip 'Dev Console (Toggle)'", True, 'tooltip single should be wrapped'),
    ("renpy.notify('Item purchased!')", True, 'renpy.notify single should be wrapped'),
    ("textbutton _('Already OK'):", False, 'single already wrapped should NOT'),
    ("text '{b}Bold{/b}' size 50", False, 'text single with tags should NOT'),
    ("define config.name = 'My Game'", False, 'define single should NOT change'),
    
    # Mixed and edge cases  
    ('text "Moving to next plate..." size 30 xalign 0.5 color "#666666"', True, 'text with multiple attrs'),
    ('text "PURCHASED" size 50 color "#00FF00"', True, 'simple status text'),
    ('    textbutton "+100$" action Function(add_money, 100) style "dev_button"', True, 'indented textbutton'),
    ("    textbutton '+100$' action Function(add_money, 100) style 'dev_button'", True, 'indented textbutton single'),
    ('default player_name = "Player"', False, 'default assignment'),
    ('# textbutton "Comment":', False, 'commented line'),
    ('text "DEV" size 30 color "#FF0000" outlines [(1, "#FFFFFF")]:', True, 'text with outlines'),
    ("text 'Price: $35' size 50 color '#FCD756'", True, 'single with colon and dollar'),
]

print("Pattern Test Results")
print("=" * 70)

passed = 0
failed = 0

for line, should_change, description in test_lines:
    result = line
    
    # Check skip patterns
    should_skip = False
    for skip in skip_patterns:
        if re.search(skip, line):
            should_skip = True
            break
    
    # Apply patterns if not skipped
    if not should_skip:
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result)
    
    did_change = (line != result)
    
    if did_change == should_change:
        status = "PASS"
        passed += 1
    else:
        status = "FAIL"
        failed += 1
    
    print(f"\n[{status}] {description}")
    print(f"  Input:    {line}")
    print(f"  Output:   {result}")
    print(f"  Changed:  {did_change} (expected: {should_change})")

print("\n" + "=" * 70)
print(f"Results: {passed} passed, {failed} failed")
