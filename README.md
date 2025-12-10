> ⚠️ **Warning (English)**: This project has been assisted by AI. It may contain mistakes, incomplete implementations and is still under active development. It is NOT a final release.

# RenLocalizer

**RenLocalizer** is a modern desktop application built to unpack, decompile and translate Ren'Py visual novel (.rpy) files with high accuracy and performance. It now includes a guided UnRen workflow (automatic or manual), multi-engine translation, smart text filtering and a professional bilingual interface.

## ✨ Key Features

### 🎯 Smart Translation
- **Multiple engines**: Google Translate (web), DeepL API, Deep-Translator (multi-engine) support
- **Context-aware parser**: Indentation-based block tracking distinguishes dialogue, menus, screen/UI text and Ren'Py helper calls with metadata
- **Structured extraction**: Each text now ships with `text`, `processed_text`, `context_path`, `text_type`, `character` and `placeholder_map` fields for smarter filtering
- **Conditional menu support**: Handles `"choice" if condition:` syntax
- **Technical filtering**: Automatically excludes color codes, font files, performance metrics
- **Placeholder pipeline**: Parser caches `{color}`, `[player]`, `{variable}` placeholders ahead of MT and restores them afterwards
- **Offline translation**: Offline engines may be available via third-party packages (optional)

### 🚀 High Performance  
- **Concurrent processing**: Configurable thread count (1-256)
- **Batch translation**: Process multiple texts together (1-2000)
- **Proxy rotation**: Automatic proxy management and validation
- **Config-driven behaviour**: Proxy update interval, failure limits and startup tests are now fully controlled from the `Proxy` tab in Settings.
- **Smart fallback**: Falls back to direct requests if proxies fail
- **Rate limiting**: Adaptive delays to prevent blocking

### 🎨 Modern Interface
- **Professional themes**: Dark and Solarized themes
- **Minimal main screen**: Only folder selection, basic translation settings and progress bar
- **Dedicated Info Center**: `Help → Info` now includes UnRen quick reference, troubleshooting steps and workflow tips
- **Separate settings dialog**: Advanced performance / proxy / logging options in the `Settings` menu
- **Bilingual UI**: English and Turkish interface support with automatic system-language detection (Turkic locales open in Turkish by default)
- **Auto-save**: Timestamped output with proper Ren'Py structure

### 🧰 UnRen Workflow
- **Embedded UnRen launcher**: Download, cache and launch Lurmel's UnRen-forall scripts directly from the app (Windows)
- **Automatic vs manual choice**: New UnRen Mode dialog asks whether to run a hands-off decompile pass or open UnRen in a console window
- **Automation script**: Automatic mode now sends only the menu option `2` (decompile `.rpyc` → `.rpy`), skips long archive extraction, shows a modal progress bar, and displays a reminder to re-select the folder if no texts appear afterwards
- **Project hints**: When `.rpyc/.rpa` files are detected, the app offers to run UnRen for you and links to the info tab for guidance

### 🔧 RenPy Integration
- **Correct format output**: Individual `translate strings` blocks as required by RenPy
- **Language initialization**: Automatic language setup files
- **Cache management**: Built-in RenPy cache clearing
- **Directory structure**: Proper `game/tl/[language]/` organization

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- Git (optional, you can also download as ZIP)
- pip (Python package manager)
- For Windows users: Visual Studio Build Tools with C++ support (for some dependencies)

### Steps

1. **Clone the repository:**
```bash
git clone https://github.com/YOUR_USERNAME/RenLocalizer.git
cd RenLocalizer
```

2. **Create virtual environment (recommended):**
```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On Linux/macOS:
source venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Run the application:**
```bash
python run.py
```

Or on Windows, you can double-click `run.bat`

## 🚀 Quick Start
1. Launch the app (`python run.py`)
2. Select the folder containing your Ren'Py project
3. If prompted, choose whether to run UnRen automatically or manually (Windows only). Automatic mode performs a quick `.rpyc` → `.rpy` decompile and shows a progress dialog until it finishes
4. Select source & target language (e.g. EN → TR)
5. Configure engine & batch settings
6. Start translation – watch live progress
7. Translations auto-save (or you can save manually)

### Automatic vs Manual UnRen
| Mode | When to use | What happens |
|------|-------------|--------------|
| **Automatic** | You prefer a hands-off workflow with recommended defaults | RenLocalizer feeds UnRen only menu option `2` (decompile `.rpyc` into `.rpy`), shows a blocking progress dialog, and pops up a reminder to re-select the folder if text parsing still says "No texts found". |
| **Manual** | You want to pick specific menu items or use experimental UnRen modes | A separate console opens with UnRen so you can interact with it directly. |

You can re-launch UnRen anytime via `Tools → Run UnRen` or force a re-download of the package via `Tools → Redownload UnRen`.

## ⚙️ Settings
- Concurrent threads (1–256)
- Batch size (1–2000)
- Request delay (0–5 s)
- Max retries
- Enable / disable proxy
- Proxy failure limit, update interval and custom proxy list (one per line)

### 🌍 Language Support
- Auto-detect source language
- UI language now auto-detects the operating system locale: English systems start in English; Turkish and other Turkic locales (Azerbaijani, Kazakh, Uzbek, etc.) start in Turkish
- Extended source/target language list covering most major world languages
- Recent additions include Czech, Romanian, Hungarian, Greek, Bulgarian, Ukrainian, Indonesian, Malay and Hebrew

## 🌍 Engine Status Table
| Engine | Status | Languages | Note |
|--------|--------|-----------|------|
| Google | ✅ Active | 100+ | Web client + proxy fallback |
| DeepL | ✅ Active | 30+ | API key required only if you use it |
| OPUS-MT | ❌ Removed | - | Offline OPUS-MT removed due to native dependency issues |
| Deep-Translator | ✅ Active | 100+ | Multi-engine wrapper (Google, Bing, Yandex, etc.) |
| Bing / Microsoft | ⏳ Planned | - | Not yet added |
| Yandex | ⏳ Planned | - | Not yet added |
| LibreTranslator | ⏳ Planned | - | Future self-host option |

### Offline Engines
Offline engines may support a variable set of language pairs depending on installed packages.

## 🧠 Parsing Logic
- Tracks indentation-based contexts so `label`, `menu`, `screen` and `python` scopes are respected
- Multi-line dialogue, narrator blocks and `extend` statements are captured as a single entry with original line range
- Excludes technical code, label definitions and Python blocks while retaining user-facing strings
- Emits structured entries with context path + type hints to drive translation decisions and UI previews
- Placeholder preservation happens at parse time, ensuring `%s`, `{name}`, `{color}` or `[player]` tokens survive machine translation intact

## 📁 Project Structure
```
src/
	core/ (translation, parser, proxy)
	gui/  (interface, themes, dialogs)
	utils/ (config, UnRen manager)
docs/ (detailed walkthroughs)
run.py (launcher)
README.md / README.tr.md
LICENSE
```

## 🔐 API Keys
Currently only DeepL key meaningful; others activate when engines arrive.

## 📦 Building Executable
See `BUILD.md` for detailed instructions on creating standalone executables.

## 🧪 Test & Contribute
Pull Requests welcome. Suggested improvements:
- New engine integration
- Performance optimization
- Additional language support
- UI improvements

## ❓ Troubleshooting
| Problem | Solution |
|---------|----------|
| Module not found 'src' | Set `PYTHONPATH` or run from root |
| Slow translation | Increase threads & batch, lower delay |
| Rate limit | Enable proxy or change engine |
| Broken tag | Ensure placeholder protection enabled |

## 📄 License
This project is licensed under **GPL-3.0-or-later**. See `LICENSE`.

## 💬 Contact
Open an issue or contribute. Community contributions welcome.

---
**RenLocalizer v2.2.5** – Professional translation accelerator for Ren'Py projects.
