# EdikteFinder Analyzer

A desktop application for discovering, downloading, and AI-analyzing Austrian judicial real-estate auctions (*Gerichtsversteigerungen*) from [edikte.justiz.gv.at](https://edikte.justiz.gv.at).

> **⚠️ Legal Disclaimer:** This tool is for research purposes only. AI-generated analyses are **not** financial or investment advice. See [DISCLAIMER.md](DISCLAIMER.md) for the full disclaimer in English and German.

---

## Features

- **Automated scraping** – searches the Austrian Edikt portal using simple, Aktenzeichen, or extended search modes; enriches every result with full detail-page metadata
- **PDF download** – fetches the expert appraisal (Langgutachten) directly from the court portal
- **Multi-provider AI analysis** – sends the PDF text + Edikt metadata to your chosen AI and returns a structured investment assessment:
  - Investment score 1–10 (decimal)
  - Risk class & return potential
  - Up to 6 concrete opportunities and 6 risks
  - Market position, renovation cost estimate, detailed summary
- **Five AI providers** – OpenAI, Anthropic Claude, Google Gemini, xAI Grok, or a local Ollama model (free)
- **100 % local / serverless** – no database, no server, no cloud storage; all data lives in `data/jsons/` as plain JSON files
- **Dark-mode PyQt6 UI** – search panel, results table, detail panel, investment overview tab with KPIs

---

## Screenshots

> *(Add screenshots here after first run)*

---

## Requirements

| Dependency | Version |
|---|---|
| Python | ≥ 3.11 |
| PyQt6 | ≥ 6.7 |
| Playwright (Chromium) | ≥ 1.44 |
| pdfplumber | ≥ 0.11 |
| httpx | ≥ 0.27 |

AI provider libraries are optional – install only what you use:

| Provider | Package |
|---|---|
| OpenAI / Grok | `openai` |
| Anthropic | `anthropic` |
| Google Gemini | `google-genai` |
| Ollama | *(no extra package – uses httpx)* |

---

## Installation

```bash
# 1. Clone
git clone https://github.com/JakOb-dotcom/EdikteFinder-Analyzer.git
cd EdikteFinder-Analyzer

# 2. Virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install Playwright browser
playwright install chromium

# 5. Create your settings file from the template
copy data\jsons\settings.example.json data\jsons\settings.json
#   → then edit settings.json with your API keys (see Configuration below)
```

---

## Configuration

All settings are stored in `data/jsons/settings.json` (excluded from Git). You can also edit them through the app's **⚙ Einstellungen** dialog.

```json
{
  "ai_provider": "ollama",
  "openai_api_key": "sk-...",
  "openai_model": "gpt-4o-mini",
  "anthropic_api_key": "sk-ant-...",
  "anthropic_model": "claude-haiku-20240307",
  "gemini_api_key": "AIza...",
  "gemini_model": "gemini-2.0-flash",
  "grok_api_key": "xai-...",
  "grok_model": "grok-3-fast-beta",
  "ollama_base_url": "http://localhost:11434",
  "ollama_model": "llama3.2",
  "max_context_chars": 40000
}
```

**Tip for free local analysis:** Set `ai_provider` to `"ollama"` and run [Ollama](https://ollama.com) locally – no API keys, no costs. Recommended model: `qwen2.5:32b` or `llama3.2` for German-language documents.

---

## Usage

```bash
python main.py
```

1. **Search** – select a search mode (simple / Aktenzeichen / extended), fill in the filters, click **Suchen**. The app fetches all result detail pages automatically.
2. **Download** – select one or more entries and click **⬇ Gutachten laden** to download the expert appraisal PDF.
3. **Analyze** – click **✦ KI-Analyse** to send the PDF text to your configured AI provider. Results appear in the detail panel and the **Investitions-Übersicht** tab.

---

## Project Structure

```
EdikteFinder-Analyzer/
├── main.py            # PyQt6 UI – all windows, panels, worker threads
├── scraper.py         # Playwright scraper for edikte.justiz.gv.at
├── ai_analyzer.py     # AI backends (OpenAI, Anthropic, Gemini, Grok, Ollama) + PDF extraction
├── storage.py         # JSON-based persistence (edikte.json, analyses.json)
├── config.py          # Central config, loads/saves settings.json
├── requirements.txt   # Python dependencies
├── data/
│   ├── downloads/     # Downloaded PDFs (git-ignored)
│   └── jsons/
│       ├── settings.example.json   # Template – copy to settings.json
│       ├── settings.json           # Your settings with API keys (git-ignored)
│       ├── edikte.json             # Scraped Edikt data (git-ignored)
│       └── analyses.json           # AI analyses (git-ignored)
├── LICENSE
├── DISCLAIMER.md
└── CONTRIBUTING.md
```

---

## AI Provider Comparison

| Provider | Cost | Privacy | German quality | Best model |
|---|---|---|---|---|
| OpenAI | Pay-per-token | Cloud | ⭐⭐⭐⭐⭐ | `GPT-5` |
| Anthropic | Pay-per-token | Cloud | ⭐⭐⭐⭐⭐ | `Claude Sonnet 4.5` |
| Google Gemini | Pay-per-token (free tier available) | Cloud | ⭐⭐⭐⭐ | `Gemini3.0 Flash` |
| xAI Grok | Pay-per-token | Cloud | ⭐⭐⭐ | `Grok3` |
| Ollama (local) | **Free** | **100% local** | ⭐⭐ | `qwen2.5:32b` |
You can also try other models and easily change the model, just type in the model name and put in your API key, currently supported are all models from OpenAI, Anthropic, Google Gemini, xAI Grok and Ollama.
---

## Legal & Privacy

- This software accesses **publicly available** data from `edikte.justiz.gv.at`. No authentication is bypassed.
- **No personal data is collected** by the application. All scraped data stays on your local machine.
- PDF files downloaded from the portal are court documents in the public domain.
- **AI analyses are generated locally or via third-party APIs** at your own cost and responsibility.
- See [DISCLAIMER.md](DISCLAIMER.md) for the full legal disclaimer (English + German).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports and PRs are welcome!

---

## License

[MIT License](LICENSE) – © 2026 [JakOb-dotcom](https://github.com/JakOb-dotcom) & EdikteFinder-Analyzer Contributors
