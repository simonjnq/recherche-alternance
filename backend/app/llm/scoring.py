"""Scoring d'une offre : pertinence par rapport au profil + extraction skills + red flags."""
from __future__ import annotations

import logging
from typing import Any

from ..models import OfferRaw, OfferScored
from .client import cached_system, complete_json

logger = logging.getLogger(__name__)

SYSTEM = """Tu es un assistant qui aide un étudiant à trouver une alternance pertinente.

Pour chaque offre, tu dois :
1. Extraire les compétences clés demandées (techniques + soft skills)
2. Donner un score de 0 à 100 de pertinence par rapport au profil candidat
3. Justifier en 1-2 phrases (reasoning)
4. Lister des red flags éventuels (contrat non alternance, localisation incompatible, stack très éloignée, entreprise sans site, rémunération bizarre, etc.)

Critères de scoring (pondération indicative) :
- Alignement avec les mots-clés/domaines prioritaires du candidat : 40%
- Type de contrat (alternance / apprentissage) : 20% — si pas d'alternance, score max 30
- Localisation compatible : 15%
- Qualité / clarté de l'offre : 10%
- Opportunité de progression / stack moderne : 15%

Réponds en JSON strict:
{
  "skills": ["...", "..."],
  "score": 0-100,
  "reasoning": "...",
  "red_flags": ["..."]
}"""


def _profile_to_text(profile: dict[str, Any]) -> str:
    kws = "\n".join(f"- {cat} : {', '.join(v)}" for cat, v in profile["keywords"].items())
    return f"""Profil candidat:
- Localisation souhaitée : {profile.get('location', 'Paris')}
- Contrats recherchés : {', '.join(profile.get('contract_types', ['alternance']))}
- Nom : {profile.get('name', 'n/a')}

Domaines & mots-clés prioritaires:
{kws}"""


async def score_offer(offer: OfferRaw, profile: dict[str, Any]) -> OfferScored:
    profile_text = _profile_to_text(profile)
    offer_text = f"""Offre:
- Source : {offer.source}
- Titre : {offer.title}
- Entreprise : {offer.company or 'n/c'}
- Localisation : {offer.location or 'n/c'}
- Contrat : {offer.contract or 'n/c'}
- Salaire : {offer.salary or 'n/c'}
- URL : {offer.url}

Description:
{offer.description[:4000]}"""

    # Cache : SYSTEM (rubriques + barème) puis profil (stable sur toute la run).
    system_blocks = cached_system([SYSTEM, profile_text])

    try:
        data = await complete_json(
            system=system_blocks,
            user=offer_text,
            max_tokens=1500,
        )
        return OfferScored(
            skills=list(data.get("skills", []))[:15],
            score=max(0, min(100, int(data.get("score", 0)))),
            reasoning=str(data.get("reasoning", ""))[:1000],
            red_flags=list(data.get("red_flags", []))[:10],
        )
    except Exception as e:
        logger.warning("Scoring failed for %s: %s", offer.url, e)
        return OfferScored(score=0, reasoning=f"Erreur scoring: {e}")
