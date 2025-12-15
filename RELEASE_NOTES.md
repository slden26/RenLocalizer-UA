# Release Notes

## Version 2.2.8 - 2025-12-13

### 🚀 Major Changes
- All Google translation and batch system performance parameters (max characters, batch size, parallel requests) are now fully manageable from the UI.
- Expanded Google endpoint list for faster and more reliable parallel translation.
- Placeholder protection is now mandatory: Ren'Py variables, technical lines, and all special markers are never corrupted during translation.
- Automated tests for placeholder safety and improved error handling in the translation pipeline.
- Parser, pyparse grammar, and related modules have been thoroughly reviewed and optimized for reliability and coverage.
- Deep scan, rpyc reader, and extraction modules have been improved for stability and scope.

### ⚠️ Known Limitations & User Notes
- The program still cannot translate 100% of all texts. Translation rate varies by game. Visual Novels are almost fully translatable, but sandbox/complex games may have untranslated parts (quests, skills, inventory, menus, etc.) due to encrypted .rpymc files or custom data structures. Even with UnRen, these contents may not be accessible.
- The program is not yet advanced enough to fully translate such technical/gameplay content, and the developer's knowledge/experience is currently insufficient to overcome this limitation. Missing translations in advanced game systems, encrypted data, or custom menus are to be expected.
- For advanced translation and full coverage, please wait for future versions.

---

## Previous Releases

### 2.2.7 - 2025-12-12
- Major parser & grammar update: modular pyparsing, improved state machine, context-aware extraction, robust placeholder handling, and more.

### 2.0.6 - 2025-11-28
- UX improvements, faster UnRen automation, deterministic dialogs, and bug fixes.

### 2.0.1 - 2025-09-11
- RenPy-specific parsing, technical string filtering, improved output, better language initialization, and enhanced encoding support.

### 2.0.5 - 2025-09-15
- Removal of Deep-Translator and OPUS-MT (Argos Translate) for stability.