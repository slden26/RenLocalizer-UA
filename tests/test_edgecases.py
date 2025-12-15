def test_protect_restore_nested_placeholders():
    from src.core.translator import protect_renpy_syntax, restore_renpy_syntax

    samples = [
        "Hello {[player]} and {color=#fff}[score]{/color}",
        "[player] says: {b}Win {score}{/b}",
        "Prefix {[outer{inner}]} suffix",
    ]

    for s in samples:
        protected, placeholders = protect_renpy_syntax(s)
        # All placeholders must appear in protected string
        for key in placeholders.keys():
            assert key in protected

        restored = restore_renpy_syntax(protected, placeholders)
        assert restored == s


def test_triple_quote_placeholder_preservation():
    from src.core.translator import protect_renpy_syntax, restore_renpy_syntax

    s = '"""Line1 {color=#fff}[player]{/color}\nLine2 """'
    protected, placeholders = protect_renpy_syntax(s)
    for key in placeholders.keys():
        assert key in protected
    restored = restore_renpy_syntax(protected, placeholders)
    assert restored == s
