"""Analyse Vision d'une image de CV pour en extraire un style applicable.

Plutôt que de générer du code arbitraire (risqué), on demande à Claude Sonnet
Vision d'analyser l'image et de renvoyer un JSON avec :
- template (parmi nos 3 built-in) qui correspond le mieux au layout détecté
- accent_color (hex dominant)
- font (Poppins / Inter / Manrope si match)
- density (sentiment de remplissage)
- photo_enabled (si l'image montre une photo)

L'utilisateur clone alors le STYLE du design, pas la structure exacte.
"""
from __future__ import annotations

import base64
import logging
from typing import Any

import httpx
from anthropic.types import TextBlock

from ..config import ANTHROPIC_MODEL
from .client import client

logger = logging.getLogger(__name__)

SYSTEM = """Tu analyses l'image d'un CV et tu en extrais un STYLE applicable à un template paramétrable.

Tu réponds en JSON STRICT avec ces clés :
{
  "template": "modern_2col" | "minimal_1col" | "bold_header",
  "accent_color": "#xxxxxx",     // couleur d'accent dominante (hex 6 chars)
  "font": "Poppins" | "Inter" | "Manrope",
  "density": 0.7-2.0,             // 0.7 = compact, 1.0 = normal, 1.5+ = aéré
  "photo_enabled": true | false,
  "notes": "1-2 phrases de ce qui caractérise ce design"
}

Règles pour template :
- modern_2col : sidebar colorée à gauche + main à droite avec cards
- minimal_1col : une seule colonne, beaucoup d'espace, sobre, sans bandeau coloré
- bold_header : bande de couleur pleine largeur en haut avec le nom dessus

Règles pour accent_color :
- Identifie la couleur primaire/d'accent du CV (pas le noir/blanc/gris)
- Renvoie en hex 6 caractères

Règles pour font :
- Match approximatif (Poppins/Inter/Manrope sont toutes sans-serif modernes)
- Si tu vois une serif → renvoie "Inter" comme fallback neutre

Rends UNIQUEMENT le JSON, sans préambule, sans ```."""


async def style_from_image(image_url: str | None = None, image_bytes: bytes | None = None, mime: str = "image/png") -> dict[str, Any]:
    """Renvoie un dict de style depuis une image (URL distante ou bytes uploadés)."""
    if image_bytes is None and image_url:
        # Télécharge l'image depuis l'URL
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as http:
            r = await http.get(image_url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                raise RuntimeError(f"Image fetch failed: HTTP {r.status_code}")
            image_bytes = r.content
            ct = r.headers.get("content-type", "").split(";")[0].strip().lower()
            if ct.startswith("image/"):
                mime = ct
    if not image_bytes:
        raise RuntimeError("No image data")

    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    content: list[dict[str, Any]] = [
        {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
        {"type": "text", "text": "Analyse ce CV et renvoie le JSON de style conforme au schéma."},
    ]
    resp = await client().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=600,
        temperature=0.2,
        system=[{"type": "text", "text": SYSTEM}],
        messages=[{"role": "user", "content": content}],
    )
    parts: list[str] = []
    for block in resp.content:
        if isinstance(block, TextBlock):
            parts.append(block.text)
    text = "".join(parts).strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()
    import json as _json
    data = _json.loads(text)
    return _normalize(data)


VALID_TEMPLATES = {"modern_2col", "minimal_1col", "bold_header"}
VALID_FONTS = {"Poppins", "Inter", "Manrope"}


def _normalize(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    t = d.get("template", "modern_2col")
    out["template"] = t if t in VALID_TEMPLATES else "modern_2col"
    color = (d.get("accent_color") or "").strip()
    if not (color.startswith("#") and len(color) == 7):
        color = "#2d52c4"
    out["accent_color"] = color
    f = d.get("font", "Poppins")
    out["font"] = f if f in VALID_FONTS else "Poppins"
    try:
        d_val = float(d.get("density") or 1.0)
        out["density"] = max(0.7, min(2.0, d_val))
    except Exception:
        out["density"] = 1.0
    out["photo_enabled"] = bool(d.get("photo_enabled", True))
    out["notes"] = str(d.get("notes") or "")[:300]
    return out
