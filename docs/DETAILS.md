# RenLocalizer V2 – Full Documentation

This file contains the extended English documentation that was previously in README.md.

## 1. Features (Detailed)
- Implemented Engines: Google (web), DeepL (API)
- Planned: Bing (Microsoft), Yandex, LibreTranslator (self-host)
- Concurrency: UI up to 256 (internal active cap ~32 per engine)
- Batch Size: Up to 2000
- Proxy Rotation: Multi-source harvesting + health scoring + disable toggle
- Fallback Logic: Google path falls back to direct requests if proxy/aiohttp fails
- Auto-save: Timestamped directory output
- Parser: Context-aware, indentation-driven extractor with placeholder caching and structured metadata output

## 2. Engine Status Matrix
| Engine | Status | Notes |
|--------|--------|-------|
| Google | Implemented | Web client with multi-endpoint support; optional proxy + direct fallback |
| DeepL  | Implemented | API key required |
| Yandex | Implemented | Web client; free |
| Bing / Microsoft | Planned | Not implemented yet |
| LibreTranslator | Planned | Self-host (future) |

## 3. Installation
```bash
git clone https://github.com/your-username/renlocalizer-v2.git
cd renlocalizer-v2
pip install -r requirements.txt
python run.py
```
Virtual env (recommended):
```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
pip install -r requirements.txt
python run.py
```

## 4. Quick Start
1. Open app `python run.py`
2. Select folder with .rpy files
3. Choose target language
4. Select engine
5. Start translation & monitor
6. Save or let auto-save handle

## 5. Configuration Example (config.json)
```json
{
  "translation_settings": {
    "source_language": "auto",
    "target_language": "tr",
    "max_concurrent_threads": 32,
    "max_batch_size": 100,
    "request_delay": 0.1,
    "max_retries": 3,
    "timeout": 30
  }
}
```

## 6. Logging
Logs stored in `logs/` (general + errors). Levels: DEBUG..CRITICAL.

## 7. API Keys
Only DeepL currently meaningful. Future engines will use existing key UI placeholders.

## 8. Parser Architecture Primer

- **Context stack**: Each Ren'Py block (`label`, `menu`, `screen`, `init python`, etc.) pushes a node with indent info so nested scopes are recognised.
- **Pattern registry**: Dialogue, narrator lines, menu options, UI strings and Ren'Py helper calls are matched via regex descriptors that also assign a `text_type`.
- **Multiline handling**: Triple-quoted dialogue and `extend` segments are consumed until the closing delimiter, producing a single coherent entry.
- **Structured entry**: Every match yields `text`, `processed_text`, `text_type`, `context_line`, `context_path`, `character`, `line_number` and a `placeholder_map`.
- **Placeholder lifecycle**: Parser replaces `{color}` tags, `[player]` variables, `%s` markers and `{fstring}` placeholders with stable tokens up front; the translation worker later restores them.
- **Legacy shim**: `extract_translatable_text()` still returns `Set[str]` so older tooling can coexist during migration.

## 9. Contribution Guide (Summary)
1. Fork & branch
2. Implement & add tests
3. Format with black/flake8
4. Submit PR

## 10. Troubleshooting (Common)
| Issue | Cause | Fix |
|-------|-------|-----|
| No texts found | Parser filtered everything | Check files have dialogue |
| Proxy errors | Dead proxies | Disable proxy or refresh list |
| Slow speed | Too few threads | Increase threads / reduce delay |
| Rate limit | Too aggressive | Lower concurrency |

## 11. License
GPL-3.0-or-later.

## 12. Roadmap (Short)
- Add Bing/Yandex engines
- LibreTranslator self-host mode
- In-app translation memory / glossary
- CLI mode

---
This condensed structure keeps README.md short while preserving full docs here.
