# Contributing to EdikteFinder-Analyzer

Thank you for your interest in contributing! This document explains how to get started.

## Ways to Contribute

- **Bug reports** – use the GitHub Issue template
- **Feature requests** – open a discussion or issue
- **Code contributions** – open a pull request
- **Documentation** – improve the README, docstrings, or add wiki pages
- **Scraper improvements** – the Austrian Edikt portal changes occasionally; field-mapping fixes are very welcome

## Development Setup

```bash
# 1. Clone the repo
git clone https://github.com/JakOb-dotcom/EdikteFinder-Analyzer.git
cd EdikteFinder-Analyzer

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 4. Copy the settings template and add your API keys
copy data\jsons\settings.example.json data\jsons\settings.json
# Then edit data/jsons/settings.json with your credentials
```

## Code Style

- **Python 3.11+** compatible (no walrus operators beyond 3.8 scope, type hints encouraged)
- Follow the existing module structure: scraper / storage / ai_analyzer / config / main
- Keep UI code in `main.py`, business logic separate
- New AI providers: add a `_provider()` async function in `ai_analyzer.py` and wire it into `analyze()` + the settings dialog

## Pull Request Guidelines

1. Fork the repository and create a branch: `git checkout -b feature/my-feature`
2. Make your changes with clear, focused commits
3. Run `python -c "import main, scraper, ai_analyzer, storage, config; print('OK')"` to verify imports
4. Open a pull request with a clear description of what you changed and why

## Sensitive Data

**Never commit:**
- `data/jsons/settings.json` (contains API keys)
- `data/jsons/edikte.json` / `analyses.json` (personal data)
- `data/downloads/` (PDF files)

All of the above are in `.gitignore`.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
