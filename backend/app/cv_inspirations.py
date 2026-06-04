"""Scrape de galeries publiques d'inspirations CV.

On utilise enhancv (la galerie /resume-examples) qui SSR ~240 thumbnails de CV
designs. Pour chaque image trouvée on récupère URL + un éventuel titre proche.

Cache disque léger (1h) pour éviter de re-scraper à chaque ouverture de la
galerie côté UI.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx

from .config import CACHE_DIR
from .scrapers.base import fetch_text

logger = logging.getLogger(__name__)

ENHANCV_URL = "https://enhancv.com/resume-examples/"
NOVORESUME_URL = "https://novoresume.com/resume-templates"
CACHE_FILE = CACHE_DIR / "cv_inspirations.json"
CACHE_TTL_S = 3600  # 1h


async def fetch_inspirations(limit: int = 60) -> list[dict[str, Any]]:
    """Liste de {url, source, title} d'inspirations CV."""
    cached = _read_cache()
    if cached is not None:
        return cached[:limit]

    items: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        items.extend(await _scrape_enhancv(client))
        items.extend(await _scrape_novoresume(client))

    # dedupe par url
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for it in items:
        u = it.get("url") or ""
        if not u or u in seen:
            continue
        seen.add(u)
        uniq.append(it)

    _write_cache(uniq)
    return uniq[:limit]


async def _scrape_enhancv(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        status, body = await fetch_text(client, ENHANCV_URL, referer="https://www.google.com/")
        if status != 200 or not body:
            return out
        # Les thumbnails enhancv sont sur cdn.enhancv.com avec un format prévisible
        imgs = re.findall(
            r'https://cdn\.enhancv\.com/[^"\s\']+\.(?:jpg|jpeg|png|webp)',
            body,
        )
        # Filtre : on garde les images qui ressemblent à des exemples (taille raisonnable)
        for url in imgs:
            # Exclure les icônes / petites images d'UI
            if any(s in url.lower() for s in ("icon", "logo", "/badge", "favicon")):
                continue
            out.append({"url": url, "source": "enhancv", "title": ""})
    except Exception as e:
        logger.warning("enhancv scrape failed: %s", e)
    return out


async def _scrape_novoresume(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        status, body = await fetch_text(client, NOVORESUME_URL, referer="https://www.google.com/")
        if status != 200 or not body:
            return out
        imgs = re.findall(
            r'https://novoresume\.com/[^"\s\']+\.(?:jpg|jpeg|png|webp)',
            body,
        )
        for url in imgs:
            if any(s in url.lower() for s in ("icon", "logo", "favicon", "preview-small")):
                continue
            out.append({"url": url, "source": "novoresume", "title": ""})
    except Exception as e:
        logger.warning("novoresume scrape failed: %s", e)
    return out


def _read_cache() -> list[dict[str, Any]] | None:
    if not CACHE_FILE.exists():
        return None
    try:
        st = CACHE_FILE.stat()
        if (time.time() - st.st_mtime) > CACHE_TTL_S:
            return None
        return json.loads(CACHE_FILE.read_text())
    except Exception:
        return None


def _write_cache(items: list[dict[str, Any]]) -> None:
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(items, ensure_ascii=False))
    except Exception as e:
        logger.debug("inspirations cache write failed: %s", e)
