# RenLocalizer

RenLocalizer is an advanced, user-friendly tool for unpacking, parsing, and translating Ren'Py visual novels. It features a guided UnRen workflow, multi-engine translation, context-aware parsing, and a bilingual UI (English/Turkish).

> ⚠️ This project is actively developed and assisted by AI. Expect frequent updates and improvements.

## 🚀 Key Features (v2.2.8)
- **Multi-Engine Translation:** Google (web), DeepL API, and more. Proxy rotation and adaptive fallback supported.
- **Batch & Performance Control:** All performance parameters (max characters, batch size, parallel requests) are fully manageable from the UI.
- **Parallel Google Endpoints:** Expanded endpoint list for faster, more reliable translation.
- **Context-Aware Parser:** Handles dialogue, menu, screen, python blocks, triple-quoted monologues, and preserves all placeholders and tags.
- **RPYC/RPYMC Support:** SDK-free AST reader for both .rpyc and .rpymc files, with context-aware deduplication.
- **Output:** Ren'Py-compliant `translate strings` (old/new) with stable IDs and language init file generation.
- **UI:** Modern dark/solarized themes, auto language detection, and full settings for threads, batch, delay, proxy, and more.
- **Placeholder Safety:** Ren'Py variables, technical lines, and all special markers are always protected during translation.
- **Automated Testing:** Built-in tests for placeholder safety and translation integrity.

## ⚠️ Known Limitations
- The program cannot translate 100% of all texts. Translation rate varies by game. Visual Novels are almost fully translatable, but sandbox/complex games may have untranslated parts (quests, skills, inventory, menus, etc.) due to encrypted .rpymc files or custom data structures. Even with UnRen, these contents may not be accessible.
- The program is not yet advanced enough to fully translate such technical/gameplay content, and the developer's knowledge/experience is currently insufficient to overcome this limitation. Missing translations in advanced game systems, encrypted data, or custom menus are to be expected.
- For advanced translation and full coverage, please wait for future versions.

## 🛠️ Installation
```sh
git clone https://github.com/YOUR_USERNAME/RenLocalizer.git
cd RenLocalizer
python -m venv venv
venv\Scripts\activate   # or source venv/bin/activate
pip install -r requirements.txt
python run.py
```

## ⚡ Quick Start
1. Run `python run.py`.
2. Select your Ren'Py project folder.
3. Choose UnRen mode if prompted (auto/manual).
4. Select source/target language and engine; adjust batch/concurrency as needed.
5. Start translation; outputs will be in `game/tl/<lang>/`.

## ⚙️ Settings Highlights
- Threads (1–256), batch size (1–2000), request delay, retries.
- Proxy enable/rotate with failure limits and custom list.
- UI language auto-detect; theme selection.

## 🧠 Parser & Engine Notes
- Respects indentation and context for label, menu, screen, python blocks.
- Preserves placeholders (`[var]`, `{tag}`), handles `_`, `__`, `renpy.say/notify/input`, `Text()`.
- Emits context_path + translation_id for stable mapping; deduplication is context-aware.

## 🤝 Contribute / Troubleshoot
- If `src` not found: set `PYTHONPATH` or run from repo root.
- Slow/blocked: tune threads/batch/delay, enable proxy.
- PRs welcome: engines, performance, language support, UI polish.

## 📄 License
GPL-3.0-or-later (see `LICENSE`).
