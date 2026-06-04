from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, Response

from .. import db as dbm
from ..config import DATA_DIR, PHOTO_EXTS, get_profile_photo_path, load_profile, save_profile
from ..models import OfferRaw
from ..pipeline import STATE, run_search
from ..scrapers.linkedin_manual import parse_linkedin_url

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search/start")
async def start_search() -> dict:
    if STATE.running:
        raise HTTPException(409, "Recherche déjà en cours")
    asyncio.create_task(run_search())
    return {"ok": True, "started": True}


@router.get("/search/status")
async def status() -> dict:
    return {
        "running": STATE.running,
        "last_progress": STATE.last_progress.model_dump() if STATE.last_progress else None,
    }


@router.get("/search/stats")
async def search_stats() -> dict:
    """Agrégats pour la stats bar : total offres, par source, score moyen, top scoring."""
    import json as _json
    db = await dbm.connect()
    try:
        cur = await db.execute(
            "SELECT COUNT(*) AS total, "
            "AVG(score) AS avg_score, "
            "SUM(CASE WHEN score >= 70 THEN 1 ELSE 0 END) AS high_score "
            "FROM offers WHERE is_hidden = 0"
        )
        row = await cur.fetchone()
        total = (row["total"] if row else 0) or 0
        avg = round((row["avg_score"] or 0) if row else 0, 1)
        high = (row["high_score"] if row else 0) or 0

        cur = await db.execute(
            "SELECT source, COUNT(*) AS n, AVG(score) AS avg FROM offers WHERE is_hidden=0 GROUP BY source"
        )
        sources = [
            {"source": r["source"], "count": r["n"], "avg_score": round(r["avg"] or 0, 1)}
            for r in await cur.fetchall()
        ]

        cur = await db.execute(
            "SELECT COUNT(*) AS n FROM generated_docs"
        )
        row = await cur.fetchone()
        generated = (row["n"] if row else 0) or 0

        # Offres découvertes au dernier run (= nouveautés du filtre UI).
        latest = await dbm.latest_run_id(db)
        new_count = 0
        if latest is not None:
            cur = await db.execute(
                "SELECT COUNT(*) AS n FROM offers WHERE is_hidden=0 AND first_run_id=?",
                (latest,),
            )
            row = await cur.fetchone()
            new_count = (row["n"] if row else 0) or 0

        cur = await db.execute(
            "SELECT started_at, finished_at, stats_json, status FROM search_runs ORDER BY id DESC LIMIT 1"
        )
        row = await cur.fetchone()
        last_run = None
        if row:
            try:
                stats = _json.loads(row["stats_json"] or "{}")
            except Exception:
                stats = {}
            last_run = {
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "status": row["status"],
                "stats": stats,
            }

        return {
            "total": total,
            "avg_score": avg,
            "high_score": high,
            "generated": generated,
            "new_count": new_count,
            "by_source": sources,
            "last_run": last_run,
        }
    finally:
        await db.close()


@router.get("/profile")
async def get_profile() -> dict:
    return load_profile()


@router.put("/profile")
async def put_profile(profile: dict) -> dict:
    save_profile(profile)
    return {"ok": True}


@router.get("/profile/photo")
async def get_profile_photo():
    p = get_profile_photo_path()
    if not p:
        return Response(status_code=404)
    ext = p.suffix.lstrip(".").lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    return FileResponse(p, media_type=mime)


@router.post("/profile/photo")
async def upload_profile_photo(file: UploadFile = File(...)) -> dict:
    filename = (file.filename or "").lower()
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in PHOTO_EXTS:
        raise HTTPException(400, f"Format non supporté (png/jpg/webp attendu), reçu : .{ext}")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Fichier vide")
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Photo trop lourde (max 5 Mo)")
    # supprimer les autres extensions
    for e in PHOTO_EXTS:
        p = DATA_DIR / f"profile_photo.{e}"
        if p.exists():
            p.unlink()
    target = DATA_DIR / f"profile_photo.{ext}"
    target.write_bytes(data)
    return {"ok": True, "filename": target.name, "size": len(data)}


@router.delete("/profile/photo")
async def delete_profile_photo() -> dict:
    p = get_profile_photo_path()
    if p and p.exists():
        p.unlink()
    return {"ok": True}


@router.post("/linkedin/add")
async def add_linkedin(payload: dict) -> dict:
    url = payload.get("url", "").strip()
    if not url or "linkedin.com" not in url:
        raise HTTPException(400, "URL LinkedIn invalide")
    raw: OfferRaw = await parse_linkedin_url(url)
    db = await dbm.connect()
    try:
        oid = await dbm.upsert_offer_raw(db, raw)
        if oid is None:
            raise HTTPException(409, "Offre déjà importée")
        return {"ok": True, "offer_id": oid}
    finally:
        await db.close()
