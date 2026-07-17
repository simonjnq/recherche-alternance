"""Recherche entreprise : la brique commune à la fiche entreprise, à la
candidature spontanée et à la prépa entretien.

Coûteuse (recherche web facturée + tokens) → TOUJOURS passer par
`get_or_research()`, qui sert le cache DB. Jamais appelée pendant le scraping :
un run ramène ~50 offres dont on en écarte 80 %, les rechercher toutes
reviendrait à payer 50 recherches pour en exploiter 10.

Le piège de cette recherche, c'est l'homonyme : « Kardham » ou « Alegria »
renvoient des boîtes sans rapport. D'où le passage du domaine/URL de l'offre
quand on l'a, et l'obligation faite au modèle de mettre `null` plutôt que de
combler un trou.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import urlparse

from .client import complete_with_search, extract_json

logger = logging.getLogger(__name__)

SCHEMA = """{
  "name": "string",                     // nom officiel
  "website": "string|null",
  "one_liner": "string|null",           // ce qu'ils font, en une phrase claire
  "activity": "string|null",            // 2-4 phrases : métier, marché, clients, modèle
  "size": "string|null",                // effectif (ordre de grandeur suffit)
  "founded": "string|null",
  "funding": "string|null",             // levées, rentabilité, actionnariat — null si rien de public
  "ai_maturity": "string|null",         // où en sont-ils vraiment sur l'IA/l'automatisation ?
  "recent_news": [                      // 0-4 faits datés et vérifiables, du plus récent
    {"date": "string", "title": "string", "source": "string|null"}
  ],
  "culture_values": ["string", ...],    // 0-5, ce qu'ils revendiquent ET ce que les faits montrent
  "hooks": ["string", ...],             // 2-4 angles d'accroche concrets pour une lettre
  "watch_outs": ["string", ...],        // 0-3 points de vigilance honnêtes pour le candidat
  "confidence": "high|medium|low"       // low si tu n'es pas sûr d'être sur la bonne boîte
}"""

SYSTEM = f"""Tu es analyste. Tu recherches une entreprise sur le web pour préparer un candidat qui va postuler chez elle.

RÈGLE ABSOLUE — n'invente RIEN. Une information que tes recherches ne confirment pas vaut `null` ou une liste vide. Un trou assumé est utile ; une invention plausible est un piège qui grillera le candidat en entretien.

Attention aux homonymes : plusieurs entreprises portent le même nom. Si un site ou un domaine t'est donné, c'est LUI qui fait foi. Si tu n'es pas certain d'être sur la bonne entreprise, mets `confidence: "low"` et ne remplis que ce dont tu es sûr.

Ce qu'on attend de toi :
- `activity` : ce qu'ils font réellement, pas leur slogan.
- `ai_maturity` : distingue ce qu'ils annoncent de ce qu'ils ont livré. « Rien de public sur le sujet » est une réponse valable et utile.
- `recent_news` : des faits datés (levée, lancement, rachat, recrutement, ouverture). Pas de généralités.
- `hooks` : des angles précis et vérifiables sur lesquels une lettre peut s'appuyer. Interdits : « entreprise en pleine croissance », « votre renommée », « secteur dynamique » — ce sont des formules creuses qui vont dans toutes les lettres.
- `watch_outs` : sois franc (turnover, avis employés négatifs, levée ancienne, flou sur le poste). Liste vide si rien à signaler.

Réponds UNIQUEMENT avec ce JSON, sans texte autour :
{SCHEMA}"""


def _domain(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        # Les agrégateurs ne disent rien de l'entreprise : leur domaine induirait en erreur.
        if any(x in host for x in ("hellowork", "indeed", "linkedin", "apec",
                                   "welcometothejungle", "labonnealternance", "pole-emploi")):
            return None
        return host or None
    except Exception:
        return None


def normalize_name(name: str) -> str:
    """Clé de cache : « KARDHAM » et « Groupe Kardham » doivent tomber sur la même fiche."""
    n = (name or "").strip().lower()
    for w in ("groupe ", "group ", "sas ", "sarl ", "sa ", "société ", "the "):
        if n.startswith(w):
            n = n[len(w):]
    for w in (" sas", " sarl", " sa", " group", " groupe", " france", " inc", " ltd"):
        if n.endswith(w):
            n = n[: -len(w)]
    return " ".join(n.split())


async def research_company(
    name: str,
    website: Optional[str] = None,
    offer_url: Optional[str] = None,
    context: Optional[str] = None,
) -> dict[str, Any]:
    """Un appel LLM + recherches web. Ne pas appeler directement : cf. get_or_research()."""
    hints = []
    dom = _domain(website) or _domain(offer_url)
    if dom:
        hints.append(f"Site officiel (fait foi) : {dom}")
    if context:
        hints.append(f"Contexte connu (extrait d'une offre d'emploi) :\n{context[:1200]}")
    hint_text = "\n".join(hints) or "Aucun indice supplémentaire."

    user = f"""Entreprise à rechercher : {name}

{hint_text}

Recherche-la sur le web et renvoie le JSON."""

    text, sources = await complete_with_search(SYSTEM, user, max_tokens=4000, max_searches=6)
    data = extract_json(text)
    data.setdefault("name", name)
    data["sources"] = sources
    for k in ("recent_news", "culture_values", "hooks", "watch_outs"):
        if not isinstance(data.get(k), list):
            data[k] = []
    if data.get("confidence") not in ("high", "medium", "low"):
        data["confidence"] = "medium"
    logger.info(
        "Recherche entreprise %r → confidence=%s, %d sources, %d actus",
        name, data["confidence"], len(sources), len(data["recent_news"]),
    )
    return data


async def get_or_research(
    db: Any,
    name: str,
    website: Optional[str] = None,
    offer_url: Optional[str] = None,
    context: Optional[str] = None,
    force: bool = False,
) -> dict[str, Any]:
    """Point d'entrée unique : sert le cache, ne recherche qu'au premier passage.

    `force=True` pour rafraîchir une fiche (l'actu d'une boîte vieillit).
    """
    from .. import db as dbm

    key = normalize_name(name)
    if not key:
        raise ValueError("Nom d'entreprise vide")
    if not force:
        cached = await dbm.get_company(db, key)
        if cached:
            cached["cached"] = True
            return cached
    data = await research_company(name, website=website, offer_url=offer_url, context=context)
    await dbm.upsert_company(db, key, data.get("name") or name, data.get("website"), data)
    data["cached"] = False
    return data


def to_prompt_text(data: dict[str, Any]) -> str:
    """Aplatit la fiche pour l'injecter dans un prompt (lettre, entretien)."""
    if not data:
        return ""
    lines = [f"FICHE ENTREPRISE — {data.get('name')}"]
    if data.get("confidence") == "low":
        lines.append("(fiabilité faible : à ne citer qu'avec prudence)")
    for label, key in (
        ("Activité", "activity"), ("Effectif", "size"), ("Création", "founded"),
        ("Financement", "funding"), ("Maturité IA", "ai_maturity"),
    ):
        if data.get(key):
            lines.append(f"- {label} : {data[key]}")
    for label, key in (("Valeurs revendiquées", "culture_values"), ("Angles d'accroche", "hooks")):
        if data.get(key):
            lines.append(f"- {label} : " + " ; ".join(str(x) for x in data[key]))
    if data.get("recent_news"):
        lines.append("- Actualités récentes :")
        for n in data["recent_news"]:
            lines.append(f"    · {n.get('date', '')} {n.get('title', '')}".rstrip())
    return "\n".join(lines)
