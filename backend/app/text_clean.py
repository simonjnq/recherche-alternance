"""Nettoyage des descriptions scrapées avant scoring/génération.

Chaque source ajoute son propre bruit (boilerplate cookie, "voir d'autres offres",
footer SEO, etc.). On veut isoler la VRAIE description sans rogner sur le contenu.

Stratégie générique :
- normaliser les sauts de ligne et espaces
- couper tout ce qui précède le premier marqueur "début de contenu" (variable selon source)
- couper tout ce qui suit le premier marqueur "fin de contenu"
- supprimer lignes de cookies, "se connecter", "voir l'offre", etc.

Idempotent — appliquer plusieurs fois ne change rien après la 1ʳᵉ passe.
"""
from __future__ import annotations

import re
from typing import Iterable

# -- Marqueurs de DÉBUT (on garde tout ce qui suit le 1er match) --
START_MARKERS = {
    "hellowork": [
        r"Détail\s+du\s+poste",
        r"Description\s+(?:du\s+poste|de\s+l'offre)",
        r"Le\s+job\b",
    ],
    "indeed": [
        r"Description\s+du\s+poste",
        r"Profil\s+recherché",
    ],
    "apec": [
        r"Description\s+du\s+poste",
        r"Missions",
    ],
    "wttj": [
        r"Descriptif\s+du\s+poste",
        r"Le\s+poste",
        r"Missions",
    ],
    "la_bonne_alternance": [],
    "linkedin_manual": [
        r"À\s+propos\s+du\s+poste",
        r"Description\s+du\s+poste",
    ],
}

# -- Marqueurs de FIN (on coupe à partir du 1er match) --
END_MARKERS = {
    "hellowork": [
        r"Ces\s+offres\s+pourraient\s+aussi\s+vous\s+intéresser",
        r"Recherches\s+similaires",
        r"Cr[ée]ez\s+votre\s+compte\s+Hellowork",
        r"Voir\s+plus\s+d'?offres",
        r"^Accueil\s*\n",
        r"Publiée\s+le\s+\d",
        r"Les\s+apps\b",
    ],
    "indeed": [
        r"Postuler\s+(?:directement\s+)?sur\s+le\s+site",
        r"Offres\s+similaires",
        r"Indeed\s+est\s+un",
    ],
    "apec": [
        r"Offres\s+similaires",
        r"Postuler\s+sur\s+le\s+site",
    ],
    "wttj": [
        r"Découvrir\s+toutes\s+les\s+offres",
        r"D'autres\s+offres",
    ],
    "la_bonne_alternance": [],
    "linkedin_manual": [
        r"Connectez-vous\s+pour\s+enregistrer",
        r"Postes\s+similaires",
    ],
}

# Lignes courtes à supprimer (boilerplate, navigation, etc.)
LINE_BLACKLIST = [
    re.compile(r"^se\s+connecter\b.*", re.IGNORECASE),
    re.compile(r"^continuer\s+avec\s+google\b.*", re.IGNORECASE),
    re.compile(r"^(en\s+poursuivant|en\s+vous\s+inscrivant).*", re.IGNORECASE),
    re.compile(r"^postuler(?:\s+sur\s+le\s+site\s+du\s+recruteur)?$", re.IGNORECASE),
    re.compile(r"^voir\s+l['’]?offre$", re.IGNORECASE),
    re.compile(r"^il\s+y\s+a\s+\d+\s+jours?$", re.IGNORECASE),
    re.compile(r"^bac\s*\+\s*\d.*", re.IGNORECASE),  # garder si en contexte ? souvent juste tag
    re.compile(r"^cgu\b.*", re.IGNORECASE),
    re.compile(r"^politique\s+de\s+confidentialité.*", re.IGNORECASE),
    re.compile(r"^accessibilité\s*:.*", re.IGNORECASE),
    re.compile(r"^aide\s+et\s+contact$", re.IGNORECASE),
    re.compile(r"^(qui\s+sommes-?nous|on\s+recrute|nous\s+suivre).*", re.IGNORECASE),
    re.compile(r"^offre\s+emploi\b.*", re.IGNORECASE),
    re.compile(r"^entreprises\s+\w", re.IGNORECASE),
    re.compile(r"^alternance\s+\w+$", re.IGNORECASE),
    re.compile(r"^accueil$", re.IGNORECASE),
    re.compile(r"^\d+\s+de\s+plus$", re.IGNORECASE),
    re.compile(r"^en\s+images?$", re.IGNORECASE),
]


def _normalize(text: str) -> str:
    """Sauts de ligne unifiés, lignes trim, lignes vides multiples → simple."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    lines = [l.strip() for l in text.split("\n")]
    out: list[str] = []
    blank = False
    for l in lines:
        if not l:
            if not blank:
                out.append("")
            blank = True
        else:
            out.append(l)
            blank = False
    return "\n".join(out).strip()


def _apply_markers(text: str, patterns: Iterable[str], where: str) -> str:
    """Coupe le texte autour du premier marqueur trouvé.

    where == 'start' → garde ce qui suit le marqueur (inclusif sur le marqueur).
    where == 'end'   → garde ce qui précède le marqueur.
    Si aucun marqueur ne matche → texte inchangé.
    """
    best: tuple[int, re.Match] | None = None
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE | re.MULTILINE):
            if best is None or m.start() < best[0]:
                best = (m.start(), m)
    if not best:
        return text
    _, m = best
    if where == "start":
        return text[m.start():]
    return text[: m.start()]


def _strip_blacklist_lines(text: str) -> str:
    out = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        if any(pat.match(stripped) for pat in LINE_BLACKLIST):
            continue
        out.append(line)
    # éviter d'avoir trop de blancs en chaîne après suppression
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(out))
    return cleaned.strip()


def clean_description(text: str, source: str | None = None) -> str:
    """Retourne une description nettoyée. Robuste : si rien à nettoyer, renvoie l'original."""
    if not text:
        return text
    src = (source or "").lower()
    t = _normalize(text)

    # 1. fin (couper le footer en premier — réduit la zone à analyser pour la suite)
    end_patterns = END_MARKERS.get(src, [])
    if end_patterns:
        t = _apply_markers(t, end_patterns, where="end")

    # 2. début (sauter le boilerplate cookie/connexion)
    start_patterns = START_MARKERS.get(src, [])
    if start_patterns:
        t = _apply_markers(t, start_patterns, where="start")

    # 3. lignes blacklistées (cookies, navigation, etc.)
    t = _strip_blacklist_lines(t)

    # 4. resserrer les blancs finaux
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t


def clean_offer_title(title: str) -> str:
    """Normalise le titre d'offre (Hellowork colle parfois l'entreprise après un \\n)."""
    if not title:
        return title
    # garder uniquement la 1ʳᵉ ligne significative
    lines = [l.strip() for l in title.replace("\r", "\n").split("\n") if l.strip()]
    return lines[0] if lines else title.strip()


def strip_long_dashes(text: str) -> str:
    """Retire les tirets longs (— em, – en) que le LLM remet malgré les consignes.
    En prose ' — ' devient ', ' ; un tiret accolé (ex. dates 2024–2026) devient '-'."""
    if not text:
        return text
    t = re.sub(r"\s+[—–]\s+", ", ", text)   # « mot — mot » → « mot, mot »
    t = t.replace("—", "-").replace("–", "-")  # restants (dates, accolés)
    t = re.sub(r",\s*,", ",", t)
    return t
