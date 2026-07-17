"""Prépa entretien : questions probables, réponses ancrées sur le parcours réel,
questions à poser, et ce qu'il ne faut pas ignorer sur la boîte.

Consomme les deux briques déjà en place : la fiche entreprise (recherche web) et
le profil combiné issu des CVs. La règle qui compte ici : les réponses proposées
doivent s'appuyer sur des expériences RÉELLES du candidat. Une réponse inventée
est pire qu'une absence de réponse — elle s'effondre à la première relance du
recruteur, en face de lui.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .client import cached_system, complete
from .company_research import to_prompt_text

logger = logging.getLogger(__name__)

SYSTEM = """Tu prépares un candidat à un entretien d'alternance. Tu produis une fiche de prépa en Markdown, directement utilisable la veille de l'entretien.

RÈGLE ABSOLUE — les réponses que tu proposes s'appuient UNIQUEMENT sur des expériences, projets et compétences réellement présents dans le profil fourni. Tu n'inventes ni chiffre, ni client, ni mission. Si le profil ne permet pas de répondre à une question attendue, dis-le franchement dans « Tes angles faibles » plutôt que de fabriquer une réponse : le candidat s'effondrerait à la première relance.

Structure EXACTE (respecte les titres) :

## Ce qu'ils vont te demander
6 à 8 questions réellement probables pour CE poste dans CETTE boîte (pas un questionnaire générique). Pour chacune :
- la question en gras
- en dessous, une trame de réponse en 2-4 phrases, ancrée sur une expérience précise du profil (nomme-la). Pas de réponse toute faite à réciter : une trame que le candidat s'approprie.

## Tes angles faibles
2 à 4 points où il va être attaqué (manque d'expérience sur un point de l'offre, trou, écart profil/poste), et pour chacun une manière honnête de le traiter — assumer et compenser, jamais bluffer.

## Ce que tu dois savoir sur eux
Les faits de la fiche entreprise qu'il serait embarrassant d'ignorer. Court, en puces.

## Les questions à leur poser
4 à 5 questions qui montrent qu'il a creusé, dont au moins deux issues des points de vigilance ou des zones d'ombre de la fiche entreprise. Pas de question dont la réponse est sur leur site.

## Le piège de cet entretien
2-3 phrases : le risque spécifique de cet entretien précis. Sois direct.

Ton : direct, concret, pas de langue de bois, pas de conseils génériques type « soyez vous-même ». Pas de tiret long (— ou –), utilise la virgule ou les deux-points."""


async def prepare_interview(
    offer: Any,
    profile_text: Optional[str],
    company: Optional[dict[str, Any]] = None,
    extra_instructions: Optional[str] = None,
) -> str:
    """Fiche de prépa en Markdown."""
    fiche = to_prompt_text(company or {})
    extra = f"\n\nConsignes du candidat :\n{extra_instructions.strip()}" if (extra_instructions or "").strip() else ""

    user = f"""POSTE
- Intitulé : {offer.title}
- Entreprise : {offer.company or 'n/c'}
- Lieu : {offer.location or 'n/c'}
- Compétences identifiées : {', '.join(offer.skills) if getattr(offer, 'skills', None) else 'n/c'}

DESCRIPTION DE L'OFFRE
{(offer.description or '')[:6000]}

{fiche or "(pas de recherche entreprise disponible — ne fabrique rien sur eux, dis-le)"}

PROFIL RÉEL DU CANDIDAT (seule source autorisée pour les réponses)
{profile_text or "(profil indisponible)"}{extra}

Rédige la fiche de prépa en Markdown."""

    md = await complete(
        cached_system([SYSTEM]), user, max_tokens=4000, temperature=0.4,
    )
    from ..text_clean import strip_long_dashes
    md = strip_long_dashes(md.strip())
    logger.info("Prépa entretien générée pour offre %s (%d caractères)",
                getattr(offer, "id", "?"), len(md))
    return md
