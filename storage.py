"""
JSON-based persistence layer for EdikteFinder-Analyzer Desktop.
All data lives in data/edikte.json and data/analyses.json.
Thread-safe via a simple file lock pattern.
"""

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import config

_lock = threading.Lock()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read(path: Path) -> dict | list:
    if not path.exists():
        return [] if "edikte" in path.name else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [] if "edikte" in path.name else {}


def _write(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8")


# ── Edikte CRUD ───────────────────────────────────────────────────────────────

def load_all_edikte() -> list[dict]:
    with _lock:
        return _read(config.EDIKTE_JSON)


def save_edikt(edikt: dict) -> str:
    """
    Upsert an Edikt by detail_url.  Returns the edikt_id.
    """
    with _lock:
        edikte = _read(config.EDIKTE_JSON)
        # Try to find existing entry by URL
        existing = next(
            (e for e in edikte if e.get("detail_url") == edikt.get("detail_url")), None
        )
        if existing:
            existing.update(edikt)
            existing["updated_at"] = datetime.now().isoformat()
            edikt_id = existing["id"]
        else:
            edikt_id = str(uuid.uuid4())[:8]
            edikt["id"]         = edikt_id
            edikt["created_at"] = datetime.now().isoformat()
            edikt["updated_at"] = edikt["created_at"]
            edikte.append(edikt)
        _write(config.EDIKTE_JSON, edikte)
    return edikt_id


def save_edikte_bulk(edikte_list: list[dict]) -> list[str]:
    """Save a batch of edikte, returning list of ids."""
    return [save_edikt(e) for e in edikte_list]


def get_edikt(edikt_id: str) -> Optional[dict]:
    with _lock:
        edikte = _read(config.EDIKTE_JSON)
        return next((e for e in edikte if e.get("id") == edikt_id), None)


def update_edikt_field(edikt_id: str, **kwargs):
    """Patch specific fields on an existing edikt."""
    with _lock:
        edikte = _read(config.EDIKTE_JSON)
        for e in edikte:
            if e.get("id") == edikt_id:
                e.update(kwargs)
                e["updated_at"] = datetime.now().isoformat()
                break
        _write(config.EDIKTE_JSON, edikte)


def delete_edikt(edikt_id: str):
    with _lock:
        edikte = _read(config.EDIKTE_JSON)
        edikte = [e for e in edikte if e.get("id") != edikt_id]
        _write(config.EDIKTE_JSON, edikte)
        # Also remove analysis
        analyses = _read(config.ANALYSES_JSON)
        analyses.pop(edikt_id, None)
        _write(config.ANALYSES_JSON, analyses)


# ── Analysis CRUD ─────────────────────────────────────────────────────────────

def load_all_analyses() -> dict:
    """Returns dict keyed by edikt_id."""
    with _lock:
        return _read(config.ANALYSES_JSON)


def save_analysis(edikt_id: str, analysis: dict):
    with _lock:
        analyses = _read(config.ANALYSES_JSON)
        analysis["edikt_id"]    = edikt_id
        analysis["analyzed_at"] = datetime.now().isoformat()
        analyses[edikt_id]      = analysis
        _write(config.ANALYSES_JSON, analyses)


def get_analysis(edikt_id: str) -> Optional[dict]:
    with _lock:
        analyses = _read(config.ANALYSES_JSON)
        return analyses.get(edikt_id)


# ── PDF path helper ───────────────────────────────────────────────────────────

def pdf_path_for(edikt_id: str) -> Path:
    return config.DOWNLOADS_DIR / f"gutachten_{edikt_id}.pdf"


def has_pdf(edikt_id: str) -> bool:
    return pdf_path_for(edikt_id).exists()


# ── Statistics ────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    edikte   = load_all_edikte()
    analyses = load_all_analyses()
    with_pdf = sum(1 for e in edikte if has_pdf(e.get("id", "")))
    scores   = [
        a.get("investitions_score", 0)
        for a in analyses.values()
        if isinstance(a.get("investitions_score"), (int, float))
    ]
    return {
        "total_edikte":   len(edikte),
        "total_analyses": len(analyses),
        "with_pdf":       with_pdf,
        "avg_score":      round(sum(scores) / len(scores), 1) if scores else 0,
        "top_score":      max(scores, default=0),
        "empfehlungen": {
            "KAUFEN": sum(1 for a in analyses.values() if a.get("empfehlung") == "KAUFEN"),
            "PRÜFEN": sum(1 for a in analyses.values() if a.get("empfehlung") == "PRÜFEN"),
            "MEIDEN": sum(1 for a in analyses.values() if a.get("empfehlung") == "MEIDEN"),
        },
    }
