# Contributing to RenLocalizer

Thank you for your interest in contributing to RenLocalizer! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Development Environment
1. Fork the repository
2. Clone your fork locally
3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running Tests
```bash
# Run the application in development mode
python run.py

# Test with sample RenPy files
# Place test .rpy files in a test directory and use the GUI
```

## 📝 Code Style

### Python Guidelines
- Follow PEP 8 standards
- Use type hints where appropriate
- Add docstrings to functions and classes
- Keep functions focused and small
- Use meaningful variable names

### Example:
```python
def extract_translatable_text(self, file_path: Path) -> Set[str]:
    """Extract translatable text from a .rpy file.
    
    Args:
        file_path: Path to the .rpy file to parse
        
    Returns:
        Set of translatable strings found in the file
    """
    # Implementation here
```

## 🔧 Architecture

### Project Structure
```
src/
├── core/           # Core translation logic
│   ├── parser.py      # RenPy file parsing
│   ├── translator.py  # Translation engines
│   └── output_formatter.py  # Output generation
├── gui/            # User interface
│   ├── main_window.py # Main application window
│   └── themes.py      # UI themes and styling
└── utils/          # Utilities
    └── config.py      # Configuration management
```

### Key Components
- **Parser**: Extracts translatable text from RenPy files
- **Translator**: Handles communication with translation services
- **Output Formatter**: Generates properly formatted RenPy translation files
- **GUI**: Qt-based user interface with theming support

## 🐛 Bug Reports

When reporting bugs, please include:
- **Environment**: OS, Python version, dependency versions
- **Steps to reproduce**: Clear step-by-step instructions
- **Expected vs actual behavior**: What should happen vs what happens
- **Sample files**: If possible, include problematic .rpy files
- **Logs**: Any error messages or log files

### Bug Report Template
```markdown
**Environment:**
- OS: Windows 10 / Ubuntu 20.04 / macOS 12
- Python: 3.9.0
- RenLocalizer: 2.0.0

**Description:**
Brief description of the issue

**Steps to reproduce:**
1. Step one
2. Step two
3. Step three

**Expected behavior:**
What should happen

**Actual behavior:**
What actually happens

**Additional info:**
Any logs, screenshots, or sample files
```

## ✨ Feature Requests

For new features:
1. Check existing issues to avoid duplicates
2. Provide clear use case and motivation
3. Consider implementation complexity
4. Discuss with maintainers before starting large changes

### Priority Areas
- **New translation engines**: Bing, Yandex, LibreTranslate
- **RenPy feature support**: New syntax, advanced features
- **Performance improvements**: Faster parsing, better caching
- **UI enhancements**: Better themes, more languages
- **Quality improvements**: Better error handling, logging

## 🔀 Pull Requests

### Before Submitting
- Create a feature branch from `main`
- Test your changes thoroughly
- Update documentation if needed
- Follow the existing code style
- Write clear commit messages

### PR Guidelines
- **Title**: Clear, descriptive title
- **Description**: Explain what changes and why
- **Testing**: Describe how you tested the changes
- **Breaking changes**: Clearly mark any breaking changes

### Commit Message Format
```
type(scope): brief description

Longer explanation if needed

- Bullet points for details
- Reference issues: Fixes #123
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## 🔍 Code Review Process

1. **Automated checks**: Code will be checked for style and basic issues
2. **Manual review**: Maintainers will review functionality and design
3. **Testing**: Changes will be tested with various RenPy files
4. **Documentation**: Ensure docs are updated for user-facing changes

## 📚 Development Tips

### Working with RenPy Files
- Test with various RenPy syntax patterns
- Consider edge cases: nested quotes, multi-line strings
- Preserve game functionality after translation

### Translation Engine Integration
- Follow the existing translator interface
- Handle rate limiting and errors gracefully
- Add proper configuration options

### UI Development
- Use existing theme system for consistency
- Support both English and Turkish interfaces
- Test with different screen resolutions

## 🎯 Current Priorities

1. **Engine expansion**: Adding Bing, Yandex, LibreTranslate
2. **RenPy compatibility**: Support for newer RenPy features
3. **Performance**: Optimize for large projects
4. **Quality**: Better error handling and user feedback

## 📞 Community

- **Issues**: GitHub Issues for bugs and feature requests
- **Discussions**: GitHub Discussions for questions and ideas
- **Email**: For security issues or private matters

## 📄 License

By contributing to RenLocalizer, you agree that your contributions will be licensed under the GPL-3.0-or-later license.

---

Thank you for helping make RenLocalizer better! 🚀
