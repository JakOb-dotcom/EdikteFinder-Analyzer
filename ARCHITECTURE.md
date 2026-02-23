# Architecture – EdikteFinder Analyzer

> This document is aimed at developers who want to understand, extend, or contribute to the project.  
> Last updated: February 2026

---

## Table of Contents

1. [High-Level Overview](#1-high-level-overview)
2. [Data Flow](#2-data-flow)
3. [Module Reference](#3-module-reference)
4. [Data Models](#4-data-models)
5. [AI Provider System](#5-ai-provider-system)
6. [Adding a New AI Provider](#6-adding-a-new-ai-provider)
7. [Extending the Scraper](#7-extending-the-scraper)
8. [UI Architecture](#8-ui-architecture)
9. [Configuration System](#9-configuration-system)
10. [Threading Model](#10-threading-model)
11. [Error Handling Strategy](#11-error-handling-strategy)
12. [Known Limitations & Future Work](#12-known-limitations--future-work)

---

## 1. High-Level Overview

EdikteFinder Analyzer is a **fully local, serverless PyQt6 desktop application**.  
There is no server, no database, and no cloud backend owned by this project.  
All data persists as plain JSON files in `data/jsons/`.

```
┌─────────────────────────────────────────────────────────────────┐
│                       Desktop Application                       │
│                                                                 │
│  ┌──────────┐   ┌─────────────┐   ┌──────────────────────────┐ │
│  │  main.py │   │  scraper.py │   │     ai_analyzer.py       │ │
│  │  (PyQt6) │──▶│ (Playwright)│   │ (OpenAI / Anthropic /    │ │
│  │          │   │             │   │  Gemini / Grok / Ollama) │ │
│  └────┬─────┘   └──────┬──────┘   └──────────┬───────────────┘ │
│       │                │                      │                 │
│       ▼                ▼                      ▼                 │
│  ┌──────────┐   ┌─────────────┐   ┌──────────────────────────┐ │
│  │config.py │   │ storage.py  │   │   data/ (JSON + PDFs)    │ │
│  │(settings)│   │ (JSON CRUD) │   │  edikte.json             │ │
│  └──────────┘   └─────────────┘   │  analyses.json           │ │
│                                   │  settings.json           │ │
│                                   │  downloads/*.pdf         │ │
│                                   └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
         │                   │                    │
         ▼                   ▼                    ▼
  edikte.justiz.gv.at   Court PDFs        AI Provider APIs
  (Austrian court portal) (public domain) (user's own API keys)
```

---

## 2. Data Flow

### 2.1 Search & Scrape

```
User fills search form
        │
        ▼
MainWindow._do_search()
        │  spawns Worker thread
        ▼
EdikteScraper.search(params)
  ├─ _fill_search_form()   → navigates edikte.justiz.gv.at
  ├─ _collect_results()    → parses DataTables result table
  │    └─ _parse_result_rows()  → basic row: titel, url, adresse
  └─ for each result:
       detail_page.goto(detail_url)
       _parse_detail()     → enriches: aktenzeichen, gericht,
                              versteigerung, mindestgebot,
                              kundmachung, objektgröße, …
        │
        ▼
storage.save_edikte_bulk()   → upsert into edikte.json (by detail_url)
        │
        ▼
EdikteModel.load()           → refreshes table in UI
```

### 2.2 PDF Download

```
User clicks "⬇ Gutachten laden"
        │
        ▼
MainWindow._do_download([edikt_id, …])
        │  spawns Worker thread
        ▼
EdikteScraper.download_gutachten(detail_url, edikt_id)
  └─ _download_pdf()
       ├─ tries Playwright download (click PDF link)
       └─ falls back to httpx GET if click fails
        │
        ▼
Saved as  data/downloads/gutachten_{edikt_id}.pdf
        │
        ▼
ai_analyzer.extract_pdf_text()   → text preview stored on edikt
storage.update_edikt_field(status="downloaded")
```

### 2.3 AI Analysis

```
User clicks "✦ KI-Analyse"
        │
        ▼
MainWindow._do_analyze([edikt_id, …])
        │  spawns Worker thread
        ▼
for each edikt_id:
  ai_analyzer.extract_pdf_text(pdf_path)
        │
        ▼
  ai_analyzer.smart_truncate(text)
    └─ intro (30%) + _extract_value_section (25%) + conclusion (45%)
        │
        ▼
  ANALYSIS_PROMPT.format(text, aktenzeichen, gericht, versteigerung, mindestgebot)
        │
        ▼
  ai_analyzer.analyze(text, edikt_meta, provider)
    ├─ _openai()     → openai.AsyncOpenAI
    ├─ _anthropic()  → anthropic.AsyncAnthropic
    ├─ _gemini()     → google.genai.Client (async)
    ├─ _grok()       → openai.AsyncOpenAI @ api.x.ai/v1
    └─ _ollama()     → httpx POST /api/chat
        │
        ▼
  _parse_json(raw_response)
    ├─ strips markdown fences
    ├─ coerces investitions_score → float
    ├─ null-guards: baujahr → "unbekannt", verkehrswert → "nicht ermittelbar"
    └─ ensures chancen/risiken are lists
        │
        ▼
  storage.save_analysis(edikt_id, result)
  storage.update_edikt_field(status="analyzed")
        │
        ▼
DetailPanel.show_edikt()  → renders result in UI
OverviewTab.refresh()     → updates KPI cards + table
```

---

## 3. Module Reference

### `main.py` — UI (PyQt6)

| Class / Function | Purpose |
|---|---|
| `MainWindow` | Application shell: toolbar, tabs, status bar |
| `Worker(QThread)` | Runs a single `async` coroutine in a new event loop; emits `finished`/`error` |
| `EdikteModel` | `QAbstractTableModel` — displays `edikte.json` in the results table |
| `OverviewModel` | `QAbstractTableModel` — displays all analyzed edikte with color-coded KPIs |
| `SettingsDialog` | Scrollable dialog for editing all AI provider settings |
| `DetailPanel` | Right-side panel: shows Edikt metadata + full AI analysis for selected row |
| `OverviewTab` | Tab with KPI cards + full overview table |
| `DARK_STYLE` | One global Qt stylesheet (dark color theme) |
| `EMPFEHLUNG_COLORS` | Shared color mapping used by both models and detail panel |

### `scraper.py` — Web Scraping (Playwright)

| Class / Function | Purpose |
|---|---|
| `EdikteScraper` | Async context manager; owns one Playwright `Browser` instance |
| `search(params)` | Full search + detail-page enrichment pipeline |
| `fetch_detail(url)` | Scrape a single detail page |
| `download_gutachten(url, id)` | Download PDF to `data/downloads/` |
| `_fill_search_form()` | Dispatches to `_fill_einfach`, `_fill_aktenzeichen`, `_fill_erweitert` |
| `_parse_result_rows()` | Extracts rows from DataTables table (`#DataTables_Table_0`) |
| `_parse_result_rows_fallback()` | Generic `<table>` parser when DataTables is absent |
| `_parse_detail()` | Regex-based field extraction from detail page body text |
| `_download_pdf()` | Tries 10 PDF link selectors; falls back to `httpx` GET |
| `KATEGORIE_MAP` | UI label ↔ site POST value for property categories |
| `BUNDESLAND_MAP` | UI label ↔ site POST value for Austrian federal states |
| `GERICHT_MAP` | UI label ↔ site court code for `Ger` select field |

### `ai_analyzer.py` — AI Analysis

| Function | Purpose |
|---|---|
| `extract_pdf_text(path)` | pdfplumber (primary) → PyPDF2 (fallback) |
| `smart_truncate(text, max_chars)` | Keeps intro + value section + conclusion within token budget |
| `_extract_value_section(text, max_len)` | 3-tier: Verkehrswert keywords → Baujahr keywords → EUR fallback |
| `analyze(text, meta, provider)` | Dispatch to correct backend |
| `_openai()` / `_anthropic()` / `_gemini()` / `_grok()` / `_ollama()` | Provider-specific async API calls |
| `_parse_json(raw)` | Normalises AI response: strips markdown fences, null-guards, type coercion |
| `make_summary(text)` | Lightweight extractive summary for DB preview (no AI call) |
| `SYSTEM_PROMPT` | Persona + JSON-only output instruction |
| `ANALYSIS_PROMPT` | Full extraction template with `=== EXTRAKTIONSREGELN ===` block |

### `storage.py` — Persistence

| Function | Purpose |
|---|---|
| `load_all_edikte()` | Returns `list[dict]` from `edikte.json` |
| `save_edikt(edikt)` | Upsert by `detail_url`; returns `edikt_id` (8-char UUID) |
| `save_edikte_bulk(list)` | Sequential upserts; returns list of IDs |
| `get_edikt(id)` | Lookup by `id` field |
| `update_edikt_field(id, **kwargs)` | Patch one or more fields without re-reading the whole model |
| `delete_edikt(id)` | Removes edikt + its analysis |
| `load_all_analyses()` | Returns `dict` keyed by `edikt_id` |
| `save_analysis(edikt_id, analysis)` | Upserts analysis; adds `analyzed_at` timestamp |
| `get_analysis(edikt_id)` | Single lookup |
| `pdf_path_for(edikt_id)` | Canonical PDF path (`downloads/gutachten_{id}.pdf`) |
| `has_pdf(edikt_id)` | Checks file existence |
| `get_stats()` | Aggregated KPIs for `OverviewTab` |

### `config.py` — Configuration

| Symbol | Purpose |
|---|---|
| `BASE_DIR`, `DATA_DIR`, `JSONS_DIR`, `DOWNLOADS_DIR` | Path constants, auto-created on import |
| `EDIKTE_JSON`, `ANALYSES_JSON`, `SETTINGS_JSON` | File paths |
| `AI_PROVIDER`, `*_API_KEY`, `*_MODEL` | Module-level globals; overwritten by `apply_settings()` |
| `MAX_CONTEXT_CHARS` | Character budget for AI input (default 40,000) |
| `HEADLESS` | `True` = Playwright runs without browser window |
| `load_settings()` | Reads `settings.json` → `dict` |
| `save_settings(s)` | Writes `dict` → `settings.json` |
| `apply_settings()` | Syncs `settings.json` values into module globals |

---

## 4. Data Models

### Edikt (element of `edikte.json`)

```jsonc
{
  "id":            "a1b2c3d4",          // 8-char UUID, assigned on first save
  "detail_url":    "https://edikte.justiz.gv.at/...",  // deduplication key
  "titel":         "BG Döbling 3 E 27/24y – Einfamilienhaus",
  "aktenzeichen":  "3 E 27/24y",
  "gericht":       "BG Döbling",
  "veroeffentlicht": "15.01.2026",      // Kundmachungsdatum
  "letzte_aenderung": "18.01.2026",
  "versteigerung": "12.03.2026, 10:00 Uhr",
  "adresse":       "Musterstraße 12, 1190 Wien",
  "kategorien":    "Eigenheim",
  "mindestgebot":  "285.000 EUR",
  "schätzwert":    "350.000 EUR",
  "objektgröße":   "Wohnfläche 120 m²",
  "beschreibung":  "...",               // first 1000 chars of detail text
  "status":        "analyzed",          // scraped | downloaded | analyzed | analyze_error | no_pdf
  "pdf_text_preview": "...",            // first 500 chars of extracted PDF
  "created_at":    "2026-01-15T14:32:00",
  "updated_at":    "2026-01-15T15:10:00"
}
```

### Analysis (value in `analyses.json`, keyed by `edikt_id`)

```jsonc
{
  "edikt_id":         "a1b2c3d4",
  "analyzed_at":      "2026-01-15T15:10:00",
  "provider":         "gemini",
  "model":            "gemini-2.0-flash",
  "tokens_used":      3840,

  // AI-extracted fields
  "objekt_art":       "Einfamilienhaus",
  "flaeche":          "Wohnfläche 120 m², Grundstück 350 m²",
  "baujahr":          "ca. 1970er",
  "zustand":          "Mittel",
  "adresse_detail":   "Musterstraße 12, 1190 Wien",
  "lage_bewertung":   "Ruhige Wohnlage, U-Bahn 600m, …",
  "verkehrswert":     "EUR 350.000,–",
  "mindestgebot":     "EUR 285.000,–",
  "sanierungskosten_schaetzung": "ca. 40.000 EUR",
  "investitions_score": 7.5,
  "risiko_klasse":    "Niedrig",
  "rendite_potenzial": "Hoch",
  "marktlage":        "Verkäufermarkt",
  "chancen":          ["Lage in etabliertem Wohnviertel", "…"],
  "risiken":          ["Sanierungsstau Dach", "…"],
  "empfehlung":       "KAUFEN",
  "zusammenfassung":  "…",
  "raw_response":     "{…}"  // original JSON string from the AI (for debugging)
}
```

### Settings (`settings.json`)

```jsonc
{
  "ai_provider":       "gemini",
  "openai_api_key":    "sk-…",
  "openai_model":      "gpt-4o-mini",
  "anthropic_api_key": "sk-ant-…",
  "anthropic_model":   "claude-haiku-20240307",
  "gemini_api_key":    "AIza…",
  "gemini_model":      "gemini-2.0-flash",
  "grok_api_key":      "xai-…",
  "grok_model":        "grok-3-fast-beta",
  "ollama_base_url":   "http://localhost:11434",
  "ollama_model":      "llama3.2",
  "max_context_chars": 40000,
  "headless":          true
}
```

---

## 5. AI Provider System

All five providers share the same interface:

```python
async def _<provider>(user_msg: str) -> dict:
    # 1. Build client + call API with SYSTEM_PROMPT + user_msg
    # 2. raw = response text (JSON string)
    # 3. result = _parse_json(raw)
    # 4. result["provider"] = "<name>"
    # 5. result["model"]    = config.<PROVIDER>_MODEL
    # 6. result["tokens_used"] = ...
    # 7. result["raw_response"] = raw
    return result
```

Provider dispatch lives in `analyze()`:

```python
if   provider == "openai":    return await _openai(user_msg)
elif provider == "anthropic":  return await _anthropic(user_msg)
elif provider == "gemini":     return await _gemini(user_msg)
elif provider == "grok":       return await _grok(user_msg)
elif provider == "ollama":     return await _ollama(user_msg)
else: raise ValueError(f"Unknown AI provider: {provider}")
```

| Provider | SDK / Transport | JSON mode |
|---|---|---|
| OpenAI | `openai.AsyncOpenAI` | `response_format={"type":"json_object"}` |
| Anthropic | `anthropic.AsyncAnthropic` | `_parse_json` strips any markdown fences |
| Gemini | `google.genai.Client (aio)` | `response_mime_type="application/json"` |
| Grok | `openai.AsyncOpenAI` @ `api.x.ai/v1` | `response_format={"type":"json_object"}` |
| Ollama | `httpx` POST `/api/chat` | `"format":"json"` in payload |

---

## 6. Adding a New AI Provider

Follow these five steps to add, say, a **Mistral** provider:

### Step 1 — `config.py`

```python
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL   = "mistral-large-latest"
```

Add to `apply_settings()`:
```python
global MISTRAL_API_KEY, MISTRAL_MODEL
MISTRAL_API_KEY = s.get("mistral_api_key", MISTRAL_API_KEY)
MISTRAL_MODEL   = s.get("mistral_model",   MISTRAL_MODEL)
```

### Step 2 — `ai_analyzer.py`

Add the backend function:
```python
async def _mistral(user_msg: str) -> dict:
    from mistralai.async_client import MistralAsyncClient
    client = MistralAsyncClient(api_key=config.MISTRAL_API_KEY)
    resp = await client.chat(
        model=config.MISTRAL_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=5000,
    )
    raw = resp.choices[0].message.content
    result = _parse_json(raw)
    result["provider"]     = "mistral"
    result["model"]        = config.MISTRAL_MODEL
    result["tokens_used"]  = resp.usage.total_tokens if resp.usage else 0
    result["raw_response"] = raw
    return result
```

Add the dispatch case in `analyze()`:
```python
elif provider == "mistral":
    return await _mistral(user_msg)
```

### Step 3 — `main.py` — SettingsDialog

Add a new `QGroupBox` in `SettingsDialog.__init__()`:
```python
grp_ms = QGroupBox("Mistral AI")
form_ms = QFormLayout(grp_ms)
self.ms_key = QLineEdit(s.get("mistral_api_key", getattr(config, "MISTRAL_API_KEY", "")))
self.ms_key.setPlaceholderText("…")
self.ms_key.setEchoMode(QLineEdit.EchoMode.Password)
self.ms_model = QComboBox()
self.ms_model.setEditable(True)
self.ms_model.addItems(["mistral-large-latest", "mistral-small-latest"])
self.ms_model.setCurrentText(s.get("mistral_model", getattr(config, "MISTRAL_MODEL", "")))
form_ms.addRow("API Key:", self.ms_key)
form_ms.addRow("Modell:", self.ms_model)
layout.addWidget(grp_ms)
```

Add the provider to the combo:
```python
self.provider_combo.addItems(["openai", "anthropic", "gemini", "grok", "mistral", "ollama"])
```

Save in `_save()`:
```python
"mistral_api_key": self.ms_key.text().strip(),
"mistral_model":   self.ms_model.currentText().strip(),
```

### Step 4 — `requirements.txt`

```
mistralai>=1.0.0
```

### Step 5 — `data/jsons/settings.example.json`

```jsonc
"mistral_api_key": "",
"mistral_model":   "mistral-large-latest",
```

---

## 7. Extending the Scraper

### Adding a new search filter

1. Add the UI widget to the appropriate form in `MainWindow._build_search_tab()` (inside `f_einfach`, `f_az`, or `f_erw`).
2. Pass the new value in `params` dict inside `MainWindow._do_search()`.
3. Read `params.get("your_key")` inside the correct `_fill_*` method in `scraper.py` and use `_try_fill()` or `_try_select_by_value()`.

### Adding a new detail field

In `_parse_detail()`, add a key to the returned dict using the `field()` closure:

```python
"my_field": field(r"My Label:\s+\n+\s*(.+)"),
```

If the field appears under multiple labels, chain with `or`:
```python
"my_field": field(r"Label A:.*?(.+)") or field(r"Label B:.*?(.+)"),
```

### Supporting a different portal domain

Set `EDIKTE_BASE_URL` in `config.py` and update `SEARCH_MODES` in `scraper.py`.  
All relative URLs in `_parse_result_rows_fallback()` use `urljoin(config.EDIKTE_BASE_URL, href)`.

---

## 8. UI Architecture

```
QMainWindow (MainWindow)
├── QToolBar
│   ├── Brand label
│   ├── ⚙ Einstellungen → SettingsDialog (QDialog)
│   └── Active provider label
├── QTabWidget
│   ├── Tab 0: "🔍 Suche & Ergebnisse"
│   │   └── QSplitter (Horizontal)
│   │       ├── Left panel (290px fixed)  – search form + bulk actions
│   │       │   └── QStackedWidget
│   │       │       ├── f_einfach  (Einfache Suche)
│   │       │       ├── f_az       (Aktenzeichen)
│   │       │       └── f_erw      (Erweiterte Suche)
│   │       ├── Middle panel – QTableView (EdikteModel)
│   │       └── Right panel (≥300px) – DetailPanel
│   │           ├── Title label
│   │           ├── QScrollArea (metadata + analysis)
│   │           └── Action buttons (Download / KI-Analyse)
│   └── Tab 1: "📊 Investitions-Übersicht" (OverviewTab)
│       ├── KPI card row (5 × QFrame#card)
│       ├── Refresh button
│       └── QTableView (OverviewModel)
└── QStatusBar + QProgressBar (indefinite spinner)
```

**Key UI patterns used:**

- `QAbstractTableModel` subclasses rather than `QStandardItemModel` — gives full control over color-coding via `ForegroundRole`
- `QScrollArea` for both `SettingsDialog` body and `DetailPanel` content — handles long content without fixed heights
- `Worker(QThread)` with `pyqtSignal` — keeps the UI responsive during all async I/O
- Single global `DARK_STYLE` stylesheet applied at app level; `objectName` selectors (`#btn_primary`, `#card`, etc.) allow per-widget overrides without subclassing

---

## 9. Configuration System

`config.py` is the **single source of truth** for runtime settings.  
It uses module-level globals so any module can do `import config; config.AI_PROVIDER`.

```
App startup
    │
    ▼
config.py imports → apply_settings() called at module level
    │  reads settings.json → overwrites globals
    ▼
All other modules (main, scraper, ai_analyzer) import config
    │  and read config.AI_PROVIDER, config.OPENAI_API_KEY, etc.
    ▼
User changes settings → SettingsDialog._save()
    │  config.save_settings(s)  → writes settings.json
    │  config.apply_settings()  → re-overwrites globals
    ▼
Next Worker call already uses updated globals
(no restart needed)
```

**Important**: `config.HEADLESS` controls whether Playwright opens a visible browser window.  
Set `"headless": true` in `settings.json` for production use.

---

## 10. Threading Model

The UI runs entirely on the **Qt main thread**.  
Every async operation (scrape / download / analyze) runs in a dedicated `Worker(QThread)`:

```
Qt Main Thread                    Worker QThread
─────────────────                 ────────────────────────────────────
_do_search() creates Worker
w.start()  ──────────────────────▶ run():
                                    loop = asyncio.new_event_loop()
                                    result = loop.run_until_complete(coro)
                                    self.finished.emit(result)   ──────▶ _on_search_done()
                                    -- OR --
                                    self.error.emit(str(e))     ──────▶ _on_error()
                                    -- cleanup --
                                    loop.run_until_complete(loop.shutdown_asyncgens())
                                    loop.close()
```

**Rules:**
- Never access `storage` from multiple Workers simultaneously for write operations — `storage.py` uses a `threading.Lock` for protection.
- `QLabel`, `QTableView`, and all other Qt widgets must only be touched from the main thread. Workers communicate only via signals.
- Workers are appended to `MainWindow._workers` while running and removed from the list on completion/error to prevent GC-related crashes.

---

## 11. Error Handling Strategy

| Layer | How errors are handled |
|---|---|
| `scraper._parse_detail()` | Non-critical fields return `""` (default); whole detail fetch exceptions are caught and the partial entry is still saved |
| `scraper.download_gutachten()` | Each PDF selector is tried in sequence; failure returns `None`; caller sets `status="no_pdf"` |
| `ai_analyzer.analyze()` | Provider exceptions propagate to `Worker.run()` which emits `error` signal |
| `ai_analyzer._parse_json()` | `json.JSONDecodeError` produces a safe fallback dict with `baujahr="unbekannt"` instead of crashing |
| `storage._read()` | Corrupt JSON returns `[]` / `{}` silently; operations continue with an empty state |
| `Worker.run()` | All exceptions captured and forwarded to `_on_error()` which shows `QMessageBox.critical` |

---

## 12. Known Limitations & Future Work

| Area | Limitation | Suggested improvement |
|---|---|---|
| **Storage** | JSON files are loaded entirely into memory on each read | Switch to SQLite with `aiosqlite` for large datasets (1,000+ edikte) |
| **Scraping** | `_parse_result_rows_fallback()` is a best-effort generic parser; may miss rows on portal layout changes | Add Playwright network-interceptor to capture XHR JSON if DataTables starts using AJAX |
| **Bulk ops** | Bulk download and analyze run sequentially (one at a time) | Add `asyncio.gather()` with concurrency limit (`asyncio.Semaphore`) |
| **UI filtering** | No sort/filter on the results table | Add `QSortFilterProxyModel` between `EdikteModel` and `QTableView` |
| **Export** | No data export | Add CSV / Excel export via `csv` stdlib or `openpyxl` |
| **Re-analysis** | Changing AI provider does not re-analyze existing entries | Add "Re-analyse" button that forces a new AI call and overwrites the existing analysis |
| **Tests** | No automated tests | Add `pytest-asyncio` for scraper unit tests with recorded HTML fixtures; `pytest-qt` for UI tests |
| **PDF extraction** | Some court PDFs use image-only scans (no text layer) | Integrate `pytesseract` (OCR) as a third-tier fallback after `PyPDF2` |
| **Prompt language** | Prompt is German-only | Parameterise language; could support other EU court portals |

---

*This document is maintained alongside the code. If you add a module, change a data model, or introduce a new provider, please update the relevant sections here.*
