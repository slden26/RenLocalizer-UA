# RenLocalizer

RenLocalizer is an advanced, cross-platform tool for unpacking, parsing, and translating Ren'Py visual novels. It features a guided UnRen workflow, multi-engine translation, context-aware parsing, and supports both GUI and CLI modes.

> ⚠️ This project is actively developed and assisted by AI. Expect frequent updates and improvements.

## 🚀 Key Features (v2.3.1)

### Translation
- **Multi-Engine Translation:** Google Translate (web) and DeepL API with automatic fallback
- **Lingva Fallback:** Free fallback translation when Google endpoints fail
- **Parallel Endpoints:** Multiple Google mirrors for faster, more reliable translation
- **Batch Processing:** Configurable batch size, concurrent requests, and character limits
- **Proxy Support:** Rotation and adaptive concurrency for rate limiting

### Parsing
- **Context-Aware Parser:** Handles dialogue, menu, screen, python blocks, and triple-quoted monologues
- **RPYC/RPYMC Support:** SDK-free AST reader for compiled .rpyc and .rpymc files
- **Placeholder Safety:** Ren'Py variables (`[var]`), tags (`{tag}`), and special markers are always protected
- **Deep Scan:** Finds hidden strings in init python blocks and variable assignments

### Output
- **Ren'Py Compliant:** Generates `translate strings` blocks with old/new format
- **Language Init:** Automatic `define config.language` file generation
- **Stable IDs:** Context-aware translation IDs for consistent updates

### Interface
- **GUI:** Modern dark/solarized themes with drag-and-drop support
- **CLI:** Interactive menu mode and direct command-line arguments
- **Cross-Platform:** GUI on Windows, CLI on Windows/Mac/Linux

## ⚠️ Known Limitations

- Translation coverage varies by game (typically 80-100% for visual novels)
- Complex sandbox games may have untranslated parts (quests, skills, inventory) due to:
  - Encrypted .rpymc files or custom data structures
  - Dynamically generated text
- UnRen (decompilation) only works on Windows

## 🛠️ Installation

```bash
git clone https://github.com/Lord0fTurk/RenLocalizer.git
cd RenLocalizer
python -m venv venv
venv\Scripts\activate   # Windows
# or: source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

## ⚡ Quick Start (GUI)

```bash
python run.py
```

1. Select your Ren'Py game folder or EXE
2. Choose UnRen mode if prompted (Windows only)
3. Select source/target language and translation engine
4. Adjust batch/concurrency settings if needed
5. Start translation → outputs in `game/tl/<lang>/`

## 💻 CLI Usage (All Platforms)

### Interactive Mode
```bash
python run_cli.py
```

Opens a menu-driven interface with options for:
- Full Translation (Game EXE/Project)
- Translate Existing TL Folder
- Settings configuration

### Direct Mode
```bash
# Translate a game project
python run_cli.py "/path/to/game" --target-lang tr --mode auto

# Translate existing TL folder
python run_cli.py "/path/to/game/tl/turkish" --mode translate --target-lang tr

# Use DeepL engine
python run_cli.py "/path/to/game" --target-lang de --engine deepl

# Show all options
python run_cli.py --help
```

### CLI Options
| Option | Default | Description |
|--------|---------|-------------|
| `--target-lang`, `-t` | `tr` | Target language code |
| `--source-lang`, `-s` | `auto` | Source language (auto-detect) |
| `--engine`, `-e` | `google` | Translation engine (google/deepl) |
| `--mode` | `auto` | Mode: auto, full, translate |
| `--config` | - | JSON config file for advanced settings |
| `--proxy` | off | Enable proxy rotation |
| `--verbose`, `-v` | off | Enable debug logging |
| `--interactive`, `-i` | - | Force interactive menu |

**Note:** On Mac/Linux, `full` mode (UnRen) is not available. Use `--mode translate` with pre-extracted files.

See [docs/CLI_USAGE.md](docs/CLI_USAGE.md) for detailed documentation.

## ⚙️ Configuration

### GUI Settings
- Threads: 1–256
- Batch size: 1–2000
- Request delay and retries
- Proxy with rotation and failure limits
- Theme selection (dark/solarized)

### Config File (CLI)
Create a JSON file to override settings:
```json
{
  "translation_settings": {
    "max_concurrent_threads": 64,
    "max_batch_size": 500,
    "translate_dialogue": true,
    "translate_menu": true
  }
}
```
Use with: `python run_cli.py /path --config my_config.json`

## 🤝 Contributing

PRs welcome for:
- New translation engines
- Performance improvements
- Language support
- UI/UX enhancements

### Troubleshooting
- **`src` not found:** Run from repo root or set `PYTHONPATH`
- **Slow/blocked:** Tune threads/batch/delay, enable proxy
- **Mac/Linux issues:** Use CLI with `--mode translate`

## 📄 License

GPL-3.0-or-later (see [LICENSE](LICENSE))
