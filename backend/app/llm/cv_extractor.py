"""Conversion image (PNG/JPG) → HTML via Claude Vision.

L'idée : l'utilisateur uploade son CV sous forme d'image, Claude lit le contenu
et produit un HTML structuré qu'on peut ensuite adapter par offre.
"""
from __future__ import annotations

import base64
import logging
from typing import Any

from anthropic.types import TextBlock

from ..config import ANTHROPIC_MODEL
from .client import client

logger = logging.getLogger(__name__)

SYSTEM = """Tu es un expert en extraction de CV. L'utilisateur te fournit l'image de son CV.

Ton travail : produire un HTML propre et structuré qui reproduit fidèlement le contenu.

Règles :
- Extrais TOUT le texte visible sans rien inventer ni omettre.
- Conserve la structure logique : nom/titre en <h1>, sections (Expérience, Formation, Compétences…) en <h2>, postes/diplômes en <h3>.
- Utilise <ul><li> pour les listes de bullet points.
- Utilise <p> pour les paragraphes.
- Ajoute des <section> pour regrouper.
- Inclus un <style> minimal et sobre (Inter/system-ui, marges raisonnables, mise en page simple une colonne).
- Pas de JS, pas d'images, pas de liens externes.
- Retourne UNIQUEMENT le HTML complet (de <!DOCTYPE html> à </html>), sans texte avant ni après, sans ```."""


MIME_BY_EXT = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "pdf": "application/pdf",
}


def guess_mime(filename: str, fallback: str = "image/png") -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return MIME_BY_EXT.get(ext, fallback)


async def extract_cv_to_html(file_bytes: bytes, mime: str) -> str:
    """Appelle Claude avec l'image (ou PDF) et renvoie un HTML structuré."""
    b64 = base64.standard_b64encode(file_bytes).decode("ascii")
    if mime == "application/pdf":
        block = {
            "type": "document",
            "source": {"type": "base64", "media_type": mime, "data": b64},
        }
    else:
        block = {
            "type": "image",
            "source": {"type": "base64", "media_type": mime, "data": b64},
        }
    content: list[dict[str, Any]] = [
        block,
        {
            "type": "text",
            "text": "Convertis ce CV en HTML structuré selon les règles. Retourne uniquement le HTML complet.",
        },
    ]
    resp = await client().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=8000,
        temperature=0.1,
        system=[{"type": "text", "text": SYSTEM}],
        messages=[{"role": "user", "content": content}],
    )
    parts: list[str] = []
    for block in resp.content:
        if isinstance(block, TextBlock):
            parts.append(block.text)
    html = "".join(parts).strip()
    if html.startswith("```"):
        html = html.split("```", 2)[1]
        if html.lower().startswith("html"):
            html = html[4:]
        html = html.rsplit("```", 1)[0].strip()
    if "<html" not in html.lower():
        logger.warning("CV extractor: pas de <html> détecté, enveloppe minimale ajoutée.")
        html = f"<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>{html}</body></html>"
    return html
