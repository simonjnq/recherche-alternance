"""Filtre de pertinence au scrape (mode "équilibré").

Les sources qui cherchent par mot-clé (ou pire, WTTJ qui scrape une page
alternance générique) ramènent beaucoup d'alternances hors-sujet : sales,
finance, RH, juridique, dev générique… On les écarte AVANT scoring (pas d'appel
LLM gaspillé) selon une règle équilibrée :

- un token DISTINCTIF du domaine (ia/llm/growth/automation/no-code/scraping…) → pertinent ;
- une EXPRESSION distinctive ("machine learning", "data scientist"…) → pertinent ;
- sinon, au moins 2 tokens GÉNÉRIQUES orientés data/produit/automation → pertinent ;
- en dernier recours, un mot-clé multi-mots du profil présent tel quel → pertinent.

L'idée : garder le cœur IA/automation/growth + les rôles data/produit, sans
laisser passer le bruit sales/RH/finance qui ne contient qu'un mot générique isolé.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional

from .models import OfferRaw

# Tokens forts : signal direct du domaine. Match sur mot entier (après normalisation).
# "agent"/"ai" volontairement ABSENTS (trop de faux positifs : agent commercial,
# "j'ai" → "ai") — on les capte via les expressions fortes ci-dessous.
_STRONG_WORDS = {
    "ia", "llm", "llms", "genai", "growth", "prompt", "prompts", "nocode",
    "scraping", "mlops", "nlp", "rag", "chatbot", "gpt", "n8n", "zapier",
    "airtable", "agentic", "datascientist", "automatisation", "automation",
    "automatisations", "copilot",
}

# Expressions fortes : match sous-chaîne (sûres car longues / spécifiques).
_STRONG_PHRASES = (
    "intelligence artificielle", "machine learning", "deep learning",
    "no-code", "no code", "low-code", "low code", "gen ai",
    "ai engineer", "ai agent", "ai automation", "agent ia", "agents ia",
    "agent llm", "ml engineer", "data scientist", "data engineer",
    "data analyst", "data science", "prompt engineer", "growth engineer",
    "growth marketing", "growth hacker", "product manager", "product builder",
    "business analyst", "ingenieur ia", "ingenieur data",
)

# Tokens génériques orientés data/produit/automation : pertinents en combo (>= 2 distincts).
_GENERIC = {
    "data", "donnees", "dataset", "datasets", "analytics", "analyste", "analyst",
    "product", "produit", "automatis", "digital", "saas", "etl", "bi",
    "python", "sql", "model", "modele", "modeles",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def is_relevant(
    offer: OfferRaw,
    keywords: Optional[Iterable[str]] = None,
    extra_strong: Optional[Iterable[str]] = None,
    excluded: Optional[Iterable[str]] = None,
) -> bool:
    """True si l'offre est dans le domaine ciblé (IA/automation/growth/data/produit).

    `extra_strong` : mots/expressions "forts" supplémentaires (réglés par l'utilisateur).
    `excluded` : mots qui, s'ils apparaissent, écartent l'offre (override).
    """
    text = _norm(f"{offer.title} {offer.description}")

    # Exclusions utilisateur : priorité absolue
    for ex in (excluded or []):
        ne = _norm(ex)
        if ne and ne in text:
            return False

    tokens = {t for t in re.split(r"[^a-z0-9]+", text) if t}

    if tokens & _STRONG_WORDS:
        return True
    if any(p in text for p in _STRONG_PHRASES):
        return True
    # Mots forts supplémentaires de l'utilisateur (sous-chaîne, insensible accents/casse)
    for s in (extra_strong or []):
        ns = _norm(s)
        if ns and ns in text:
            return True
    if len(tokens & _GENERIC) >= 2:
        return True
    if keywords:
        for kw in keywords:
            nk = _norm(kw)
            if " " in nk and len(nk) >= 7 and nk in text:
                return True
    return False
