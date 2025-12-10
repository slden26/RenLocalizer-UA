# Changelog

## [2.2.6] - 2025-12-09
### Added
- Backup mechanism in `_make_source_translatable` to ensure original files are preserved before modifications.
- Enhanced `read_rpyc_header` to handle both `RENPY RPC2` and `RENPY RPC3` headers, ensuring compatibility with newer Ren'Py versions.
- Added an option to scan `renpy/` engine files in `parser.py`, allowing users to include engine files in the translation process if enabled.
- Implemented a safety check in `translation_pipeline.py` to prevent modifications to `renpy/` engine files, ensuring engine integrity.
- Added support for detecting variable assignments in lists and tuples spanning multiple lines in `deep_scan_strings`.
- Introduced a lookback mechanism in `parser.py` to capture multi-line list contexts.
- Enhanced `_extract_strings_from_line` in `rpyc_reader.py` to detect and process variable assignments for lists and tuples.

### Changed
- Updated `init python` block in `translation_pipeline.py` to respect the user's persistent language preference, ensuring the game's language menu remains functional.

- Updated `_resolve_search_root` to avoid forcing the search root to the `game` folder. This ensures all files in the selected directory are scanned, even if the `game` folder exists but is not the primary location for scripts.
- Fixed `_is_excluded_rpy` to handle backslash replacement correctly, preventing path resolution issues on Windows.

### Fixed
- Addressed potential file exclusion issues caused by overly restrictive path resolution logic.
- Improved compatibility with non-standard Ren'Py project structures.
- Resolved `NameError` in `_extract_strings_from_line` by defining the missing `string_literal_re` regex.
- Improved handling of multi-line lists to ensure no translatable strings are missed.
 - Fixed `preserve_placeholders` return value in `src/core/parser.py` (now returns `(processed_text, placeholder_map)`), resolving `ValueError: too many values to unpack (expected 2)` during `.rpyc` extraction.
 - Added detailed diagnostics to `src/core/rpyc_reader.py` for unpickle failures: logs full traceback, `header.slots` summary and a hex snippet of the first 512 bytes of the decompressed pickle; also writes diagnostics to `stderr` as a fallback so redirected console logs capture the data.
 - Switched several extraction-level error logs to `logger.exception` to ensure tracebacks are recorded in logs.
 - Fixed Windows console encoding in `run.py` by attempting to reconfigure `stdout`/`stderr` to UTF-8 (errors='replace') to avoid `UnicodeEncodeError` on consoles with legacy code pages.

## [2.2.5] - 2025-12-08
### Added
- **RPYC Reader Integration**: Enabled the ability to read `.rpyc` files directly using AST extraction. This feature can be toggled in the UI.
- **Deep Scan Algorithm**: Added support for scanning hidden strings in Python blocks, dictionaries, and variable assignments. Includes advanced filtering to exclude technical strings.
- **Advanced Scan Options in UI**: Introduced checkboxes for enabling "Deep Scan" and "RPYC Reader" in the main window.

### Changed
- Updated the folder scanning logic to support combined extraction of `.rpy` and `.rpyc` files when advanced options are enabled.
- Improved context-aware parsing for better accuracy in identifying translatable strings.

### Fixed
- Minor UI adjustments to ensure compatibility with the new scanning options.

---

## [2.2.4] - 2025-12-07

### 🚀 Enhanced RPYC Reader (AST v2)
Major improvements to the RPYC Reader based on official Ren'Py AST source code:

**New AST Node Types:**
- **TranslateSay:** Combined translate+say node for modern Ren'Py versions (7.5+/8.x)
- **PostUserStatement:** Post-execution nodes for user-defined statements
- **ArgumentInfo/ParameterInfo:** Full argument and parameter handling
- **ATL Support:** RawBlock and transform-related classes

**Enhanced Unpickler:**
- **30+ AST classes:** Comprehensive coverage of renpy.ast, renpy.sl2.slast, renpy.atl
- **CSlots support:** Compatible with Ren'Py 8.x slot-based serialization
- **Store classes:** Game-defined store.* classes handled gracefully
- **Character/Display:** renpy.character and display module support

**Improved Text Extraction:**
- `_("text")` and `__("text")` translation functions

### 🛠️ UnRen Improvements & Fixes
- **Always run .bat scripts via `cmd.exe /c call`** for deterministic behavior on Windows
- **Fallback script lookup:** If exact expected script name is unavailable, UnRen now falls back to a nearest matching .bat file found under the cached archive
- **Zip extraction flattening:** Archives that wrap files inside a top-level folder are now flattened during extraction, preventing missing script detection
- **Preflight diagnostics:** Added `verify_installation()` to inspect cached UnRen files and return a diagnostic report (used by UI)
- **Better pipeline logging:** UnRen preflight diagnostic info now logs before execution, assisting support and debugging

- `renpy.notify("text")` notifications
- `renpy.say(who, "text")` programmatic dialogue
- `Text("content")` displayable text
- `DynamicCharacter("name")` definitions
- `config.name/version` and `gui.*text*` patterns

**Bug Fixes:**
- **Path filter fix:** Fixed critical bug where `\\renpy\\` filter pattern was matching user's parent folder path (e.g., `Desktop\Renpy\game\...`) instead of just the `renpy/` engine subfolder
- Now uses relative path from game directory for accurate filtering

---

## [2.2.3] - 2025-12-06

### 📦 RPYC Reader (Experimental)
New module for reading compiled `.rpyc` files directly without decompilation:
- **Direct AST extraction:** Reads pickle-serialized AST from compiled Ren'Py files
- **No unrpyc needed:** Works independently, no external decompiler required
- **Supports both formats:** RPYC v1 (zlib compressed) and RPYC v2 (RENPY RPC2 header)
- **Full AST coverage:** Extracts dialogue, menu choices, screen text, translated strings
- **Custom unpickler:** Uses fake AST classes to safely deserialize Ren'Py objects
- **Parser integration:** New methods `extract_from_rpyc()` and `extract_combined()` in parser module
- **Smart validation:** If RPYC Reader is enabled but no .rpyc files exist, translation is cancelled with detailed error message explaining how to fix (run game once or disable the option)
- **Note:** Experimental feature, works best as complement to standard .rpy extraction

---

## [2.2.2] - 2025-12-06

### 🔍 Deep String Scanner (Experimental)
New experimental feature to find hidden strings that normal regex patterns miss:
- **init python blocks:** Scans dictionary values, list items, and variable assignments inside Python blocks
- **Programmatic strings:** `$ my_text = "Hello"` style assignments
- **Data structures:** Strings inside dicts and lists used for dynamic content
- **Multi-line strings:** Now correctly captures triple-quoted (`"""..."""`) strings that span multiple lines
- **Settings UI:** Added checkbox in Settings → Translation → Advanced Scan section with tooltip explanation
- **Note:** This is experimental and may include false positives. Review extracted texts carefully.

### 🗑️ Removed DeepL Web Engine
- **Removed `DeepL Web (Free)` engine** - The unofficial community-hosted DeepLX endpoints proved too unreliable for production use. Endpoints frequently go offline, require API keys, or become rate-limited without notice.
- Users needing free translation should use **Google Translate (WEB)** which remains stable with multi-endpoint fallback and Lingva backup.
- Users wanting DeepL quality should use the official **DeepL API** with their own API key.

### 🎯 Enhanced Parser Coverage
Added new regex patterns for better text extraction:
- **ATL text blocks:** Captures `text "..."` inside animation/transform blocks
- **renpy.say() calls:** Programmatic dialogue via `renpy.say(char, "text")`
- **Action text patterns:** `action SetField(..., _("text"))` and similar
- **Caption attributes:** `vbar caption "Volume"`, `slider caption "..."` etc.
- **Frame/window titles:** `frame title "Settings"`, `window title "..."` 
- **Generic `_()` fallback:** Catches any `_("text")` pattern for complex expressions

### 📚 Updated Documentation
- **Help → Info → Features:** Updated feature list with Deep String Scanner, corrected translation engine info (removed Yandex/Bing references)
- **Upcoming features:** Replaced outdated "AI Filtering" with "Text Types UI"

### 🧹 Code Cleanup
- Removed `DeepLWebTranslator` class from translator module.
- Removed `DEEPL_WEB` enum value from `TranslationEngine`.
- Cleaned up engine combo boxes in main window and integrated dialog.
- Removed `deepl_web` entries from locale files.

## [2.2.1] - 2025-12-05

### 🩹 Bugfixes & Polish
- **Pipeline cleanup:** Improved pipeline worker shutdown and deterministic cleanup to allow subsequent runs without restarting the app. Added background translator session closure to reduce resource leakage.
- **Localization:** Converted several remaining hardcoded Turkish UI messages in `translation_pipeline.py` to locale keys and added matching entries to both `locales/english.json` and `locales/turkish.json`.
- **GUI stability:** Ensured integrated pipeline dialog and main window properly wait for worker termination and re-enable controls after stop/finish.

### 🧪 Notes
- Syntax checks run and source compiled successfully after these changes. Functional verification (start → finish → start; start → stop → restart) is recommended to confirm runtime behavior on your environment.


## [2.2.0] - 2025-12-03

### 🔄 Translation System Overhaul
- **String Translation Format:** Switched from hash-based dialogue translation (`translate lang block_xxx:`) to Ren'Py String Translation format (`translate lang strings: old "..." new "..."`). This format works universally without requiring matching translation IDs.
- **Single Output File:** All translations (dialogues + UI) are now consolidated into a single `strings.rpy` file, preventing duplicate string errors that occurred when the same text appeared in multiple source files.
- **No Ren'Py SDK Dependency:** Translation templates are generated entirely by RenLocalizer's parser - no external Ren'Py SDK installation required.
- **Global Deduplication:** Identical strings are now deduplicated globally across all source files, ensuring each string is defined only once.

### 🛠️ UnRen & Pipeline Improvements
- **EXE Path Resolution:** Fixed UnRen menu to correctly resolve game directory when an EXE file is selected instead of using the EXE's path directly.
- **Auto-UnRen on RPA Detection:** When `.rpa` archive files are detected in the game folder, UnRen is now automatically triggered before translation.
- **`_get_game_directory()` Helper:** Added method to properly extract game folder from EXE path or use folder path directly.
- **`_has_rpa_files()` Helper:** Added method to check for `.rpa` archives in directory.

### 🎯 Parser Enhancements (Ren'Py Compliance)
Based on official Ren'Py translation documentation:
- **Disambiguation Tags `{#identifier}`:** Preserved with `⟦D000⟧` markers - allows same text in different contexts (e.g., `"New"`, `"New{#project}"`, `"New{#game}"`).
- **Translatable Variable Flag `[var!t]`:** Variables marked with `!t` flag are now identified with `⟦VT000⟧` markers for runtime translation.
- **Hidden Label Exclusion:** Labels with `hide` clause (`label xxx hide:`) are now excluded from translation extraction.
- **NVL Mode Support:** Added `nvl_character_re` pattern for NVL character definitions.
- **Dialogue with ID:** Added `dialogue_with_id_re` pattern for `e "Text" id some_id` format.
- **Voice Statement Pattern:** Added pattern for `voice "audio/file.ogg"` localization reference.

### 🧹 Major Codebase Cleanup
- **Removed 11 unused/legacy files:** Cleaned up old config versions (`config_old.py`, `config_new.py`), backup parsers (`parser_backup.py`, `parser_simple.py`), obsolete dialogs (`info_dialog_backup.py`, `info_dialog_new.py`, `model_download_dialog.py`), test files, and `rpy_cleanup.py`.
- **Removed SDK Generator:** Deleted experimental `sdk_generator.py` and `sdk_generator_dialog.py` - feature was incomplete.
- **Cleared all `__pycache__` directories:** Reduced repository size and prevented stale bytecode issues.

### 🎯 UI Simplification
- **Removed Text Types tab:** Eliminated the Text Types filter tab from both Settings and Info dialogs. The smart `_()` wrapping system now handles UI element translation automatically.
- **Removed "Generate from SDK" menu:** Removed the incomplete SDK translation generator from Tools menu.
- **Streamlined Settings:** Now 4 tabs (General, Translation, Proxy, Advanced) instead of 5.
- **Streamlined Info Dialog:** Now 6 tabs (Formats, Multi-Endpoint, Performance, Features, Troubleshooting, UnRen) instead of 7.

### ✨ Updated Features Section
Completely refreshed the Features tab in Info Dialog with current capabilities:
- 🚀 **Multi-Endpoint Google (v2.1.0):** 2-3x faster translation with parallel server requests
- 🎯 **Smart UI Wrapping:** Auto-wraps textbutton, text, Notify elements with `_()` for Ren'Py translation
- 🔄 **Variable Protection:** Safely preserves `[player]`, `{b}`, `{color}` tags during translation
- ⚡ **Parallel Processing:** Async workers for simultaneous file processing
- 📚 **Glossary System:** Define preferred translations for frequently used terms
- 🌐 **Multi-Engine Support:** Google, DeepL, Yandex and more
- 🔧 **UnRen Integration:** Built-in .rpa extraction and .rpyc decompilation
- 💾 **Auto-Save:** Automatic translation file saving on completion

### 🔧 Technical Improvements
- **Simplified translation pipeline:** Removed SDK generator dependencies from `translation_pipeline.py`.
- **Cleaner locale files:** Removed obsolete `text_types` tab references and `sdk_generator_menu` entries.
- **Reduced complexity:** Fewer moving parts means easier maintenance and fewer potential bugs.
- **`_generate_all_strings_file()` Method:** New method that creates unified translation file for all text types.
- **`_is_hidden_context()` Method:** Added to parser for hidden label detection.

## [2.1.2] - 2025-12-03

### 🔧 Encoding & Compatibility Fixes
- **UTF-8 BOM Encoding:** All translation output files now use `utf-8-sig` encoding (UTF-8 with BOM). This ensures Ren'Py correctly reads Cyrillic (Russian, Ukrainian), Asian (Chinese, Japanese, Korean), and other non-Latin character translations on all systems.
- **Consistent Line Endings:** Added explicit `newline='\n'` to prevent Windows CRLF issues that could cause Ren'Py parse errors.
- **Language Init File Fix:** The language initialization file (`a0_[lang]_language.rpy`) now also uses UTF-8 BOM encoding.
- **Dynamic Version Header:** Translation file headers now show the correct RenLocalizer version dynamically.

### 🛡️ Error Prevention
- **Cyrillic/Russian Support:** Fixed encoding issues that caused `UnicodeDecodeError` with Russian (`0xbb` byte) and other Cyrillic translations.
- **Parse Error Prevention:** Ensured all generated `.rpy` files are fully UTF-8 compliant for Ren'Py 8.x compatibility.

## [2.1.1] - 2025-12-03

### 🎨 Theme & UI Consistency
- **Fusion Style Applied:** Added `app.setStyle("Fusion")` to ensure consistent cross-platform appearance. This prevents Windows/system themes from interfering with QSS styles.
- **QWidget/QLabel Base Styles:** Added explicit `QWidget` and `QLabel` style definitions to all themes (Dark, Light, Solarized). Text colors now inherit correctly on all systems.
- **Fixed Text Color Issues:** Resolved issue where some users saw white text turning black on their systems due to missing base widget styles.

### 🎯 Parser Fixes
- **Python Format String Filtering:** Added filtering for Python format strings like `{:,}`, `{}Attitude:{}`, `{:3d}` that should not be translated. These caused Ren'Py parse errors when included in translation files.

### 🔧 Output Encoding Fix
- **UTF-8 BOM Encoding:** Translation files are now written with UTF-8-sig encoding (BOM) to ensure Ren'Py correctly reads files on all Windows systems.
- **Unix Line Endings:** Explicit `newline='\n'` ensures consistent line endings across all platforms.

## [2.1.0] - 2025-12-03

### 🚀 Performance: Multi-Endpoint Google Translator
- **4 Google mirrors:** Translation requests now use 4 different Google endpoints (`googleapis.com`, `google.com`, `google.com.tr`, `google.co.uk`) with intelligent rotation.
- **Parallel endpoint racing (single + batch):** Both single and batch translations try multiple endpoints simultaneously - fastest response wins.
- **Endpoint failure tracking:** Failing endpoints are temporarily deprioritized, requests automatically route to healthy mirrors.
- **Lingva fallback:** When all Google endpoints fail, automatically falls back to Lingva Translate (free, no API key needed).
- **Increased batch size:** `max_slice_chars` increased from 6000 to 12000 for fewer HTTP requests.
- **Higher concurrency:** `multi_q_concurrency` increased from 8 to 16 parallel requests.
- **~2-3x faster:** Combined optimizations result in significantly faster batch translations.

### ⚙️ New Settings (Translation Tab)
- **Use Multi-Endpoint:** Sends parallel requests to multiple Google servers.
- **Lingva Fallback:** Falls back to free Lingva service when Google fails.
- **Concurrent Requests:** Number of endpoints to query simultaneously (default: 16).
- **Max Characters Per Request:** Maximum characters per translation request (default: 12000).

### 💡 UX Improvements
- **Tooltips for all settings:** Every setting now has a descriptive tooltip on hover explaining its purpose.
- **New Info Dialog tab:** Added "Multi-Endpoint (v2.1.0)" tab in Help → Info explaining the new translation architecture.
- **Bilingual tooltips:** All tooltips available in both Turkish and English.

### 🎯 Parser & Translation Fixes
- **`_()` Translatable Strings:** Added new patterns to capture `textbutton _("History")` and `text _("text")` as `translatable_string` type - these are now ALWAYS translated.
- **Case-Sensitive Deduplication:** Fixed critical bug where strings with different capitalization (e.g., "Save" vs "save", "History" vs "HISTORY") were incorrectly treated as duplicates. Ren'Py string matching is case-sensitive, and RenLocalizer now properly preserves all case variants.
- **UI Label Recognition:** Removed "History", "Help", "Settings", "Credits" from technical terms blocklist - these are valid UI labels that should be translated.
- **Ren'Py Documentation Compliance:** Full review against official Ren'Py translation documentation to ensure all patterns are correctly captured.

### 🔧 Technical
- `GoogleTranslator` now accepts `config_manager` parameter to read settings from config.
- `_multi_q()` batch translation now uses parallel endpoint racing instead of sequential fallback.
- Settings are properly saved/loaded from `config.json`.
- Proxy system works with new multi-endpoint architecture.
- **parser.py:** Added `textbutton_translatable_re` and `screen_text_translatable_re` patterns for `_()` marked screen elements.
- **output_formatter.py:** Fixed deduplication to use case-sensitive comparison (`string_key = result.original_text.strip()` instead of `.lower()`).

## [2.0.9] - 2025-12-02

### 🚨 Critical Fix: Standalone EXE Support
- **Complete PyQt6 bundling:** Used `collect_all('PyQt6')` to include all Qt binaries, plugins and DLLs for standalone operation on systems without Python.
- **Manual Qt6 DLL inclusion:** Added all DLLs from `Qt6/bin/` directory to both root and `PyQt6/Qt6/bin/` for redundant DLL discovery.
- **Dual plugin paths:** Critical plugins (`platforms/qwindows.dll`, `styles/`, `imageformats/`, `tls/`) are now placed in both `PyQt6/Qt6/plugins/` and root-level `plugins/` for maximum compatibility.
- **Qt environment setup:** Added `setup_qt_environment()` function that sets `QT_PLUGIN_PATH` and adds Qt DLL directories to `PATH` before Qt import.
- **Python 3.8+ DLL loading:** Added `os.add_dll_directory()` calls for all Qt DLL paths - required because Python 3.8+ changed Windows DLL search behavior.
- **Critical DLL pre-loading:** Pre-loads `Qt6Core.dll`, `Qt6Gui.dll`, `Qt6Widgets.dll` via `ctypes.CDLL()` before PyQt6 import to ensure DLLs are in memory.
- **Lazy GUI imports:** Restructured `src/__init__.py` and `src/gui/__init__.py` to avoid Qt import at package level, preventing DLL load failures.
- **Better error handling:** Improved `run.py` to catch Qt DLL load failures with detailed error messages before crashing.
- **Fixed "No module named PySide6" error:** EXE now works correctly on machines without Python or Qt installed.
- **Fixed "DLL load failed while importing QtWidgets" error:** Qt plugins are now properly bundled and discoverable.

### 🛡️ System Compatibility Checks
- **Visual C++ Runtime check:** Added `check_vcruntime()` that verifies `vcruntime140.dll` and `msvcp140.dll` presence before Qt import, showing download link if missing.
- **Windows version check:** Added `check_windows_version()` to detect 32-bit vs 64-bit architecture and show appropriate error message.
- **User-friendly error messages:** All startup errors now display Windows MessageBox with clear instructions instead of silent crashes.
- **Debug mode:** Added `RenLocalizer V2 DEBUG.exe` build with console output for troubleshooting startup issues.

### 🔍 Enhanced Debug Output
- **MEIPASS directory listing:** DEBUG exe now lists all files/folders in the extraction directory to diagnose missing components.
- **PyQt6 directory check:** Specifically checks and lists PyQt6 folder contents.
- **Qt6 DLL inventory:** Reports number of Qt6*.dll files found in root.
- **qwindows.dll search:** Recursively searches for qwindows.dll and reports all found locations.
- **DLL directory tracking:** Reports which directories were added via `os.add_dll_directory()`.
- **Pre-load status:** Reports success/failure of each critical DLL pre-load attempt with specific error messages.

> ⚠️ **Note:** EXE size increased from ~41MB to ~150MB due to complete Qt framework and DLL inclusion. This is necessary for standalone operation on systems without development tools.

## [2.0.8] - 2025-12-02

### 🔧 Output Format & Parser Fixes
- **Simple format fix:** Fixed output format selection where "simple" mode was still producing "old/new" format. Simple format now correctly outputs `# "original"` comment followed by `"translated"` string.
- **Technical string filtering:** Parser now correctly detects and filters shader/technical parameters like `vertex_200=`, `fragment_350=`, `u__duration=10.0` by recognizing Python block context (`init python:`, `python:`, `python early:`).
- **Python context detection:** Added `_is_python_context()` method to parser for accurate identification of code blocks vs dialogue.

### 📦 PyInstaller & Distribution
- **Comprehensive hidden imports:** Added all required aiohttp dependencies (`aiohappyeyeballs`, `aiosignal`, `frozenlist`, `multidict`, `yarl`, `propcache`, `attrs`, `async_timeout`) to spec file.
- **SSL certificates:** Integrated certifi CA bundle using `collect_data_files('certifi')` for proper HTTPS connections.
- **Encoding support:** Added `charset_normalizer` for robust character encoding detection.
- **HTTP dependencies:** Included `urllib3` and `idna` for complete requests support.
- **Working directory fix:** Added `get_app_dir()` function and `os.chdir(APP_DIR)` in launcher to ensure logs directory and config files work correctly in frozen exe.
- **Source inclusion:** Added `src` folder to datas for reliable relative imports in packaged exe.

### 🐛 Bug Fixes
- Fixed exe not creating logs directory on other machines.
- Fixed potential "No module named 'PySide6'" errors by removing unused PySide6 hidden imports.
- Fixed icon path resolution for frozen executables.

### 🎛️ UnRen Automation Improvements
- **Full automation:** Auto mode now runs both extract (1) and decompile (2) operations sequentially.
- **Timeout protection:** Added 5-minute timeout to prevent automation from hanging indefinitely.
- **Better batch handling:** Uses `cmd.exe /c` for more reliable stdin pipe handling with batch files.
- **Process cleanup:** Properly terminates stuck UnRen processes instead of leaving orphan windows.

## [2.0.7] - 2025-11-27

### 🧠 Parser & Extraction
- **Context-aware parser core:** Rebuilt `src/core/parser.py` with an indentation-based context stack so dialogue, menus, screen text and inline Ren'Py helpers are classified with their structural metadata.
- **Multiline + extend handling:** Triple-quoted dialogue, narrator blocks and `extend` statements are now captured as a single entry with accurate line ranges, preventing duplicate/partial translations.
- **Placeholder preservation:** Placeholders such as `{color}` tags, `[player]` variables and interpolation markers are cached before translation and re-applied after, reducing accidental corruption during MT runs.
- **Structured entry output:** Downstream consumers now receive `text`, `processed_text`, `context_path`, `text_type`, `character` and `placeholder_map`, unlocking smarter filtering and future glossary tooling.

### 🎛️ UnRen Automation & UX
- **UnRen Mode dialog:** Added `UnRenModeDialog` that guides users through automatic vs manual UnRen runs with localized descriptions.
- **Automation script:** `_build_unren_auto_script()` now sends a deterministic command sequence (decompile option → no overwrite → exit) so unattended runs just work.
- **Embedded logging:** Automatic runs capture stdout and present completion feedback inside the GUI instead of leaving users guessing.
- **UnRen re-download tooling:** `Tools → Redownload UnRen` forces a fresh package fetch when corruption or updates are detected.
- **Info dialog update:** The multi-page Info Center now ships with an UnRen tab explaining when/why to use automatic vs manual flows.
- **Version chooser guidance:** Help → Info → UnRen now tells users exactly when to launch `UnRen-current.bat` versus `UnRen-legacy.bat`, synchronized across English and Turkish locales.

### 🌍 Localization
- **Turkic language detection:** `detect_system_language()` now treats Turkish plus Azeri, Kazakh, Uzbek, Kyrgyz, Turkmen, Tatar (and similar locales) as “Turkish UI” defaults, while other systems stay English.
- **README refresh:** Both English and Turkish READMEs were rewritten to cover the new UnRen workflow, Info Center, and language defaults.

### 🧪 Regression Safety
- **Legacy compatibility shim:** `extract_translatable_text()` still exposes the historical `Set[str]` interface so existing tests/scripts continue to work while the GUI migrates to structured entries.
- **Logging & diagnostics:** Parser errors now include file and block context, making it easier to triage problematic `.rpy` files reported by users.

## [2.0.6] - 2025-11-26

### 🎨 UI Simplification & UX
- **Minimal main window:** Simplified the main screen to only show project folder selection, basic translation settings and a progress section so new users are not overwhelmed.
- **Removed results/log tabs:** The old right-hand panel with `Translation Results`, `Extracted Texts` and log tabs has been removed; extracted texts are now written to simple `.txt` reports under `logs/`.
- **Settings-only advanced options:** Advanced performance, proxy and logging options are now managed exclusively via the `Settings` dialog instead of the main window.
- **Window size cleanup:** Removed window size persistence and the related controls in Settings; the app now opens with a sane default size instead of reusing previous large/fullscreen sizes.

### 🌐 Glossary, Proxy & Localization
- **Glossary editor dialog:** Added a dedicated `Glossary` menu entry and dialog to edit `glossary.json` (term → preferred translation) with immediate in-memory update.
- **Config‑driven proxy manager:** Proxy behaviour is now fully driven by `Proxy` settings (enable/disable, failure limit, update interval and startup testing) instead of hardcoded values.
- **Custom proxy list support:** You can now define your own proxy list in the `Proxy` tab; these entries are parsed and preferred over public proxy sources.
- **Locale updates:** Updated English and Turkish locale files to match the new minimal UI and removed obsolete Quick Options/OPUS-MT related strings.
 - **Expanded translation language list:** Greatly extended the supported source/target languages (Czech, Romanian, Hungarian, Greek, Bulgarian, Ukrainian, Indonesian, Malay, Hebrew and more) via `get_supported_languages`, so most major world languages can now be selected.

### 📚 Documentation
- **README refresh:** Updated both `README.md` and `README.tr.md` to describe the minimal main window, current theme options and the separate Settings dialog.

## [2.0.5] - 2025-09-16

### 🧹 Removal: Deep-Translator
- **Removed Deep-Translator:** The experimental `Deep-Translator` multi-engine wrapper and its UI entry have been removed due to stability and maintenance reasons. If you relied on this engine, please switch to supported engines (Google, DeepL, Yandex, LibreTranslator).

### 🧹 Removal: OPUS-MT (Argos Translate)
- **Removed OPUS-MT (Argos Translate):** All OPUS-MT / Argos Translate integration, model download UI, and related code paths have been removed due to instability and crashes observed in production. Offline model download/dialog features related to OPUS-MT were deleted, and references in UI/locales/docs were cleaned up.

## [2.0.4] - 2025-09-15

### 🛠️ RenPy Compliance & Cleanup
- **Config Cleanup:** Only `config.py` is now active; `config_new.py` and `config_old.py` have been completely removed.
- **Default Format:** The default translation output format is now `old_new`. The `simple` format remains as an optional legacy mode.
- **Format Compliance:** The `old_new` format is now fully compliant with RenPy documentation. All translations are grouped in a single `translate [lang] strings:` block, with each entry as `old "..."` and `new "..."`, and file/directory structure matches RenPy standards.
- **Language Init File:** The automatic language initializer file (e.g. `a0_pt_language.rpy`) is now minimal: only `define config.language = "[lang]"` is used for automatic language selection. All complex init/python blocks have been removed.
- **Bug Fixes:** Fixed quote and newline issues in language init file generation; output is now error-free.
- **Code & Documentation:** All relevant code sections and README/BUILD.md have been reviewed and updated for RenPy compliance and accuracy.
- **User Feedback:** Language initialization issues (e.g. for Portuguese) are resolved; automatic language selection now works for all languages.

## [2.0.3] - 2025-09-15

### 🔧 Build & Packaging Improvements

### 🛠️ GitHub Repository Preparation

### 🐛 Minor Fixes

### 📦 Distribution Ready

## [2.0.2] - 2025-09-15

### 🚀 New Translation Engine
- **Complete UI Translation**: All interface elements now support English and Turkish
- **Dynamic Language Switching**: Real-time language switching without restart
- **Translation Engine Names**: Engine dropdown now adapts to selected UI language
- **Model Download Dialog**: Full multi-language support for offline model downloads

### 🔧 Architecture Improvements
- **Batch Translation Optimization**: Pre-check model availability before processing thousands of texts
- **Signal-Based Download Workflow**: Clean separation between translation worker and GUI dialogs
- **Error Prevention**: Eliminated infinite loop errors from missing models
- **Memory Management**: Efficient model caching and loading system

### 🐛 Critical Fixes
- Fixed OPUS-MT model download infinite loop that caused application crashes
- Resolved Qt thread safety issues with dialog creation
- Improved error handling for missing translation models
- Better fallback mechanisms when models are unavailable

### 📚 Documentation & GitHub Preparation
- Updated README.md with OPUS-MT information and installation instructions
- Enhanced .gitignore for better repository management
- Cleaned up debug prints and improved code quality
- Added GitHub community files (CODE_OF_CONDUCT.md, issue templates, PR template)

## [2.0.1] - 2025-09-11

### 🎯 RenPy Integration Overhaul
- **Conditional Menu Support**: Perfect handling of `"choice" if condition:` syntax
- **Technical String Filtering**: Automatically excludes color codes (#08f), font files (.ttf), performance metrics
- **Correct Output Format**: Individual `translate strings` blocks (RenPy standard compliance)
- **Modern Language Initialization**: Compatible language setup without deprecated APIs
- **Encoding Fixes**: Proper UTF-8 handling for all international characters

### 🔧 Parser Improvements
- **Enhanced Regex Engine**: Improved extraction of conditional menu choices
- **Smart Content Detection**: Better filtering of meaningful vs technical content
- **Multi-line String Handling**: Fixed parsing issues with complex string patterns
- **Variable Preservation**: Maintains `[character_name]` and placeholder integrity

### 🐛 Critical Bug Fixes
- Fixed "Could not parse string" errors in RenPy
- Resolved multi-line string parsing issues (line 2327 type errors)
- Corrected character encoding problems (Türkçe character corruption)
- Fixed language initialization file compatibility issues
- Eliminated technical string translation (fps, renderer, etc.)

### 📦 Quality Improvements
- **Cache Management**: Built-in RenPy cache clearing functionality
- **Error Prevention**: Proactive filtering prevents RenPy parse errors
- **Output Validation**: Ensures all generated files are RenPy-compatible
- **Real-world Testing**: Validated with actual RenPy visual novel projects

### 📦 Distribution Ready
- **Clean Repository**: Removed all temporary test and debug files
- **Professional Documentation**: Updated README, added CONTRIBUTING.md, RELEASE_NOTES.md
- **Example Configuration**: Sample config.json.example for users
- **GitHub Ready**: Proper .gitignore, structured for open source collaboration

### 🧪 Testing & Validation
- Comprehensive testing with Secret Obsessions 0.11 (RenPy 8.3.2)
- Menu choice translation validation
- Technical string exclusion verification
- Encoding and character preservation testing

## [2.0.0] - Previous Release
- Initial stable release with core translation functionality
- Basic RenPy file parsing and translation
- Multi-engine support (Google, DeepL, Bing, Yandex)
- Professional UI with theme support
