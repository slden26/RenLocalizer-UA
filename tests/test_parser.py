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
