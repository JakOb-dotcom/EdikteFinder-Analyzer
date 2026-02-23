"""
AI analysis module for EdikteFinder-Analyzer.
Supports OpenAI, Anthropic, Google Gemini, xAI Grok, and Ollama (local).
Token-efficient: extracts key sections before sending to the model.
20-30 Seiten Gutachten: ~40.000 Zeichen Kontext + 5.000 Output-Token für Cloud, 8.000 für Ollama.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)


# ── Prompt Templates ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Du bist ein erfahrener Immobiliengutachter und Investitionsberater mit Fokus auf österreichische Gerichtsversteigerungen. 
Analysiere den gegebenen Text aus einem gerichtlichen Schätzgutachten und extrahiere alle relevanten Immobiliendaten.
Antworte AUSSCHLIESSLICH im angegebenen JSON-Format. Keine zusätzlichen Erklärungen außerhalb des JSON."""

ANALYSIS_PROMPT = """Analysiere dieses österreichische Gerichtsgutachten und gib eine strukturierte Immobilienbewertung zurück.

=== GUTACHTEN-TEXT (Auszug) ===
{text}

=== EDIKT-METADATEN (vom Versteigerungsportal) ===
Aktenzeichen: {aktenzeichen}
Gericht: {gericht}
Versteigerungstermin: {versteigerung}
Mindestgebot (lt. Edikt): {mindestgebot}

=== EXTRAKTIONSREGELN (SEHR WICHTIG – lies genau) ===

Feld "verkehrswert":
  → Suche nach EINEM dieser Begriffe (häufige österreichische Gutachtenbegriffe):
     Verkehrswert, Gesamtverkehrswert, Marktwert, Gesamtmarktwert, Schätzwert,
     Gesamtschätzwert, Liegenschaftswert, Objektwert, Zeitwert, Sachwert,
     Wert der Liegenschaft, Wert des Objektes, festgestellter Wert,
     Bodenwert + Bauwert (addiere diese dann), Gesamtwert
  → Gib den höchsten genannten Gesamtwert an (nicht Teilwerte wie nur Boden oder nur Gebäude).
  → Format: z.B. "EUR 285.000,–" oder "285.000 EUR"
  → Falls kein expliziter Verkehrswert genannt: verwende den Schätzwert oder das Mindestgebot
     aus den Edikt-Metadaten ({mindestgebot}) und schreibe "ca. {mindestgebot} (lt. Edikt-Mindestgebot)"
  → NIEMALS null – immer einen Wert liefern!

Feld "baujahr":
  → Suche nach EINEM dieser Begriffe:
     Baujahr, Errichtungsjahr, Erbaut, Bauperiode, Baualtersklasse, Herstellungsjahr,
     Herstellungszeitraum, Baudatum, errichtet ca., erbaut ca.,
     Altbau (vor 1945), Gründerzeit, Zwischenkriegszeit (1919–1945), Nachkriegsbau (1945–1970)
  → Falls ein Jahrzehnt oder Zeitraum genannt: schreibe z.B. "ca. 1960er" oder "1950–1965"
  → Falls kein Baujahr gefunden: schreibe "unbekannt" – NIEMALS null für dieses Feld!

Feld "flaeche":
  → Suche nach: Nutzfläche, Wohnfläche, Gesamtfläche, Bruttogeschossfläche (BGF),
     Nettogrundrissflächs (NGF), Grundstücksfläche, Grundfläche, m²
  → Nenne alle verfügbaren Flächenangaben, z.B. "Wohnfläche 87 m², Grundstück 412 m²"

Feld "zustand":
  → Ableiten aus: Renovierungsstand, Instandhaltungszustand, Baumängel, Sanierungsbedarf,
     Feuchtigkeit, Schimmel, Heizsystem (alt/neu), Fenster (alt/neu), Dach (dicht/undicht)

Feld "sanierungskosten_schaetzung":
  → Suche nach: Sanierungskosten, Renovierungskosten, Instandsetzungskosten, Reparaturbedarf
  → Falls nicht im Text: schätze grob basierend auf Fläche × Zustand
     (Vollsanierung ~500–1.000 EUR/m², Teilsanierung ~150–400 EUR/m²)
  → Gib null wenn Zustand "Sehr gut" oder "Gut"

=== JSON-AUSGABE ===
Antworte NUR mit diesem JSON-Objekt:
{{
  "objekt_art": "z.B. Einfamilienhaus / Eigentumswohnung / Gewerbeimmobilie / Grundstück",
  "flaeche": "Alle Flächenangaben aus dem Gutachten",
  "baujahr": "Baujahr, Zeitraum oder 'unbekannt' – NICHT null",
  "zustand": "Sehr gut / Gut / Mittel / Sanierungsbedürftig / Abrissreif",
  "adresse_detail": "vollständige Adresse aus dem Gutachten",
  "lage_bewertung": "Mikrolage (Straße/Viertel) und Makrolage (Stadt/Region), Infrastruktur, Verkehrsanbindung",
  "verkehrswert": "Verkehrswert/Marktwert in EUR – aus Gutachten oder Edikt-Metadaten, NICHT null",
  "mindestgebot": "Mindestgebot / Schätzwert in EUR",
  "sanierungskosten_schaetzung": "Geschätzte Sanierungskosten in EUR oder null wenn nicht nötig",
  "investitions_score": 7.0,
  "risiko_klasse": "Sehr Niedrig / Niedrig / Mittel / Hoch / Sehr Hoch",
  "rendite_potenzial": "Sehr Hoch / Hoch / Mittel / Niedrig / Negativ",
  "marktlage": "Verkäufermarkt / Ausgewogen / Käufermarkt",
  "chancen": [
    "Chance 1 – konkret und spezifisch",
    "Chance 2 – z.B. Lage, Preis-Leistung, Entwicklungspotenzial",
    "Chance 3 – z.B. Mietrendite, Wertsteigerung",
    "Chance 4 – z.B. steuerliche Vorteile, Umbaumöglichkeit",
    "Chance 5 – z.B. Alleinstellungsmerkmal der Immobilie",
    "Chance 6 – falls zutreffend, sonst Feld weglassen"
  ],
  "risiken": [
    "Risiko 1 – z.B. Baumängel, Altlasten, Pfandrechte",
    "Risiko 2 – z.B. Leerstand, Mietnomaden, Nebenkosten",
    "Risiko 3 – z.B. Marktrisiko, Zinsentwicklung",
    "Risiko 4 – z.B. Sanierungsstau, behördliche Auflagen",
    "Risiko 5 – z.B. Lagerisiko, Infrastrukturmangel",
    "Risiko 6 – falls zutreffend, sonst Feld weglassen"
  ],
  "empfehlung": "KAUFEN / PRÜFEN / MEIDEN",
  "zusammenfassung": "Detaillierte Zusammenfassung in 5-7 Sätzen: Objektbeschreibung, Preiseinschätzung (Verkehrswert vs. Mindestgebot inkl. Abschlag in %), Renditepotenzial, empfohlene Strategie (Eigennutzung/Vermietung/Sanierung/Weiterverkauf)"
}}

Score-Legende (investitions_score 1-10, Dezimalwerte wie 6.5 erlaubt):
1–2   = Absolutes Risikoobjekt, Finger weg
3–4   = Erhebliche Mängel / schlechte Ausgangslage, sehr genau prüfen
5     = Durchschnitt – weder besonders attraktiv noch schlecht
6–7   = Interessantes Objekt mit vertretbarem Risiko
8–9   = Sehr attraktive Investition mit klarem Renditepotenzial
10    = Ausnahme-Deal, sofortiger Handlungsbedarf

Wichtig: Bewerte streng und realistisch. Österreichische Gerichtsversteigerungen haben oft versteckte
Risiken (Pfandrechte, Sanierungsstau, schwierige Mieter). Wenn der Verkehrswert deutlich über dem
Mindestgebot liegt, ist das eine Chance – erwähne den Abschlag in % in der Zusammenfassung."""


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF using pdfplumber (primary) or pypdf2 (fallback)."""
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            pages = []
            for page in pdf.pages:
                t = page.extract_text() or ""
                pages.append(t)
            text = "\n\n".join(pages)
        logger.info("Extracted %d chars via pdfplumber", len(text))
    except Exception as e:
        logger.warning("pdfplumber failed (%s), trying pypdf2", e)
        try:
            import PyPDF2
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = "\n\n".join(
                    page.extract_text() or "" for page in reader.pages
                )
            logger.info("Extracted %d chars via PyPDF2", len(text))
        except Exception as e2:
            logger.error("PDF extraction failed: %s", e2)

    return text


def smart_truncate(text: str, max_chars: int = config.MAX_CONTEXT_CHARS) -> str:
    """
    Token-efficient: keep the most relevant sections of a long document.
    Strategy: first 30% + middle 20% + last 50% (intro + values + conclusion)
    """
    if len(text) <= max_chars:
        return text

    intro  = text[: int(max_chars * 0.30)]
    # Find "Verkehrswert", "Schätzwert", "Mindestgebot" sections
    value_section = _extract_value_section(text, int(max_chars * 0.25))
    conclusion = text[-int(max_chars * 0.45):]

    combined = "\n\n[...]\n\n".join(filter(None, [intro, value_section, conclusion]))
    return combined[: max_chars + 500]  # slight buffer


def _extract_value_section(text: str, max_len: int) -> str:
    """Find and return the section around monetary values AND Baujahr.

    Priority order: Verkehrswert-related terms first (most critical for scoring),
    then Baujahr terms, then generic EUR/Bewertung as fallback.
    """
    # Tier 1 – value terms (most important for investment scoring)
    value_keywords = [
        "Verkehrswert", "Gesamtverkehrswert", "Marktwert", "Gesamtmarktwert",
        "Schätzwert", "Gesamtschätzwert", "Liegenschaftswert", "Sachwert",
        "Wertermittlung", "Bewertung", "Wert der Liegenschaft", "Mindestgebot",
    ]
    # Tier 2 – age / construction terms
    age_keywords = [
        "Baujahr", "Errichtungsjahr", "erbaut", "Bauperiode", "Baualtersklasse",
        "Herstellungsjahr", "Herstellungszeitraum",
    ]
    # Tier 3 – generic fallback
    fallback_keywords = ["EUR", "Sanierungskosten", "Instandsetzung"]

    text_lower = text.lower()
    half = max_len // 2

    # Try to grab one value section + one age section and combine them
    value_chunk = ""
    for kw in value_keywords:
        idx = text_lower.find(kw.lower())
        if idx != -1:
            start = max(0, idx - 300)
            end = min(len(text), idx + max_len)
            value_chunk = text[start:end]
            break

    age_chunk = ""
    for kw in age_keywords:
        idx = text_lower.find(kw.lower())
        if idx != -1:
            start = max(0, idx - 100)
            end = min(len(text), idx + half)
            age_chunk = text[start:end]
            break

    if value_chunk and age_chunk:
        return value_chunk + "\n\n[...Baujahr-Abschnitt...]\n\n" + age_chunk
    if value_chunk:
        return value_chunk
    if age_chunk:
        return age_chunk

    # Fallback
    for kw in fallback_keywords:
        idx = text_lower.find(kw.lower())
        if idx != -1:
            start = max(0, idx - 200)
            end = min(len(text), idx + max_len)
            return text[start:end]
    return ""


def make_summary(text: str, max_chars: int = 3000) -> str:
    """Create a short extractive summary for DB storage (no AI needed)."""
    # Keep first 1000 + value section + last 1000
    intro = text[:1000]
    value = _extract_value_section(text, 1500)
    outro = text[-500:] if len(text) > 1500 else ""
    return "\n---\n".join(filter(None, [intro, value, outro]))[:max_chars]


# ── AI Backends ───────────────────────────────────────────────────────────────

async def analyze(
    text: str,
    edikt_meta: dict,
    provider: Optional[str] = None,
) -> dict:
    """
    Run AI analysis on the extracted PDF text + edikt metadata.
    Returns a structured dict with all analysis fields.
    """
    provider = provider or config.AI_PROVIDER
    truncated = smart_truncate(text)

    prompt_vars = {
        "text": truncated,
        "aktenzeichen": edikt_meta.get("aktenzeichen", ""),
        "gericht":      edikt_meta.get("gericht", ""),
        "versteigerung": edikt_meta.get("versteigerung", ""),
        "mindestgebot":  edikt_meta.get("mindestgebot", ""),
    }
    user_msg = ANALYSIS_PROMPT.format(**prompt_vars)

    logger.info("Analyzing with provider=%s, ~%d chars", provider, len(truncated))

    if provider == "openai":
        return await _openai(user_msg)
    elif provider == "anthropic":
        return await _anthropic(user_msg)
    elif provider == "ollama":
        return await _ollama(user_msg)
    elif provider == "gemini":
        return await _gemini(user_msg)
    elif provider == "grok":
        return await _grok(user_msg)
    else:
        raise ValueError(f"Unknown AI provider: {provider}")


async def _gemini(user_msg: str) -> dict:
    """Google Gemini via the new google-genai SDK (google.genai)."""
    from google import genai
    from google.genai import types
    api_key = getattr(config, "GEMINI_API_KEY", None) or ""
    model_name = getattr(config, "GEMINI_MODEL", "gemini-2.0-flash")
    client = genai.Client(api_key=api_key)
    response = await client.aio.models.generate_content(
        model=model_name,
        contents=user_msg,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.1,
            max_output_tokens=5000,
        ),
    )
    raw = response.text if hasattr(response, "text") else str(response)
    result = _parse_json(raw)
    result["provider"] = "gemini"
    result["model"] = model_name
    try:
        result["tokens_used"] = response.usage_metadata.total_token_count
    except Exception:
        result["tokens_used"] = 0
    result["raw_response"] = raw
    return result


async def _grok(user_msg: str) -> dict:
    """Grok (xAI) – OpenAI-compatible API at api.x.ai/v1."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=getattr(config, "GROK_API_KEY", ""),
        base_url="https://api.x.ai/v1",
    )
    model_name = getattr(config, "GROK_MODEL", "grok-3-fast-beta")
    completion = await client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=5000,
    )
    raw = completion.choices[0].message.content
    tokens = completion.usage.total_tokens if completion.usage else 0
    result = _parse_json(raw)
    result["provider"]     = "grok"
    result["model"]        = model_name
    result["tokens_used"]  = tokens
    result["raw_response"] = raw
    return result


async def _openai(user_msg: str) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    completion = await client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=5000,
    )
    raw = completion.choices[0].message.content
    tokens = completion.usage.total_tokens if completion.usage else 0
    result = _parse_json(raw)
    result["provider"]    = "openai"
    result["model"]       = config.OPENAI_MODEL
    result["tokens_used"] = tokens
    result["raw_response"] = raw
    return result


async def _anthropic(user_msg: str) -> dict:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = await client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=5000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = msg.content[0].text if msg.content else "{}"
    tokens = (msg.usage.input_tokens + msg.usage.output_tokens) if msg.usage else 0
    result = _parse_json(raw)
    result["provider"]    = "anthropic"
    result["model"]       = config.ANTHROPIC_MODEL
    result["tokens_used"] = tokens
    result["raw_response"] = raw
    return result


async def _ollama(user_msg: str) -> dict:
    import httpx
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        "stream": False,
        "format": "json",
        # Ollama is local/free – generous token budget for large Gutachten (20-30 Seiten)
        "options": {"temperature": 0.1, "num_predict": 8000, "num_ctx": 32768},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{config.OLLAMA_BASE_URL}/api/chat", json=payload
        )
        resp.raise_for_status()
        data = resp.json()

    raw = data.get("message", {}).get("content", "{}")
    tokens = data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
    result = _parse_json(raw)
    result["provider"]    = "ollama"
    result["model"]       = config.OLLAMA_MODEL
    result["tokens_used"] = tokens
    result["raw_response"] = raw
    return result


def _parse_json(raw: str) -> dict:
    """Safely parse JSON response, even if wrapped in markdown."""
    raw = raw.strip()
    # Strip ```json ... ``` wrapper if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
        # Ensure list fields are native Python lists (JSON storage, not SQLite)
        for key in ("chancen", "risiken"):
            v = data.get(key)
            if isinstance(v, str):
                try:
                    data[key] = json.loads(v)
                except Exception:
                    data[key] = [v] if v else []
            elif not isinstance(v, list):
                data[key] = []
        # Coerce score to float (prompt allows decimals like 6.5)
        try:
            data["investitions_score"] = float(data.get("investitions_score") or 0)
        except (ValueError, TypeError):
            data["investitions_score"] = 0.0
        # Ensure critical fields are never None/null
        if not data.get("baujahr"):
            data["baujahr"] = "unbekannt"
        if not data.get("verkehrswert") and not data.get("mindestgebot"):
            data["verkehrswert"] = "nicht ermittelbar"
        return data
    except json.JSONDecodeError as e:
        logger.error("JSON parse error: %s | raw=%s", e, raw[:300])
        return {
            "objekt_art": "", "flaeche": "", "baujahr": "unbekannt", "zustand": "",
            "adresse_detail": "", "lage_bewertung": "", "verkehrswert": "nicht ermittelbar",
            "mindestgebot": "", "investitions_score": 0.0,
            "risiko_klasse": "", "rendite_potenzial": "", "marktlage": "",
            "sanierungskosten_schaetzung": None,
            "chancen": [], "risiken": [],
            "empfehlung": "PRÜFEN", "zusammenfassung": raw[:500],
        }
