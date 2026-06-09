"""Convertit un CV HTML adapté à une offre en JSON éditable pour l'éditeur visuel.

Différent de `cv_profile.extract_profile` (qui produit un profil candidat générique
depuis le CV source). Ici on cible le CV DÉJÀ ADAPTÉ stocké dans `offers/<slug>/cv.html` :
on veut récupérer le titre adapté, l'intro adaptée, l'ordre/contenu déjà retravaillés.

Utilise Haiku pour rester cheap (cette extraction est faite 1x par CV adapté).
"""
from __future__ import annotations

import logging
import re
from typing import Any

from .client import complete_json

logger = logging.getLogger(__name__)

SYSTEM = """On te donne un CV HTML déjà adapté à une offre d'alternance. Extrais-en un JSON éditable selon ce schéma exact :

{
  "name": "string",
  "role": "string|null",                        // titre adapté sous le nom (ex: "Alternance Growth & Automatisation")
  "contact": {"email": "string|null", "phone": "string|null", "linkedin": "string|null", "location": "string|null"},
  "intro": "string|null",                       // phrase d'intro adaptée à l'offre
  "hard_skills": ["string", ...],
  "soft_skills": ["string", ...],
  "tools": ["string", ...],                     // section Stack & Outils
  "languages": [{"name": "string", "level": "string|null"}],
  "formations": [{"degree": "string", "school": "string", "period": "string"}],
  "experiences": [{
    "company": "string", "role": "string", "period": "string",
    "bullets": ["string", ...]
  }],
  "projects_pedagogical": [{"name": "string", "summary": "string"}],
  "projects_personal": [{"name": "string", "summary": "string"}]
}

Règles :
- Extrais EXACTEMENT le contenu visible. Ne paraphrase pas, ne corrige pas.
- Si la section pédago/personnel n'est pas distincte, mets les projets en "projects_pedagogical".
- Pour le champ `role` (sidebar sous le nom), cherche un .role / div sous H1.
- Si une section est absente, mets [] ou null. Pas d'invention.
- Pas de balises HTML dans les valeurs textuelles."""


def _strip_for_extraction(html: str) -> str:
    """Retire le CSS / head / scripts / styles inline pour ne garder que la
    structure + le texte. Sinon le contenu réel (nom, expériences) se retrouve
    au-delà de la troncature et le LLM ne voit que du CSS → JSON vide."""
    s = re.sub(r"<head[^>]*>.*?</head>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r"<style[^>]*>.*?</style>", " ", s, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r"<script[^>]*>.*?</script>", " ", s, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.DOTALL)
    s = re.sub(r'\sstyle="[^"]*"', "", s)          # attributs style inline (volumineux)
    s = re.sub(r"\sclass=\"[^\"]*\"", "", s)         # classes (inutiles pour l'extraction)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


async def extract_editable(cv_html: str) -> dict[str, Any]:
    content = _strip_for_extraction(cv_html)
    user = f"""CV HTML à structurer :

{content[:18000]}

Renvoie UNIQUEMENT le JSON conforme."""
    data = await complete_json(
        system=SYSTEM,
        user=user,
        max_tokens=4000,
        model="claude-haiku-4-5-20251001",
    )
    return _normalize(data)


def _normalize(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return _empty()
    out = _empty()
    out["name"] = _str_or_none(data.get("name"))
    out["role"] = _str_or_none(data.get("role"))
    contact = data.get("contact") or {}
    if isinstance(contact, dict):
        out["contact"] = {
            "email": _str_or_none(contact.get("email")),
            "phone": _str_or_none(contact.get("phone")),
            "linkedin": _str_or_none(contact.get("linkedin")),
            "location": _str_or_none(contact.get("location")),
        }
    out["intro"] = _str_or_none(data.get("intro"))
    out["hard_skills"] = _list_of_str(data.get("hard_skills"))[:8]
    out["soft_skills"] = _list_of_str(data.get("soft_skills"))[:5]
    out["tools"] = _list_of_str(data.get("tools"))[:12]
    out["languages"] = _list_of_objs(data.get("languages"), {"name": "", "level": None})
    out["formations"] = _list_of_objs(data.get("formations"), {"degree": "", "school": "", "period": ""})
    out["experiences"] = _list_of_objs(data.get("experiences"), {
        "company": "", "role": "", "period": "", "bullets": [],
    })
    out["projects_pedagogical"] = _list_of_objs(
        data.get("projects_pedagogical"), {"name": "", "summary": ""}
    )
    out["projects_personal"] = _list_of_objs(
        data.get("projects_personal"), {"name": "", "summary": ""}
    )
    return out


def _empty() -> dict[str, Any]:
    return {
        "name": None, "role": None,
        "contact": {"email": None, "phone": None, "linkedin": None, "location": None},
        "intro": None,
        "hard_skills": [], "soft_skills": [], "tools": [],
        "languages": [], "formations": [], "experiences": [],
        "projects_pedagogical": [], "projects_personal": [],
    }


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _list_of_str(v: Any) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if isinstance(x, (str, int, float)) and str(x).strip()]


def _list_of_objs(v: Any, defaults: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(v, list):
        return []
    out: list[dict[str, Any]] = []
    for item in v:
        if not isinstance(item, dict):
            continue
        merged: dict[str, Any] = {**defaults}
        for k in defaults:
            if k in item:
                if isinstance(defaults[k], list):
                    merged[k] = _list_of_str(item[k])
                elif defaults[k] is None:
                    merged[k] = _str_or_none(item[k])
                else:
                    merged[k] = str(item[k] or "").strip()
        out.append(merged)
    return out


# --- Inférence rapide des styles depuis le HTML existant (couleur accent, photo) ---

ACCENT_RE = re.compile(r"--accent\s*:\s*(#[0-9a-fA-F]{3,6})|color:\s*(#2d52c4)|background:\s*(#2d52c4)")


def detect_style(cv_html: str) -> dict[str, Any]:
    """Tente de détecter accent_color / font / photo depuis le HTML existant.

    Heuristique simple : on cherche --accent dans le body inline, sinon la couleur
    historique #2d52c4. Si pas de match, on garde le défaut.
    """
    accent = None
    m = re.search(r"--accent\s*:\s*(#[0-9a-fA-F]{3,6})", cv_html)
    if m:
        accent = m.group(1)
    elif "#2d52c4" in cv_html:
        accent = "#2d52c4"
    font = "Poppins"
    if "Inter" in cv_html and "Poppins" not in cv_html:
        font = "Inter"
    elif "Manrope" in cv_html and "Poppins" not in cv_html:
        font = "Manrope"
    photo_enabled = ('background-image:url(' in cv_html.replace(" ", ""))
    return {
        "accent_color": accent or "#2d52c4",
        "font": font,
        "density": 1.0,
        "photo_enabled": True,  # défaut : on rebranche la photo si dispo
    }
