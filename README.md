> ⚠️ **Warning (English)**: This project has been assisted by AI. It may contain mistakes, incomplete implementations and is still under active development. It is NOT a final release.
> ⚠️ **Uyarı (Türkçe)**: Bu proje yapay zeka desteğiyle hazırlanmıştır; hatalar ve eksikler içerebilir, halen geliştirme aşamasındadır ve nihai sürüm değildir.

# RenLocalizer V2

[English] | [Türkçe README](./README.tr.md)

![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

**RenLocalizer V2** is a high-performance desktop application built to automatically translate Ren'Py visual novel (.rpy) files with multiple translation engines. It offers automatic proxy rotation, batch translation, smart filtering, and a modern interface.

## ✨ Features

### 🚀 High Performance
- **Implemented engines**: Google (web), DeepL (API)
- **Planned**: Bing (Microsoft), Yandex, LibreTranslator
- **Concurrent execution**: Up to 256 in UI (core currently ~32 active slots)
- **Batch translation**: Configurable up to 2000
- **Proxy rotation**: Multi-source + validation
- **Smart fallback**: Google path falls back to direct requests if proxy/aiohttp fails

### 🎨 Modern Interface
- **Professional themes**: Dark, Light, Solarized, Eye-friendly
- **Real-time monitoring**: Live speed, progress, status
- **Two language UI**: English & Turkish
- **Auto-save**: Timestamped output folders

### 🔧 Smart Processing
- **Intelligent parser**: Filters code parts, file paths, technical terms
- **Context preservation**: Character names & placeholders are preserved
- **Ren'Py tag support**: Keeps tags like {color}, {size}

### 🛡️ Reliability
- **Error capture**: Retry & logging
- **Rate limiting**: Engine-based adaptive delay
- **Proxy management**: Statistics of working proxies

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- Git (optional, you can also download as ZIP)
- pip (Python package manager)
- For Windows users: Visual Studio Build Tools with C++ support (for some dependencies)

### Steps

1. Get the code:
```bash
git clone https://github.com/kullanici/RenLocalizer-V2.git
cd RenLocalizer-V2
```

2. Create virtual environment (recommended):
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

3. Install requirements:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
# On Linux/macOS:
python run.py

# On Windows:
# Either double-click run.bat or use PowerShell:
```powershell
$env:PYTHONPATH="$(Get-Location)"; python run.py
```

## 🚀 Quick Start
1. Launch the app (`python run.py`)
2. Select the folder containing `.rpy` files
3. Select source & target language (e.g. EN → TR)
4. Configure engine & batch settings
5. Start translation – watch live progress
6. Translations auto-save (or you can save manually)

## ⚙️ Settings
- Concurrent threads (1–256)
- Batch size (1–2000)
- Request delay (0–5 s)
- Max retries
- Enable / disable proxy

## 🌍 Engine Status Table
| Engine | Status | Note |
|--------|--------|------|
| Google | ✅ Active | Web client + proxy fallback |
| DeepL | ✅ Active | API key required only if you use it |
| Bing / Microsoft | ⏳ Planned | Not yet added |
| Yandex | ⏳ Planned | Not yet added |
| LibreTranslator | ⏳ Planned | Future self-host option |

## 🧠 Parsing Logic
- Excludes code blocks, label definitions, python blocks
- Only real dialogue & user-visible strings extracted
- File paths, variables, `%s`, `{name}` etc. preserved

## 📁 Project Structure
```
src/
	core/ (translation, parser, proxy)
	gui/  (interface & themes)
	utils/ (config)
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
**RenLocalizer V2** – Professional translation accelerator for Ren'Py projects.
