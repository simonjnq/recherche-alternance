"""Configuration + profil utilisateur chargé depuis data/profile.json."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CVS_DIR = DATA_DIR / "cvs"
OFFERS_DIR = DATA_DIR / "offers"
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "db.sqlite"
PROFILE_PATH = DATA_DIR / "profile.json"
FRONTEND_DIST = ROOT / "frontend" / "dist"

for d in (DATA_DIR, CVS_DIR, OFFERS_DIR, CACHE_DIR):
    d.mkdir(parents=True, exist_ok=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8787"))

DEFAULT_PROFILE: dict[str, Any] = {
    "name": "",
    "email": "",
    "phone": "",
    "linkedin": "",
    "location": "Paris",
    "contract_types": ["alternance", "apprentissage"],
    "tagline": "",                       # phrase de positionnement courte
    "signature_achievements": [],        # 3-5 phrases impactantes à toujours pouvoir citer
    "letter_style": "natural",           # natural | factual | story | direct
    "forbidden_phrases": [],             # tics à bannir (vide → liste par défaut côté letter.py)
    "keywords": {
        "ia_automation": [
            "automatisation IA", "LLM", "agent IA", "n8n", "Zapier", "workflow IA",
        ],
        "growth": [
            "growth engineer", "growth marketing IA", "acquisition IA",
        ],
        "tech_builder": [
            "prompt engineer", "no-code builder", "scraping automatisation",
        ],
        "data_product": [
            "product manager IA", "business analyst IA",
        ],
        "combos": [
            "IA alternance Paris", "AI engineer alternance", "no-code alternance Paris",
        ],
    },
    "sources_enabled": {
        "la_bonne_alternance": True,
        "indeed": True,
        "wttj": True,
        "hellowork": True,
        "apec": True,
        "linkedin": True,
        "linkedin_manual": True,
    },
    "score_threshold_generate": 70,
    "max_offers_per_source": 60,
}


def load_profile() -> dict[str, Any]:
    if not PROFILE_PATH.exists():
        PROFILE_PATH.write_text(json.dumps(DEFAULT_PROFILE, indent=2, ensure_ascii=False))
        return DEFAULT_PROFILE.copy()
    data = json.loads(PROFILE_PATH.read_text())
    # Merge avec les valeurs par défaut pour exposer les nouveaux champs sur les
    # profils créés avant l'ajout de ces champs.
    merged: dict[str, Any] = {**DEFAULT_PROFILE, **data}
    # keywords est un dict imbriqué — merger les clés manquantes uniquement
    kws = {**DEFAULT_PROFILE["keywords"], **(data.get("keywords") or {})}
    merged["keywords"] = kws
    src = {**DEFAULT_PROFILE["sources_enabled"], **(data.get("sources_enabled") or {})}
    merged["sources_enabled"] = src
    return merged


def save_profile(profile: dict[str, Any]) -> None:
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False))


def all_keywords(profile: dict[str, Any]) -> list[str]:
    return [kw for group in profile["keywords"].values() for kw in group]


PHOTO_EXTS = ("jpg", "jpeg", "png", "webp")


def get_profile_photo_path() -> Path | None:
    for ext in PHOTO_EXTS:
        p = DATA_DIR / f"profile_photo.{ext}"
        if p.exists():
            return p
    return None


def get_profile_photo_data_url() -> str | None:
    p = get_profile_photo_path()
    if not p:
        return None
    import base64
    ext = p.suffix.lstrip(".").lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"
