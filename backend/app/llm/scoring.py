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
2. Donner un score de 0 à 100 de PERTINENCE de l'offre pour le candidat
3. Justifier en 1-2 phrases (reasoning)
4. Lister des red flags réellement bloquants

Le score mesure à quel point LE POSTE correspond au candidat — PAS la qualité de
rédaction ou la complétude de l'annonce.

Ce qui FAIT le score (par ordre d'importance) :
- Adéquation au domaine et aux mots-clés prioritaires du candidat (déterminant)
- Adéquation au niveau ALTERNANT/JUNIOR : un poste clairement Senior / Lead /
  Principal / Staff / Head / Director / Manager confirmé / 5+ ans d'XP est INADAPTÉ
  à un alternant → score bas (≤ 40) même si le domaine colle parfaitement
- Contrat alternance / apprentissage confirmé

⚠️ NE FAIS JAMAIS BAISSER LE SCORE pour ces raisons (très fréquentes et normales en alternance) :
- salaire non précisé ou non chiffré
- description courte, vague ou peu détaillée
- localisation non précisée (Paris par défaut)
- entreprise peu connue, jeune, ou sans site web
- annonce générique / publiée par une école ou un CFA
Ces éléments sont NEUTRES. Juge le poste lui-même, jamais la complétude de l'annonce.

red_flags : n'y mets QUE des signaux vraiment bloquants — contrat non-alternance,
poste manifestement senior, domaine très éloigné du profil, localisation explicitement
incompatible. N'inscris JAMAIS "salaire non précisé", "description courte" ou
"entreprise peu connue".

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
