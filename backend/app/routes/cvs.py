from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from .. import db as dbm
from ..llm.cv_extractor import extract_cv_to_html, guess_mime
from ..llm.cv_profile import extract_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cvs", tags=["cvs"])

IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "gif"}
PDF_EXTS = {"pdf"}


@router.get("")
async def list_cvs() -> list[dict]:
    db = await dbm.connect()
    try:
        cvs = await dbm.list_cvs(db)
        return [
            {
                "id": c.id, "filename": c.filename,
                "uploaded_at": c.uploaded_at.isoformat() if c.uploaded_at else None,
                "is_default": c.is_default,
                "size": len(c.html_content),
            }
            for c in cvs
        ]
    finally:
        await db.close()


@router.post("")
async def upload_cv(file: UploadFile = File(...), set_default: bool = False) -> dict:
    raw = await file.read()
    filename = file.filename or "cv"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    content_type = (file.content_type or "").lower()

    is_image = ext in IMAGE_EXTS or content_type.startswith("image/")
    is_pdf = ext in PDF_EXTS or content_type == "application/pdf"
    is_html = ext == "html" or content_type == "text/html"

    if is_image or is_pdf:
        if is_pdf:
            mime = "application/pdf"
        else:
            mime = content_type if content_type.startswith("image/") else guess_mime(filename)
        try:
            html = await extract_cv_to_html(raw, mime)
        except Exception as e:
            logger.exception("CV extraction failed")
            raise HTTPException(500, f"Extraction CV échouée : {e}") from e
        stored_name = filename.rsplit(".", 1)[0] + ".html" if "." in filename else filename + ".html"
    elif is_html:
        try:
            html = raw.decode("utf-8")
        except UnicodeDecodeError:
            html = raw.decode("latin-1")
        if "<" not in html or ">" not in html:
            raise HTTPException(400, "Fichier HTML invalide")
        stored_name = filename
    else:
        raise HTTPException(
            400,
            "Format non supporté. Accepté : HTML, PDF ou image (PNG, JPG, JPEG, WEBP).",
        )

    db = await dbm.connect()
    try:
        cv_id = await dbm.add_cv(db, stored_name, html, is_default=set_default)
        # Auto-promotion : si aucun CV n'est marqué défaut après l'insert, on promeut celui-ci.
        cvs = await dbm.list_cvs(db)
        if not any(c.is_default for c in cvs):
            await dbm.set_default_cv(db, cv_id)
    finally:
        await db.close()

    # Extraction profil structuré en tâche de fond — ne bloque pas l'upload.
    asyncio.create_task(_extract_and_store_profile(cv_id, html))
    return {"id": cv_id, "ok": True, "filename": stored_name}


async def _extract_and_store_profile(cv_id: int, html: str) -> None:
    try:
        structured = await extract_profile(html)
    except Exception as e:
        logger.warning("Profile extraction failed for CV %s: %s", cv_id, e)
        return
    db = await dbm.connect()
    try:
        await dbm.set_cv_structured(db, cv_id, structured)
        logger.info("Profile extracted + stored for CV %s", cv_id)
    finally:
        await db.close()


@router.delete("/{cv_id}")
async def delete_cv(cv_id: int) -> dict:
    db = await dbm.connect()
    try:
        await dbm.delete_cv(db, cv_id)
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{cv_id}/default")
async def set_default(cv_id: int) -> dict:
    db = await dbm.connect()
    try:
        await dbm.set_default_cv(db, cv_id)
        return {"ok": True}
    finally:
        await db.close()


@router.get("/{cv_id}/content")
async def get_cv_content(cv_id: int) -> dict:
    db = await dbm.connect()
    try:
        cvs = await dbm.list_cvs(db)
        for c in cvs:
            if c.id == cv_id:
                return {"id": c.id, "filename": c.filename, "html": c.html_content}
        raise HTTPException(404, "CV introuvable")
    finally:
        await db.close()
