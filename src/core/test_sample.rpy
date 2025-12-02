label start:
    e "Merhaba, [player_name]!"
    "Bu bir anlatıcı satırı."
    menu:
        "Devam etmek istiyor musun?":
            e "Evet."
    init python:
        x = _('Kaydet')
        y = "Bu çevrilmez"
    translate tr something:
        old "Hello."
        new "Merhaba."
