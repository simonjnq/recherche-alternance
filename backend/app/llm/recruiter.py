"""Agent recruteur : évalue une candidature générée (CV + lettre) face à l'offre.

Simule le tri d'un recruteur/manager qui recrute des alternants : convoquerait-il
en entretien ? Renvoie un verdict, un score, les forces/faiblesses et des
suggestions actionnables — qu'on peut réinjecter dans une régénération.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from ..models import Offer
from .client import complete_json

logger = logging.getLogger(__name__)

SYSTEM = """Tu es un recruteur/manager expérimenté qui recrute des ALTERNANTS et qui trie des dizaines de candidatures par jour. On te donne une OFFRE, le CV adapté et la LETTRE d'un candidat.

Évalue HONNÊTEMENT et avec exigence : convoquerais-tu ce candidat en entretien ? Juge l'adéquation réelle au poste, la crédibilité et le concret des preuves, la personnalisation (vs générique), la clarté. Pas de complaisance : si c'est hors-sujet, générique ou creux, dis-le franchement.

Réponds en JSON strict :
{
  "verdict": "entretien" | "peut-etre" | "non",
  "score": 0-100,                              // probabilité de convocation en entretien
  "verdict_reason": "1-2 phrases : pourquoi ce verdict, du point de vue recruteur",
  "strengths": ["point fort concret", ...],    // 2-4
  "weaknesses": ["faiblesse/risque concret", ...],  // 2-4
  "cv_suggestions": ["amélioration actionnable et précise du CV", ...],     // 2-4
  "letter_suggestions": ["amélioration actionnable et précise de la lettre", ...]  // 2-4
}

Les suggestions doivent être DIRECTEMENT applicables (quoi changer, où), pas des généralités."""


async def recruiter_review(offer: Offer, cv_text: str, letter_md: str) -> dict[str, Any]:
    user = f"""=== OFFRE ===
Titre : {offer.title}
Entreprise : {offer.company or 'n/c'}
Localisation : {offer.location or 'n/c'}
Compétences clés : {', '.join(offer.skills[:12]) if offer.skills else 'n/c'}

Description :
{(offer.description or '')[:3500]}

=== CV DU CANDIDAT (texte) ===
{cv_text[:4000]}

=== LETTRE DU CANDIDAT ===
{letter_md[:3000]}

Évalue cette candidature et renvoie UNIQUEMENT le JSON."""
    data = await complete_json(system=SYSTEM, user=user, max_tokens=1500)
    return _normalize(data)


def _normalize(d: Any) -> dict[str, Any]:
    if not isinstance(d, dict):
        d = {}
    verdict = str(d.get("verdict") or "peut-etre").lower().strip()
    if verdict not in ("entretien", "peut-etre", "non"):
        verdict = "peut-etre"
    try:
        score = max(0, min(100, int(d.get("score", 0))))
    except (TypeError, ValueError):
        score = 0

    def _lst(v: Any) -> list[str]:
        return [str(x).strip() for x in v if str(x).strip()][:5] if isinstance(v, list) else []

    return {
        "verdict": verdict,
        "score": score,
        "verdict_reason": str(d.get("verdict_reason") or "").strip()[:500],
        "strengths": _lst(d.get("strengths")),
        "weaknesses": _lst(d.get("weaknesses")),
        "cv_suggestions": _lst(d.get("cv_suggestions")),
        "letter_suggestions": _lst(d.get("letter_suggestions")),
    }


def review_to_cv_notes(review: dict[str, Any]) -> str:
    """Transforme le retour recruteur en consignes pour régénérer le CV."""
    bits = list(review.get("cv_suggestions") or [])
    bits += [f"Corriger : {w}" for w in (review.get("weaknesses") or [])]
    if not bits:
        return ""
    return "RETOUR RECRUTEUR à corriger en priorité :\n- " + "\n- ".join(bits)


def review_to_letter_notes(review: dict[str, Any]) -> str:
    """Transforme le retour recruteur en consignes pour régénérer la lettre."""
    bits = list(review.get("letter_suggestions") or [])
    bits += [f"Corriger : {w}" for w in (review.get("weaknesses") or [])]
    if not bits:
        return ""
    return "RETOUR RECRUTEUR à corriger en priorité :\n- " + "\n- ".join(bits)


def html_to_text(html: str) -> str:
    s = re.sub(r"<(style|script|head)[^>]*>.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()
