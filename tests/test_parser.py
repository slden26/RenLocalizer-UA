from src.core.parser import RenPyParser
from src.core.output_formatter import RenPyOutputFormatter


def test_parser_regex_attributes_exist():
    p = RenPyParser()
    for attr in [
        "label_def_re",
        "multiline_registry",
        "menu_def_re",
        "screen_def_re",
        "pattern_registry",
        "python_block_re",
    ]:
        assert hasattr(p, attr), f"RenPyParser missing attribute: {attr}"


def test_skip_extensions_removed():
    f = RenPyOutputFormatter()
    # These extensions should NOT be in the skip list (we removed them)
    for ext in ['.json', '.txt', '.xml', '.csv']:
        assert ext not in f.SKIP_FILE_EXTENSIONS


def test_protect_renpy_syntax_edge_cases():
    from src.core.translator import protect_renpy_syntax, restore_renpy_syntax
    # Edge-case: teknik tag, iç içe placeholder, karmaşık yapı
    samples = [
        "{color=#fff}Merhaba{/color}",
        "[player] {b}Kazandı{/b}",
        "{size=20}[score]{/size}",
        "{font=Comic}[name]{/font}",
        "{[player]} ve [{score}]",  # iç içe
        "[player] {color=#fff}Kazandı{/color}"
    ]
    for sample in samples:
        protected, placeholders = protect_renpy_syntax(sample)
        # Tüm teknik ve iç içe yapılar korunmalı
        for key, original in placeholders.items():
            assert key in protected
            assert original in sample
        # Geri dönüşümde orijinal metin elde edilmeli
        restored = restore_renpy_syntax(protected, placeholders)
        assert restored == sample


def test_quality_check():
    from src.core.parser import RenPyParser
    parser = RenPyParser()
    # Anlamlı, doğru ve teknik olmayan metin
    result = parser.quality_check("Merhaba, nasılsın?")
    assert result['is_meaningful'] is True
    assert result['has_grammar_error'] is False
    assert result['is_technically_valid'] is True

    # Teknik kod, dosya yolu, anlamsız metin
    result2 = parser.quality_check("config.version = 1.0")
    assert result2['is_meaningful'] is False
    assert result2['is_technically_valid'] is False

    # Dilbilgisi hatalı metin
    result3 = parser.quality_check("merhaba nasılsın")
    assert result3['has_grammar_error'] is True


def test_classify_text_type():
    from src.core.parser import RenPyParser
    parser = RenPyParser()
    assert parser.classify_text_type("menu \"Seçenek\":") == "menu"
    assert parser.classify_text_type("screen ana_ekran:") == "screen"
    assert parser.classify_text_type("e \"Merhaba!\"") == "character"
    assert parser.classify_text_type("config.version = 1.0") == "technical"
    assert parser.classify_text_type("Merhaba, nasılsın?") == "general"


def test_pyparse_python_calls_and_notify(tmp_path):
    from src.core.pyparse_grammar import extract_with_pyparsing
    sample = '''
label start:
    $ renpy.notify("Hello Player")
    python:
        _("Inner call")
        __("Double underscore")
        renpy.say(e, "Talk")
    '''
    out = extract_with_pyparsing(sample, file_path="test.rpy")
    texts = {e['text'] for e in out}
    assert "Hello Player" in texts
    assert "Inner call" in texts
    assert "Double underscore" in texts
    assert "Talk" in texts
