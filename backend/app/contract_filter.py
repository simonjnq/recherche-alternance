"""Filtre alternance centralisé.

Les scrapers mettent parfois `contract="Alternance"` par défaut faute de mieux, et
certaines sources (Indeed surtout) ne filtrent pas le type de contrat côté requête.
On tranche donc ici, à partir du texte réel (titre + contrat + description), avant
de stocker/scorer : inutile de brûler des appels LLM sur des CDI/stages.

Règle :
- signal positif d'alternance (alternance/apprenti/pro) → on garde, prioritaire ;
- sinon signal négatif net (CDI/CDD/stage/freelance…) → on rejette ;
- ni l'un ni l'autre → on fait confiance aux sources qui ne renvoient QUE de
  l'alternance (filtre appliqué côté requête de la source).
"""
from __future__ import annotations

import re
import unicodedata

from .models import OfferRaw

# Sources dont l'endpoint est filtré "alternance" côté requête : l'absence de
# signal explicite dans le texte ne suffit pas à rejeter (descriptions parfois muettes).
# NB : "apec" en est volontairement ABSENTE — son API ignore le filtre typesContrat
# et renvoie typeContrat=101888 ("Apprentissage") même pour des postes seniors/CDI.
# On ne lui fait donc pas confiance : ses offres passent par l'analyse du texte.
ALTERNANCE_ONLY_SOURCES = {"la_bonne_alternance", "wttj", "hellowork"}

_POS = re.compile(
    r"alternan|apprenti|apprentissage|professionnalisation|contrat\s+pro\b|en\s+alternance|rythme\s+altern",
)
_NEG = re.compile(
    r"\b(cdi|cdd|stage|stagiaire|freelance|free-lance|inter[ie]m|portage)\b",
)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def is_alternance(offer: OfferRaw) -> bool:
    """True si l'offre est (vraisemblablement) une alternance/apprentissage."""
    hay = _norm(f"{offer.title} {offer.contract or ''} {offer.description}")
    if _POS.search(hay):
        return True
    if _NEG.search(hay):
        return False
    return offer.source in ALTERNANCE_ONLY_SOURCES
