"""Édition de CV/lettre via instructions naturelles de l'utilisateur.

L'utilisateur voit son CV/lettre et écrit "raccourcis la partie projets",
"ajoute une ligne sur mon expérience chez X", etc. On envoie le document
courant + l'instruction à Claude, qui renvoie la version modifiée.
"""
from __future__ import annotations

import logging

from ..text_clean import strip_long_dashes
from .client import complete

logger = logging.getLogger(__name__)

CV_SYSTEM = """Tu es un expert en édition de CV pour alternance.

On te donne :
1. Un CV en HTML (structure à préserver absolument)
2. Une instruction de modification en français

Ta tâche : appliquer l'instruction au CV et renvoyer la nouvelle version HTML.

Règles impératives :
- Applique UNIQUEMENT ce qui est demandé. Ne touche pas au reste.
- GARDE la structure HTML (balises, classes, styles inline) sauf si l'instruction le demande explicitement.
- Ne mens PAS : n'invente pas d'expérience, de diplôme, de compétence. Si l'instruction le demande, refuse poliment dans un commentaire HTML en tête (<!-- refus: … -->) mais produis quand même une version cohérente.
- Préserve les infos factuelles (dates, noms, écoles) sauf si l'instruction demande de les modifier.
- Réponds avec UNIQUEMENT le HTML complet résultant. Aucun commentaire hors du HTML. Pas de ```html."""


LETTER_SYSTEM = """Tu es un expert en rédaction de lettres de motivation pour alternance.

On te donne :
1. Une lettre en markdown
2. Une instruction de modification en français

Ta tâche : appliquer l'instruction à la lettre et renvoyer la nouvelle version markdown.

Règles impératives :
- Applique UNIQUEMENT ce qui est demandé.
- Garde le ton français professionnel, chaleureux mais précis.
- Reste dans la fourchette 250-400 mots sauf si l'instruction demande autrement.
- Ne mens pas : n'invente pas d'expérience ou de compétence non mentionnée.
- Structure en 3 paragraphes (pourquoi l'entreprise / ce que j'apporte / call-to-action) sauf instruction contraire.
- Réponds avec UNIQUEMENT le markdown. Pas de ```markdown, pas de commentaire autour."""


async def apply_instructions_to_cv(cv_html: str, instruction: str) -> str:
    user = f"""CV actuel (HTML) :
{cv_html}

---

Instruction de modification :
{instruction}

Produis la nouvelle version HTML du CV."""
    result = await complete(
        system=CV_SYSTEM,
        user=user,
        max_tokens=8000,
        temperature=0.3,
    )
    return strip_long_dashes(_strip_fence(result, "html"))


async def apply_instructions_to_letter(letter_md: str, instruction: str) -> str:
    user = f"""Lettre actuelle (markdown) :
{letter_md}

---

Instruction de modification :
{instruction}

Produis la nouvelle version markdown de la lettre."""
    result = await complete(
        system=LETTER_SYSTEM,
        user=user,
        max_tokens=3000,
        temperature=0.4,
    )
    return strip_long_dashes(_strip_fence(result, "markdown"))


def _strip_fence(text: str, lang_hint: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        for lang in (lang_hint, "html", "markdown", "md"):
            if t.lower().startswith(lang):
                t = t[len(lang):]
                break
        t = t.rsplit("```", 1)[0].strip()
    return t
