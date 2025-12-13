import pytest
from src.core.translator import protect_renpy_syntax, restore_renpy_syntax

@pytest.mark.parametrize("original,expected_placeholders", [
    ("[player] kazandı!", ["[player]"]),
    ("{color=#fff}Merhaba{/color}", ["{color=#fff}", "{/color}"]),
    ("?V000? ve ⟦V000⟧", ["?V000?", "⟦V000⟧"]),
    ("[who.age] {b}Kazandı{/b}", ["[who.age]", "{b}", "{/b}"]),
    ("{#disambig} [var]", ["{#disambig}", "[var]"]),
    ("[player] {color=#fff}Kazandı{/color}", ["[player]", "{color=#fff}", "{/color}"]),
    ("⟦V000⟧", ["⟦V000⟧"]),
    ("?T123?", ["?T123?"]),
])
def test_protect_restore_renpy_syntax(original, expected_placeholders):
    protected, placeholders = protect_renpy_syntax(original)
    # Tüm placeholder'lar korunmalı
    for ph in expected_placeholders:
        assert any(ph == v for v in placeholders.values()), f"Eksik placeholder: {ph}"
        assert any(k in protected for k, v in placeholders.items() if v == ph), f"Placeholder korunmadı: {ph}"
    # Geri dönüşümde orijinal metin elde edilmeli
    restored = restore_renpy_syntax(protected, placeholders)
    assert restored == original

@pytest.mark.parametrize("broken", [
    "Çeviri sırasında [player] bozuldu!",
    "{color=#fff} yanlış çevrildi",
    "?V000? kayboldu",
    "⟦V000⟧ eksik",
    "[who.age] değişti",
])
def test_broken_placeholder_detection(broken):
    # Placeholder'lar bozulmuşsa, orijinal ile karşılaştırınca eksik olur
    # Bu test, pipeline'daki validate_placeholders fonksiyonunun mantığını simüle eder
    import re
    def extract_placeholders(text):
        return set(re.findall(r'\[[^\]]+\]|\{[^}]+\}|\?[A-Za-z]\d{3}\?|[\u27e6][^\u27e7]+[\u27e7]', text))
    # Orijinal placeholder'lar
    orig = "[player] {color=#fff} ?V000? ⟦V000⟧ [who.age]"
    orig_ph = extract_placeholders(orig)
    broken_ph = extract_placeholders(broken)
    # Orijinaldeki herhangi bir placeholder bozulmuşsa, test fail olmalı
    assert not orig_ph.issubset(broken_ph), f"Bozuk placeholder tespit edilemedi: {broken}"
