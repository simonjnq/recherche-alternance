"""Extracteur de profil structuré à partir d'un CV HTML.

Un seul appel LLM au moment de l'upload : on transforme le HTML du CV en JSON
exploitable (nom, contact, intro, expériences, formation, skills, projets,
langues). Ensuite le profil structuré sert de "source de vérité" textuelle pour
la rédaction CV/lettre — au lieu de re-parser du HTML à chaque génération.

Sortie schématique :
{
  "name": "...",
  "contact": {"email": "...", "phone": "...", "linkedin": "...", "location": "..."},
  "intro": "phrase de positionnement (si présente)",
  "experiences": [
    {"company": "...", "role": "...", "period": "...", "location": "...",
     "bullets": ["...", "..."], "skills": ["..."]}
  ],
  "formations": [{"degree": "...", "school": "...", "period": "...", "details": "..."}],
  "hard_skills": ["..."],
  "soft_skills": ["..."],
  "tools": ["..."],
  "projects": [{"name": "...", "summary": "...", "url": "..."}],
  "languages": [{"name": "...", "level": "..."}],
  "achievements": ["réalisation 1", "..."]
}

Pas de HTML, pas de Markdown : du texte brut dans les champs.
"""
from __future__ import annotations

import logging
from typing import Any

from .client import complete_json

logger = logging.getLogger(__name__)

SYSTEM = """Tu reçois un CV en HTML. Extrais-en un profil structuré en JSON suivant ce schéma exact :

{
  "name": "string",
  "contact": {"email": "string|null", "phone": "string|null", "linkedin": "string|null", "location": "string|null"},
  "intro": "string|null",                              // phrase d'auto-présentation si présente
  "experiences": [{
    "company": "string", "role": "string", "period": "string",
    "location": "string|null",
    "bullets": ["string", ...],                        // 2-6 bullets factuels
    "skills": ["string", ...]                          // outils/méthodes utilisés sur ce poste
  }],
  "formations": [{
    "degree": "string", "school": "string", "period": "string", "details": "string|null"
  }],
  "hard_skills": ["string", ...],                      // compétences techniques (outils, langages)
  "soft_skills": ["string", ...],
  "tools": ["string", ...],                            // outils/stack (peut recouper hard_skills)
  "projects": [{"name": "string", "summary": "string", "url": "string|null"}],
  "languages": [{"name": "string", "level": "string|null"}],
  "achievements": ["string", ...]                      // réussites concrètes signatures (chiffrées si possible)
}

Règles :
- Extrais TOUT le contenu utile du CV. Ne paraphrase pas — garde la formulation candidate.
- Pas d'invention : si un champ est absent du CV, mets null (ou liste vide pour les arrays).
- Les bullets sont des phrases courtes, action + impact si dispo.
- L'intro doit être la phrase d'auto-présentation si elle existe ; sinon null.
- Le champ achievements regroupe les bullets/phrases les plus impactantes (chiffrées, livrées, mesurables) — entre 2 et 6 entrées."""


async def ensure_structured_profile(db: Any, cv: Any) -> dict[str, Any]:
    """Renvoie le profil structuré du CV, l'extrait + le stocke si absent.

    `db` est un aiosqlite.Connection, `cv` un models.CV. On évite l'import direct
    pour éviter une dépendance circulaire au démarrage des modules.
    """
    from .. import db as dbm  # local import
    existing = await dbm.get_cv_structured(db, cv.id)
    if existing:
        return existing
    structured = await extract_profile(cv.html_content)
    try:
        await dbm.set_cv_structured(db, cv.id, structured)
    except Exception as e:
        logger.warning("Failed to store extracted profile for CV %s: %s", cv.id, e)
    return structured


async def extract_profile(cv_html: str) -> dict[str, Any]:
    """Renvoie le profil structuré. Lève l'exception en cas d'échec JSON."""
    user = f"""CV à structurer :

{cv_html[:16000]}

Renvoie UNIQUEMENT le JSON conforme au schéma."""
    data = await complete_json(system=SYSTEM, user=user, max_tokens=4000)
    return _normalize(data)


def _normalize(data: Any) -> dict[str, Any]:
    """Garde-fou : applique le schéma même si le LLM omet/ajoute des champs."""
    if not isinstance(data, dict):
        return _empty()
    out = _empty()
    out["name"] = str(data.get("name") or "").strip() or None
    contact = data.get("contact") or {}
    if isinstance(contact, dict):
        out["contact"] = {
            "email": _str_or_none(contact.get("email")),
            "phone": _str_or_none(contact.get("phone")),
            "linkedin": _str_or_none(contact.get("linkedin")),
            "location": _str_or_none(contact.get("location")),
        }
    out["intro"] = _str_or_none(data.get("intro"))
    out["experiences"] = _list_of_objs(data.get("experiences"), {
        "company": "", "role": "", "period": "",
        "location": None, "bullets": [], "skills": [],
    })
    out["formations"] = _list_of_objs(data.get("formations"), {
        "degree": "", "school": "", "period": "", "details": None,
    })
    out["hard_skills"] = _list_of_str(data.get("hard_skills"))
    out["soft_skills"] = _list_of_str(data.get("soft_skills"))
    out["tools"] = _list_of_str(data.get("tools"))
    out["projects"] = _list_of_objs(data.get("projects"), {
        "name": "", "summary": "", "url": None,
    })
    out["languages"] = _list_of_objs(data.get("languages"), {"name": "", "level": None})
    out["achievements"] = _list_of_str(data.get("achievements"))
    return out


def _empty() -> dict[str, Any]:
    return {
        "name": None,
        "contact": {"email": None, "phone": None, "linkedin": None, "location": None},
        "intro": None,
        "experiences": [],
        "formations": [],
        "hard_skills": [],
        "soft_skills": [],
        "tools": [],
        "projects": [],
        "languages": [],
        "achievements": [],
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
        merged = {**defaults}
        for k in defaults:
            if k in item:
                if isinstance(defaults[k], list):
                    merged[k] = _list_of_str(item[k])
                else:
                    merged[k] = _str_or_none(item[k]) if defaults[k] is None else str(item[k] or "").strip()
        out.append(merged)
    return out


# ----------- formatage texte pour injection dans les prompts -----------

def profile_to_text(profile: dict[str, Any]) -> str:
    """Renders le profil structuré en texte compact pour usage dans un prompt."""
    lines: list[str] = []
    if profile.get("name"):
        lines.append(f"Nom : {profile['name']}")
    contact = profile.get("contact") or {}
    contact_bits = [contact.get(k) for k in ("email", "phone", "linkedin", "location") if contact.get(k)]
    if contact_bits:
        lines.append("Contact : " + " · ".join(contact_bits))
    if profile.get("intro"):
        lines.append(f"\nIntro / positionnement :\n{profile['intro']}")

    if profile.get("experiences"):
        lines.append("\nExpériences :")
        for e in profile["experiences"]:
            head = f"- {e.get('role') or 'Poste'} @ {e.get('company') or '—'} ({e.get('period') or '—'})"
            loc = e.get("location")
            if loc:
                head += f" — {loc}"
            lines.append(head)
            for b in (e.get("bullets") or [])[:6]:
                lines.append(f"  • {b}")
            if e.get("skills"):
                lines.append(f"  → outils : {', '.join(e['skills'][:10])}")

    if profile.get("formations"):
        lines.append("\nFormations :")
        for f in profile["formations"]:
            lines.append(
                f"- {f.get('degree') or 'Diplôme'} · {f.get('school') or '—'} · {f.get('period') or '—'}"
            )
            if f.get("details"):
                lines.append(f"  {f['details']}")

    if profile.get("hard_skills"):
        lines.append("\nHard skills : " + ", ".join(profile["hard_skills"][:20]))
    if profile.get("tools"):
        lines.append("Outils : " + ", ".join(profile["tools"][:20]))
    if profile.get("soft_skills"):
        lines.append("Soft skills : " + ", ".join(profile["soft_skills"][:12]))

    if profile.get("projects"):
        lines.append("\nProjets :")
        for p in profile["projects"]:
            name = p.get("name") or "Projet"
            summary = p.get("summary") or ""
            url = p.get("url")
            lines.append(f"- {name} — {summary}" + (f" ({url})" if url else ""))

    if profile.get("languages"):
        lang_bits = [
            f"{l.get('name')}" + (f" ({l.get('level')})" if l.get("level") else "")
            for l in profile["languages"]
            if l.get("name")
        ]
        if lang_bits:
            lines.append("\nLangues : " + ", ".join(lang_bits))

    if profile.get("achievements"):
        lines.append("\nRéalisations signatures :")
        for a in profile["achievements"][:8]:
            lines.append(f"- {a}")

    return "\n".join(lines).strip()
