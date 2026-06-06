from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import markdown as md_lib
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse, Response

from .. import db as dbm
from ..cv_render import list_templates, render_cv
from ..llm.cv_fit import fit_cv_html
from ..llm.cv_profile import profile_to_text
from ..llm.cv_to_editable import detect_style, extract_editable
from ..llm.doc_editor import apply_instructions_to_cv, apply_instructions_to_letter
from ..llm.client import complete, complete_json
from ..pipeline import regenerate_for_offer
from ..render_pdf import html_to_pdf

router = APIRouter(prefix="/api/offers", tags=["offers"])

# Templates registry (publique pour le picker UI)
templates_router = APIRouter(prefix="/api/cv-templates", tags=["cv-templates"])


@templates_router.get("")
async def get_templates() -> list[dict]:
    return list_templates()


@templates_router.get("/inspirations")
async def get_inspirations(limit: int = 60) -> dict:
    """Galerie d'inspirations CV (scrap d'enhancv + novoresume avec cache 1h)."""
    from ..cv_inspirations import fetch_inspirations
    items = await fetch_inspirations(limit=limit)
    return {"items": items}


@templates_router.post("/clone-style")
async def clone_style(payload: dict = Body(...)) -> dict:
    """Vision : extrait un style applicable depuis l'URL d'une image de CV."""
    from ..llm.style_from_image import style_from_image
    image_url = (payload.get("image_url") or "").strip()
    if not image_url:
        raise HTTPException(400, "Champ 'image_url' manquant")
    try:
        style = await style_from_image(image_url=image_url)
    except Exception as e:
        raise HTTPException(500, f"Analyse Vision échouée : {e}") from e
    return {"style": style}


def _slugify(title: str) -> str:
    import re
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (title or "doc").lower()).strip("-")
    return s[:60] or "doc"


async def _require_docs(offer_id: int):
    db = await dbm.connect()
    try:
        docs = await dbm.get_docs_for_offer(db, offer_id)
        if not docs:
            raise HTTPException(404, "Documents non générés pour cette offre")
        offer = await dbm.get_offer(db, offer_id)
        return docs, offer
    finally:
        await db.close()


LETTER_PDF_TEMPLATE = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><style>
  @page {{ size: A4; margin: 0; }}
  body {{ font-family: -apple-system, 'Segoe UI', Inter, Helvetica, Arial, sans-serif;
          color: #111; line-height: 1.55; font-size: 11.5pt;
          padding: 24mm 22mm; margin: 0; }}
  h1, h2, h3 {{ margin: 0 0 0.6em; }}
  p {{ margin: 0 0 0.8em; }}
  strong {{ font-weight: 600; }}
  em {{ font-style: italic; }}
  ul, ol {{ margin: 0 0 0.8em 1.2em; padding: 0; }}
  li {{ margin-bottom: 0.2em; }}
</style></head><body>{body}</body></html>
"""


@router.get("")
async def list_offers(
    min_score: int = 0,
    favorites_only: bool = False,
    source: Optional[str] = None,
    search: Optional[str] = None,
    new_only: bool = False,
    sort: str = "score",
    generated: Optional[bool] = None,
    contract: Optional[str] = None,
    location: Optional[str] = None,
    days_max: Optional[int] = None,
    limit: int = Query(500, le=2000),
) -> list[dict]:
    db = await dbm.connect()
    try:
        offers = await dbm.list_offers(
            db, min_score, favorites_only, source, search, new_only,
            sort=sort, generated=generated, contract=contract,
            location=location, days_max=days_max, limit=limit,
        )
        return [o.model_dump(mode="json") for o in offers]
    finally:
        await db.close()


@router.post("/cleanup")
async def cleanup(mode: str = "old", days: int = 30) -> dict:
    """Masque en masse les offres anciennes ('old') ou non scorées ('unscored')."""
    db = await dbm.connect()
    try:
        n = await dbm.cleanup_offers(db, mode=mode, days=days)
        return {"ok": True, "hidden": n}
    finally:
        await db.close()


_STATUS_LABELS = {
    "to_apply": "À postuler", "applied": "Postulé", "interview": "Entretien",
    "accepted": "Retenu", "rejected": "Non retenu",
}


@router.get("/export.csv")
async def export_csv(favorites_only: bool = True) -> Response:
    """Exporte les offres (favoris par défaut) en CSV pour suivi hors-ligne."""
    import csv
    import io

    db = await dbm.connect()
    try:
        offers = await dbm.list_offers(db, favorites_only=favorites_only, limit=2000)
    finally:
        await db.close()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Titre", "Entreprise", "Lieu", "Source", "Score", "Étape",
        "Postulé le", "Relance prévue", "Contact", "Notes", "URL",
    ])
    for o in offers:
        w.writerow([
            o.title, o.company or "", o.location or "", o.source, o.score,
            _STATUS_LABELS.get(o.application_status or "to_apply", ""),
            o.applied_at or "", o.follow_up_at or "", o.contact or "",
            (o.notes or "").replace("\n", " "), o.url,
        ])
    csv_bytes = ("﻿" + buf.getvalue()).encode("utf-8")  # BOM → Excel ouvre l'UTF-8
    return Response(
        csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="candidatures.csv"'},
    )


@router.get("/{offer_id}")
async def get_offer(offer_id: int) -> dict:
    db = await dbm.connect()
    try:
        offer = await dbm.get_offer(db, offer_id)
        if not offer:
            raise HTTPException(404, "Offre introuvable")
        if not offer.seen:
            await dbm.mark_seen(db, offer_id)  # ouvrir le détail = marquer vu
        docs = await dbm.get_docs_for_offer(db, offer_id)
        return {
            "offer": offer.model_dump(mode="json"),
            "docs": docs.model_dump(mode="json") if docs else None,
        }
    finally:
        await db.close()


@router.post("/{offer_id}/favorite")
async def toggle_favorite(offer_id: int, value: bool = True) -> dict:
    db = await dbm.connect()
    try:
        await dbm.set_favorite(db, offer_id, value)
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{offer_id}/hide")
async def hide_offer(offer_id: int) -> dict:
    db = await dbm.connect()
    try:
        await dbm.hide_offer(db, offer_id)
        return {"ok": True}
    finally:
        await db.close()


@router.post("/reorder")
async def reorder(payload: dict = Body(...)) -> dict:
    """Réordonne une colonne du board : payload {ordered_ids:[...]}."""
    ids = payload.get("ordered_ids") or []
    if not isinstance(ids, list):
        raise HTTPException(400, "ordered_ids doit être une liste")
    db = await dbm.connect()
    try:
        await dbm.reorder_offers(db, [int(i) for i in ids])
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{offer_id}/unhide")
async def unhide_offer(offer_id: int) -> dict:
    db = await dbm.connect()
    try:
        await dbm.unhide_offer(db, offer_id)
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{offer_id}/tracking")
async def set_tracking(offer_id: int, payload: dict = Body(...)) -> dict:
    """Met à jour le suivi : applied_at, follow_up_at, notes, contact (champs partiels)."""
    db = await dbm.connect()
    try:
        await dbm.set_tracking(db, offer_id, payload)
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{offer_id}/status")
async def set_status(offer_id: int, value: Optional[str] = None) -> dict:
    """Met à jour l'étape de suivi de candidature (board des favoris)."""
    if value is not None and value not in dbm.APPLICATION_STATUSES:
        raise HTTPException(400, f"Statut invalide. Valeurs: {', '.join(dbm.APPLICATION_STATUSES)}")
    db = await dbm.connect()
    try:
        await dbm.set_application_status(db, offer_id, value)
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{offer_id}/generate")
async def generate(offer_id: int) -> dict:
    folder = await regenerate_for_offer(offer_id)
    if folder is None:
        raise HTTPException(404, "Offre introuvable")
    return {"ok": True, "folder": str(folder)}


@router.get("/{offer_id}/cv")
async def download_cv(offer_id: int):
    db = await dbm.connect()
    try:
        docs = await dbm.get_docs_for_offer(db, offer_id)
        if not docs or not Path(docs.adapted_cv_path).exists():
            raise HTTPException(404, "CV non généré")
        return FileResponse(docs.adapted_cv_path, media_type="text/html", filename="cv.html")
    finally:
        await db.close()


@router.get("/{offer_id}/letter")
async def download_letter(offer_id: int):
    db = await dbm.connect()
    try:
        docs = await dbm.get_docs_for_offer(db, offer_id)
        if not docs or not Path(docs.letter_path).exists():
            raise HTTPException(404, "Lettre non générée")
        return PlainTextResponse(Path(docs.letter_path).read_text(), media_type="text/markdown")
    finally:
        await db.close()


# ---------------------------------------------------------------------
# Édition CV / lettre (MVP)
# ---------------------------------------------------------------------


@router.get("/{offer_id}/cv/content")
async def get_cv_content(offer_id: int) -> dict:
    docs, _ = await _require_docs(offer_id)
    path = Path(docs.adapted_cv_path)
    if not path.exists():
        raise HTTPException(404, "Fichier CV introuvable")
    return {"html": path.read_text()}


@router.put("/{offer_id}/cv/content")
async def put_cv_content(offer_id: int, payload: dict = Body(...)) -> dict:
    html = payload.get("html")
    if not isinstance(html, str) or not html.strip():
        raise HTTPException(400, "Champ 'html' manquant")
    docs, _ = await _require_docs(offer_id)
    fitted = await fit_cv_html(html)
    Path(docs.adapted_cv_path).write_text(fitted)
    return {"ok": True, "html": fitted}


@router.post("/{offer_id}/cv/ai-edit")
async def ai_edit_cv(offer_id: int, payload: dict = Body(...)) -> dict:
    instruction = (payload.get("instruction") or "").strip()
    if not instruction:
        raise HTTPException(400, "Champ 'instruction' manquant")
    docs, _ = await _require_docs(offer_id)
    current = Path(docs.adapted_cv_path).read_text()
    new_html = await apply_instructions_to_cv(current, instruction)
    new_html = await fit_cv_html(new_html)
    Path(docs.adapted_cv_path).write_text(new_html)
    return {"html": new_html}


@router.get("/{offer_id}/letter/content")
async def get_letter_content(offer_id: int) -> dict:
    docs, _ = await _require_docs(offer_id)
    path = Path(docs.letter_path)
    if not path.exists():
        raise HTTPException(404, "Fichier lettre introuvable")
    return {"markdown": path.read_text()}


@router.put("/{offer_id}/letter/content")
async def put_letter_content(offer_id: int, payload: dict = Body(...)) -> dict:
    markdown = payload.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise HTTPException(400, "Champ 'markdown' manquant")
    docs, _ = await _require_docs(offer_id)
    Path(docs.letter_path).write_text(markdown)
    return {"ok": True}


@router.post("/{offer_id}/letter/ai-edit")
async def ai_edit_letter(offer_id: int, payload: dict = Body(...)) -> dict:
    instruction = (payload.get("instruction") or "").strip()
    if not instruction:
        raise HTTPException(400, "Champ 'instruction' manquant")
    docs, _ = await _require_docs(offer_id)
    current = Path(docs.letter_path).read_text()
    new_md = await apply_instructions_to_letter(current, instruction)
    Path(docs.letter_path).write_text(new_md)
    return {"markdown": new_md}


# ---------------------------------------------------------------------
# Éditeur visuel (v2) — structured JSON + render programmatique
# ---------------------------------------------------------------------


def _structured_path(cv_path: Path) -> Path:
    """Chemin du JSON éditable à côté du cv.html (data/offers/<slug>/cv.structured.json)."""
    return cv_path.with_name("cv.structured.json")


def _style_path(cv_path: Path) -> Path:
    return cv_path.with_name("cv.style.json")


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


@router.get("/{offer_id}/cv/editable")
async def get_editable(offer_id: int) -> dict:
    """Renvoie le modèle éditable + le style courant. Si absent, l'extrait du HTML existant."""
    docs, _ = await _require_docs(offer_id)
    cv_path = Path(docs.adapted_cv_path)
    if not cv_path.exists():
        raise HTTPException(404, "CV non généré")

    struct_path = _structured_path(cv_path)
    style_path = _style_path(cv_path)

    structured = _read_json(struct_path)
    style = _read_json(style_path)
    if structured is None:
        cv_html = cv_path.read_text()
        try:
            structured = await extract_editable(cv_html)
        except Exception as e:
            raise HTTPException(500, f"Extraction éditable échouée : {e}") from e
        if style is None:
            style = detect_style(cv_html)
        _write_json(struct_path, structured)
        _write_json(style_path, style)
    elif style is None:
        style = detect_style(cv_path.read_text())
        _write_json(style_path, style)

    return {"structured": structured, "style": style}


@router.put("/{offer_id}/cv/editable")
async def put_editable(offer_id: int, payload: dict = Body(...)) -> dict:
    """Sauvegarde structured + style, re-render le HTML, applique fit, persiste cv.html."""
    structured = payload.get("structured")
    style = payload.get("style") or {}
    if not isinstance(structured, dict):
        raise HTTPException(400, "Champ 'structured' invalide")
    docs, _ = await _require_docs(offer_id)
    cv_path = Path(docs.adapted_cv_path)
    if not cv_path.exists():
        raise HTTPException(404, "CV non généré")

    # WYSIWYG : on persiste EXACTEMENT le rendu affiché dans l'aperçu de l'éditeur
    # (render_cv applique la densité choisie). Pas d'auto-fit ici — sinon le PDF
    # diffère de l'aperçu. L'utilisateur règle la densité à la main et la voit.
    html = render_cv(structured, style)
    cv_path.write_text(html)
    _write_json(_structured_path(cv_path), structured)
    _write_json(_style_path(cv_path), style)
    return {"ok": True, "html": html}


@router.post("/{offer_id}/cv/render-preview")
async def render_preview(offer_id: int, payload: dict = Body(...)) -> dict:
    """Render rapide (sans fit, sans persister) — pour l'aperçu live pendant l'édition."""
    structured = payload.get("structured")
    style = payload.get("style") or {}
    if not isinstance(structured, dict):
        raise HTTPException(400, "Champ 'structured' invalide")
    html = render_cv(structured, style)
    return {"html": html}


AI_BULLET_SYSTEM = """Tu reformules UN seul bullet de CV d'alternance. Garde le sens factuel, ne change pas la nature de l'action, n'invente pas de chiffres ni de mots qui ne soient pas déjà dans le bullet ou la description de l'offre fournie.

Tu reçois :
- l'offre cible (titre + description) en contexte
- le bullet actuel
- une instruction (plus court / plus impact / reformule pour l'offre)

Renvoie UNIQUEMENT la nouvelle version du bullet. Une seule phrase, courte (≤ 18 mots si possible), action puis impact. Pas de point final si le bullet d'origine n'en a pas. Pas d'emoji."""


@router.post("/{offer_id}/cv/ai-bullet")
async def ai_bullet(offer_id: int, payload: dict = Body(...)) -> dict:
    """Reformule un bullet en isolation, avec le contexte de l'offre."""
    bullet = (payload.get("bullet") or "").strip()
    instruction = (payload.get("instruction") or "Reformule pour mieux coller à l'offre.").strip()
    if not bullet:
        raise HTTPException(400, "Champ 'bullet' manquant")

    db = await dbm.connect()
    try:
        offer = await dbm.get_offer(db, offer_id)
    finally:
        await db.close()
    if not offer:
        raise HTTPException(404, "Offre introuvable")

    user = f"""Offre cible :
- Titre : {offer.title}
- Entreprise : {offer.company or 'n/c'}
- Compétences clés : {', '.join(offer.skills[:8]) if offer.skills else 'n/c'}

Description (extrait) :
{(offer.description or '')[:2500]}

Bullet actuel :
{bullet}

Instruction :
{instruction}

Renvoie uniquement le nouveau bullet."""
    new_bullet = await complete(
        system=AI_BULLET_SYSTEM,
        user=user,
        max_tokens=300,
        temperature=0.4,
        model="claude-haiku-4-5-20251001",
    )
    new_bullet = new_bullet.strip().strip('"').strip("'")
    if new_bullet.startswith("- "):
        new_bullet = new_bullet[2:]
    if "\n" in new_bullet:
        new_bullet = new_bullet.split("\n", 1)[0].strip()
    return {"bullet": new_bullet}


AI_BLOCK_SYSTEM = """Tu reçois la valeur courante d'UN champ de CV (titre, bullet, phrase, nom de projet, etc.) et une instruction en français de modification. Tu renvoies UNIQUEMENT la nouvelle valeur du champ, sans préambule, sans guillemets, sans markdown.

Règles :
- Garde les faits factuels (chiffres, noms d'outils, dates) sauf si l'instruction demande explicitement de les retirer.
- Aucune invention de chiffre ou de fait absent du champ ou du contexte offre fourni.
- Pour un titre/bullet : 1 ligne max, action en premier si pertinent.
- Pour une description / intro : 1-2 phrases max sauf instruction contraire.
- Jamais d'emoji, jamais de placeholder [crochets]."""


@router.post("/{offer_id}/cv/ai-block")
async def ai_block(offer_id: int, payload: dict = Body(...)) -> dict:
    """Réécrit la valeur d'un champ ciblé (path) via une instruction libre."""
    value = (payload.get("value") or "").strip()
    instruction = (payload.get("instruction") or "").strip()
    path = (payload.get("path") or "").strip()
    if not value and not instruction:
        raise HTTPException(400, "Champ 'value' ou 'instruction' manquant")

    db = await dbm.connect()
    try:
        offer = await dbm.get_offer(db, offer_id)
    finally:
        await db.close()
    offer_ctx = ""
    if offer:
        offer_ctx = (
            f"Offre cible : {offer.title}"
            + (f" · {offer.company}" if offer.company else "")
            + (f"\nCompétences clés : {', '.join(offer.skills[:8])}" if offer.skills else "")
            + (f"\n\nExtrait offre :\n{(offer.description or '')[:1500]}" if offer.description else "")
        )

    value_line = value if value else "(vide — créer un contenu adapté)"
    instruction_line = instruction or "Améliore ce champ pour mieux coller à l'offre."
    user = f"""{offer_ctx}

Champ : {path or 'libre'}
Valeur actuelle :
{value_line}

Instruction :
{instruction_line}

Renvoie uniquement la nouvelle valeur."""
    new_value = await complete(
        system=AI_BLOCK_SYSTEM,
        user=user,
        max_tokens=300,
        temperature=0.4,
        model="claude-haiku-4-5-20251001",
    )
    new_value = new_value.strip().strip('"').strip("'")
    # Garde la 1ʳᵉ ligne si Haiku en pond plusieurs
    if "\n" in new_value:
        # On garde TOUT le texte si c'est manifestement une intro (multi-phrase)
        # mais limite à 600 chars pour éviter les pavés
        new_value = "\n".join(line for line in new_value.splitlines() if line.strip())[:600]
    return {"value": new_value}


AI_GLOBAL_SYSTEM = """Tu es un expert en CV pour alternance. Tu vas modifier un CV STRUCTURÉ (JSON) d'un seul coup, selon une instruction libre.

On te fournit :
1. Le PROFIL SOURCE du candidat (toutes ses vraies expériences, projets, compétences, formations — c'est la source de vérité factuelle).
2. Le CV ACTUEL adapté à l'offre (JSON éditable, peut être incomplet/vide si premier remplissage).
3. L'OFFRE cible.
4. Une INSTRUCTION en français.

Tu produis le NOUVEAU CV éditable (JSON) en appliquant l'instruction.

Schéma exact attendu (respecte les clés, types, ordre n'a pas d'importance) :
{
  "name": "string|null",
  "role": "string|null",
  "contact": {"email":"string|null","phone":"string|null","linkedin":"string|null","location":"string|null"},
  "intro": "string|null",
  "hard_skills": ["string", ...],
  "soft_skills": ["string", ...],
  "tools": ["string", ...],
  "languages": [{"name":"string","level":"string|null"}, ...],
  "formations": [{"degree":"string","school":"string","period":"string"}, ...],
  "experiences": [{"company":"string","role":"string","period":"string","bullets":["string",...]}, ...],
  "projects_pedagogical": [{"name":"string","summary":"string"}, ...],
  "projects_personal": [{"name":"string","summary":"string"}, ...]
}

RÈGLES IMPÉRATIVES
- Tu peux RÉORDONNER, RÉÉCRIRE, AJOUTER, SUPPRIMER. Mais tu ne dois JAMAIS inventer un fait absent du profil source (entreprise, école, projet, chiffre). Si l'instruction te pousse vers une invention, refuse-la en gardant la donnée d'origine.
- Préserve TOUJOURS les faits factuels : noms d'entreprises, écoles, dates, diplômes. Tu peux reformuler les bullets ; tu ne peux pas changer une période ou un employeur.
- Si l'instruction dit "préremplir" / "remplir depuis le source", repars du profil source ET adapte fortement role / intro / ordre des bullets / sélection hard_skills à l'offre. Garde 2-4 expériences (les plus pertinentes), 3-5 bullets par expérience.
- Si l'instruction dit "raccourcir tout", supprime les bullets faibles ; vise 3 bullets/expérience max.
- Le champ `role` doit toujours être adapté à l'offre (titre court d'alternance en français).
- Le champ `intro` est une phrase italique courte (15-30 mots), elle référence un élément concret de l'offre.

SORTIE
Retourne UNIQUEMENT le JSON conforme. Pas de texte avant/après, pas de ```."""


@router.post("/{offer_id}/cv/ai-global")
async def ai_global(offer_id: int, payload: dict = Body(...)) -> dict:
    """Réécrit la totalité du CV structuré en un coup (préremplir, refondre, raccourcir…)."""
    structured = payload.get("structured") or {}
    instruction = (payload.get("instruction") or "").strip()
    if not instruction:
        raise HTTPException(400, "Champ 'instruction' manquant")

    db = await dbm.connect()
    try:
        offer = await dbm.get_offer(db, offer_id)
        default_cv = await dbm.get_default_cv(db)
        source_struct = None
        if default_cv:
            source_struct = await dbm.get_cv_structured(db, default_cv.id or 0)
    finally:
        await db.close()
    if not offer:
        raise HTTPException(404, "Offre introuvable")

    source_text = (
        profile_to_text(source_struct) if source_struct
        else "(profil source non extrait — utiliser uniquement le CV actuel comme base)"
    )

    offer_text = (
        f"Titre : {offer.title}\n"
        f"Entreprise : {offer.company or 'n/c'}\n"
        f"Localisation : {offer.location or 'n/c'}\n"
        f"Compétences clés : {', '.join(offer.skills[:10]) if offer.skills else 'n/c'}\n\n"
        f"Description :\n{(offer.description or '')[:3500]}"
    )

    current_json = json.dumps(structured, ensure_ascii=False, indent=2)

    user = f"""=== PROFIL SOURCE DU CANDIDAT (source de vérité factuelle) ===
{source_text}

=== CV ACTUEL ADAPTÉ À L'OFFRE (JSON éditable) ===
{current_json}

=== OFFRE CIBLE ===
{offer_text}

=== INSTRUCTION ===
{instruction}

Renvoie UNIQUEMENT le JSON conforme au schéma."""

    try:
        new_struct = await complete_json(
            system=AI_GLOBAL_SYSTEM,
            user=user,
            max_tokens=6000,
        )
    except Exception as e:
        raise HTTPException(500, f"Réécriture IA échouée : {e}") from e
    return {"structured": new_struct}


@router.get("/{offer_id}/cv/pdf")
async def download_cv_pdf(offer_id: int):
    docs, offer = await _require_docs(offer_id)
    path = Path(docs.adapted_cv_path)
    if not path.exists():
        raise HTTPException(404, "CV non généré")
    pdf_bytes = await html_to_pdf(path.read_text(), margin_mm=0)
    filename = f"cv-{_slugify(offer.title if offer else 'offre')}.pdf"
    return Response(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{offer_id}/letter/pdf")
async def download_letter_pdf(offer_id: int):
    docs, offer = await _require_docs(offer_id)
    path = Path(docs.letter_path)
    if not path.exists():
        raise HTTPException(404, "Lettre non générée")
    body_html = md_lib.markdown(path.read_text(), extensions=["extra", "sane_lists"])
    html_doc = LETTER_PDF_TEMPLATE.format(body=body_html)
    pdf_bytes = await html_to_pdf(html_doc, margin_mm=0)
    filename = f"lettre-{_slugify(offer.title if offer else 'offre')}.pdf"
    return Response(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
