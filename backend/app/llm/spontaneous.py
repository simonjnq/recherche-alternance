"""Candidature spontanée : fabrique une pseudo-offre à partir d'une recherche
entreprise + du poste visé.

Tout le reste de la chaîne (scoring, adaptation du CV, lettre multi-agents,
agent recruteur, éditeur) prend une *offre* en entrée. Plutôt que de dupliquer
cette chaîne pour le spontané, on lui fournit l'offre qu'elle attend : une fiche
de poste plausible, ancrée sur ce que la recherche a réellement trouvé.

Le risque du spontané, c'est le fantasme : inventer un poste qui n'existe pas et
écrire une lettre à côté. D'où la règle imposée au modèle — s'appuyer sur les
faits de la recherche, et rester sur le terrain du « ce que ce rôle impliquerait
ici », jamais du « voici l'offre ».
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .client import cached_system, complete_json
from .company_research import to_prompt_text

logger = logging.getLogger(__name__)

SYSTEM = """Tu prépares une candidature SPONTANÉE : l'entreprise n'a publié aucune offre. À partir d'une fiche de recherche sur l'entreprise et du poste visé par le candidat, tu rédiges la fiche de poste la plus plausible.

RÈGLES
- Appuie-toi UNIQUEMENT sur les faits de la fiche entreprise. N'invente ni client, ni chiffre, ni projet, ni outil qui n'y figure pas.
- Tu décris ce que ce rôle impliquerait CHEZ EUX compte tenu de leur activité et de leur maturité réelle — pas un descriptif générique recopiable pour n'importe quelle boîte.
- Les missions doivent découler de leurs enjeux identifiés. Si leur maturité IA est faible, le poste est un poste de défrichage et tu le dis ; si elle est avancée, le poste s'insère dans l'existant.
- `pitch` : l'angle de la candidature spontanée — pourquoi ce candidat, chez eux, maintenant. Concret, appuyé sur un fait de la fiche.
- Pas de langue de bois, pas de « entreprise en pleine croissance ».

Réponds UNIQUEMENT avec ce JSON :
{
  "title": "string",              // intitulé réaliste du poste, en français, mentionnant l'alternance
  "description": "string",        // 250-400 mots : contexte de la boîte, missions probables, compétences attendues, enjeux du rôle
  "skills": ["string", ...],      // 5-10 compétences clés que ce poste demanderait
  "pitch": "string",              // 2-3 phrases : l'angle d'attaque de la candidature
  "hypotheses": ["string", ...]   // 1-3 hypothèses que tu as faites et que le candidat devra vérifier
}"""


async def build_spontaneous_offer(
    company: dict[str, Any],
    role: str,
    contract: str = "Alternance",
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """Fiche de poste plausible pour une candidature spontanée."""
    fiche = to_prompt_text(company)
    extra = f"\n\nPrécisions du candidat :\n{notes.strip()}" if (notes or "").strip() else ""
    user = f"""{fiche}

Poste visé par le candidat : {role}
Type de contrat : {contract}{extra}

Rédige la fiche de poste plausible et renvoie le JSON."""

    data = await complete_json(cached_system([SYSTEM]), user, max_tokens=2500)
    data.setdefault("title", role)
    data.setdefault("description", "")
    for k in ("skills", "hypotheses"):
        if not isinstance(data.get(k), list):
            data[k] = []
    logger.info(
        "Pseudo-offre spontanée %r chez %r → %d compétences, %d hypothèses",
        data.get("title"), company.get("name"), len(data["skills"]), len(data["hypotheses"]),
    )
    return data


def build_description(company: dict[str, Any], built: dict[str, Any]) -> str:
    """Description stockée sur l'offre : la fiche de poste + le contexte entreprise.

    C'est ce texte que liront le scoring, l'adaptation du CV et la lettre — il doit
    donc contenir les faits de la recherche, sinon la lettre les ignorera.
    """
    parts = [built.get("description") or ""]
    if built.get("pitch"):
        parts.append(f"\n\nAngle de la candidature spontanée :\n{built['pitch']}")
    fiche = to_prompt_text(company)
    if fiche:
        parts.append(f"\n\n--- Contexte entreprise (recherche web) ---\n{fiche}")
    if built.get("hypotheses"):
        parts.append(
            "\n\nHypothèses à vérifier :\n"
            + "\n".join(f"- {h}" for h in built["hypotheses"])
        )
    return "".join(parts)[:20000]
