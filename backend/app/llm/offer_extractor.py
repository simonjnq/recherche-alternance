"""Extrait les métadonnées d'une offre collée en texte brut (copier-coller).

Quand une offre n'est pas trouvée par le scraping, l'utilisateur colle son texte :
on en tire titre / entreprise / lieu / contrat / salaire (Haiku, cheap). La
description reste le texte collé (on ne perd rien pour le scoring/génération).
"""
from __future__ import annotations

import logging
from typing import Any

from .client import complete_json

logger = logging.getLogger(__name__)

HAIKU = "claude-haiku-4-5-20251001"

SYSTEM = """On te donne le texte brut d'une offre d'emploi/alternance (copié-collé). Extrais-en les métadonnées en JSON strict :

{
  "title": "intitulé du poste (sans le nom d'entreprise, sans H/F)",
  "company": "nom de l'entreprise ou null",
  "location": "ville/localisation ou null",
  "contract": "type de contrat si mentionné (Alternance, Apprentissage, CDI, Stage…) ou null",
  "salary": "rémunération si mentionnée ou null"
}

Règles : n'invente rien (null si absent). Le titre est court et propre."""


async def extract_offer_meta(text: str) -> dict[str, Any]:
    user = f"""Texte de l'offre :

{text[:12000]}

Renvoie UNIQUEMENT le JSON."""
    try:
        data = await complete_json(system=SYSTEM, user=user, max_tokens=400, model=HAIKU)
    except Exception as e:
        logger.warning("Extraction offre collée échouée (%s)", e)
        data = {}
    if not isinstance(data, dict):
        data = {}

    def _s(v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    return {
        "title": _s(data.get("title")),
        "company": _s(data.get("company")),
        "location": _s(data.get("location")),
        "contract": _s(data.get("contract")),
        "salary": _s(data.get("salary")),
    }
