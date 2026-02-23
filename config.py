"""
Configuration for EdikteFinder-Analyzer (Desktop Edition).
Settings persist in data/settings.json — no .env or server needed.
"""

import json
import os
from pathlib import Path

BASE_DIR     = Path(__file__).parent

# All data lives in ./data/
DATA_DIR      = BASE_DIR / "data"
JSONS_DIR     = DATA_DIR / "jsons"
DOWNLOADS_DIR = DATA_DIR / "downloads"

JSONS_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

# ── JSON Storage Paths ────────────────────────────────────────────────────────
EDIKTE_JSON   = JSONS_DIR / "edikte.json"     # list of all scraped Edikte
ANALYSES_JSON = JSONS_DIR / "analyses.json"   # AI analyses keyed by edikt id
SETTINGS_JSON = JSONS_DIR / "settings.json"   # user settings

# ── Playwright / Scraper ──────────────────────────────────────────────────────
EDIKTE_BASE_URL = "https://edikte.justiz.gv.at"
HEADLESS        = True
SCRAPER_TIMEOUT = 30_000  # ms

# ── AI Provider Defaults ──
AI_PROVIDER       = "openai"
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL      = "gpt-4o-mini"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL   = "claude-haiku-20240307"
OLLAMA_BASE_URL   = "http://localhost:11434"
OLLAMA_MODEL      = "llama3.2"
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL      = "gemini-2.0-flash"
GROK_API_KEY      = os.getenv("GROK_API_KEY", "")
GROK_MODEL        = "grok-3-fast-beta"

# Token budget per analysis.
# 20-30 Seiten Gutachten ≈ 50.000-75.000 Zeichen roh → 40.000 Zeichen Fenster ≈ 10.000 Input-Token
MAX_CONTEXT_CHARS = 40_000



# ── Settings helpers ──────────────────────────────────────────────────────────

def load_settings() -> dict:
    if SETTINGS_JSON.exists():
        try:
            return json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_settings(s: dict):
    SETTINGS_JSON.write_text(
        json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8"
    )



def apply_settings():
    """Copy settings.json values into this module's globals."""
    global AI_PROVIDER, OPENAI_API_KEY, OPENAI_MODEL
    global ANTHROPIC_API_KEY, ANTHROPIC_MODEL
    global OLLAMA_BASE_URL, OLLAMA_MODEL
    global GEMINI_API_KEY, GEMINI_MODEL
    global GROK_API_KEY, GROK_MODEL
    global MAX_CONTEXT_CHARS, HEADLESS
    s = load_settings()
    AI_PROVIDER       = s.get("ai_provider",       AI_PROVIDER)
    OPENAI_API_KEY    = s.get("openai_api_key",    OPENAI_API_KEY)
    OPENAI_MODEL      = s.get("openai_model",      OPENAI_MODEL)
    ANTHROPIC_API_KEY = s.get("anthropic_api_key", ANTHROPIC_API_KEY)
    ANTHROPIC_MODEL   = s.get("anthropic_model",   ANTHROPIC_MODEL)
    OLLAMA_BASE_URL   = s.get("ollama_base_url",   OLLAMA_BASE_URL)
    OLLAMA_MODEL      = s.get("ollama_model",      OLLAMA_MODEL)
    GEMINI_API_KEY    = s.get("gemini_api_key",    GEMINI_API_KEY)
    GEMINI_MODEL      = s.get("gemini_model",      GEMINI_MODEL)
    GROK_API_KEY      = s.get("grok_api_key",      GROK_API_KEY)
    GROK_MODEL        = s.get("grok_model",        GROK_MODEL)
    MAX_CONTEXT_CHARS = int(s.get("max_context_chars", MAX_CONTEXT_CHARS))
    HEADLESS          = bool(s.get("headless",     HEADLESS))


apply_settings()
