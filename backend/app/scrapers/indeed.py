"""Scraper Indeed FR — httpx + parsing du JSON `mosaic-provider-jobcards`.

Indeed FR embarque dans chaque page de recherche le JSON Algolia-like des résultats
dans `window.mosaic.providerData["mosaic-provider-jobcards"]`. C'est exactement
ce qu'on veut : titre, entreprise, location, snippet, jobkey — pas besoin de DOM.

Important : il faut OMETTRE `br` de Accept-Encoding (déjà fait dans base.browser_headers)
sinon httpx renvoie du brotli non décodé.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, AsyncIterator
from urllib.parse import quote_plus

import httpx

from ..models import OfferRaw
from .base import Scraper, fetch_text, polite_delay

logger = logging.getLogger(__name__)

BASE_URL = "https://fr.indeed.com"
# sort=date → priorise le frais ; fromage=14 → fenêtre 14 jours ; start → pagination (10/page).
SEARCH_URL = "https://fr.indeed.com/jobs?q={kw}&l={loc}&sort=date&fromage=14&start={start}"

MOSAIC_RE = re.compile(
    r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.+?\});\s*(?:window|</script>)',
    re.DOTALL,
)


class IndeedScraper(Scraper):
    source = "indeed"
    budget_s = 60.0
    max_per_keyword = 30
    parallel_keywords = 3
    pages = 2  # nb de pages (10 offres/page) parcourues par mot-clé

    async def search(
        self, keywords: list[str], location: str, max_per_source: int
    ) -> AsyncIterator[OfferRaw]:
        seen_keys: set[str] = set()
        yielded = 0
        async with httpx.AsyncClient(timeout=15.0) as client:
            sem = asyncio.Semaphore(self.parallel_keywords)

            async def fetch_one(kw: str) -> list[OfferRaw]:
                async with sem:
                    res = await self._scrape_keyword(client, kw, location)
                    await polite_delay(0.3, 0.9)
                    return res

            tasks = [asyncio.create_task(fetch_one(kw)) for kw in keywords]
            try:
                for task in asyncio.as_completed(tasks):
                    offers = await task
                    for o in offers:
                        # dedup par jobkey si extrait, sinon par URL
                        m = re.search(r"jk=([\w]+)", o.url)
                        key = m.group(1) if m else o.url
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        yield o
                        yielded += 1
                        if yielded >= max_per_source:
                            return
            finally:
                for t in tasks:
                    if not t.done():
                        t.cancel()

    async def _scrape_keyword(
        self, client: httpx.AsyncClient, keyword: str, location: str
    ) -> list[OfferRaw]:
        out: list[OfferRaw] = []
        seen_urls: set[str] = set()
        for page in range(self.pages):
            url = SEARCH_URL.format(
                kw=quote_plus(keyword), loc=quote_plus(location), start=page * 10
            )
            status, body = await fetch_text(client, url, referer=BASE_URL)
            if status != 200 or not body:
                logger.info("Indeed kw=%r p=%d → HTTP %s", keyword, page, status)
                break  # page suivante inutile si celle-ci échoue
            results = _extract_mosaic_results(body)
            if not results:
                # Pas de json mosaic → fallback regex sur le HTML brut
                logger.info("Indeed kw=%r p=%d → mosaic JSON absent, fallback HTML", keyword, page)
                results = _extract_from_html(body)
            if not results:
                break
            for r in results:
                offer = _to_offer(r)
                if offer is None or offer.url in seen_urls:
                    continue
                # Filtre rapide alternance : on garde si "altern" ou "apprent" apparaît
                full = f"{offer.title} {offer.description} {offer.contract or ''}".lower()
                if "altern" in full or "apprent" in full:
                    seen_urls.add(offer.url)
                    out.append(offer)
            if len(out) >= self.max_per_keyword:
                break
            if page + 1 < self.pages:
                await polite_delay(0.3, 0.9)
        logger.info("Indeed kw=%r → %d offres (filtrées alternance, %d pages)",
                    keyword, len(out), self.pages)
        return out[: self.max_per_keyword]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _extract_mosaic_results(html: str) -> list[dict[str, Any]]:
    m = MOSAIC_RE.search(html)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception as e:
        logger.debug("Indeed mosaic JSON parse failed: %s", e)
        return []
    meta = (data or {}).get("metaData") or {}
    model = meta.get("mosaicProviderJobCardsModel") or {}
    results = model.get("results")
    if isinstance(results, list):
        return results
    return []


def _extract_from_html(html: str) -> list[dict[str, Any]]:
    """Fallback : extrait les jk + titres avec regex sur le HTML brut."""
    out = []
    for m in re.finditer(r'data-jk="([\w]{8,20})"[^>]*>', html):
        jk = m.group(1)
        # cherche title proche
        # Pattern : <span title="Titre"> ou <h2 ...>Titre
        nearby = html[m.start(): m.start() + 4000]
        t = re.search(r'<span\s+title="([^"]+)"', nearby)
        title = t.group(1) if t else ""
        out.append({"jobkey": jk, "title": title, "company": None, "snippet": ""})
    return out


def _to_offer(r: dict[str, Any]) -> OfferRaw | None:
    try:
        jk = r.get("jobkey") or r.get("jobKey") or ""
        title = (r.get("title") or r.get("displayTitle") or "").strip()
        if not jk and not title:
            return None
        url = f"{BASE_URL}/viewjob?jk={jk}" if jk else r.get("viewJobLink", "")
        if not url:
            return None
        company = (r.get("company") or "").strip() or None
        location = (
            r.get("formattedLocation")
            or r.get("formattedRelativeLocation")
            or r.get("jobLocationCity")
            or ""
        ).strip() or None
        snippet = (r.get("snippet") or "").strip()
        # snippet contient parfois du HTML léger (<b>) → on nettoie
        snippet = re.sub(r"<[^>]+>", " ", snippet)
        snippet = re.sub(r"\s+", " ", snippet).strip()[:1500]
        # type de contrat
        contract = None
        attrs = r.get("jobTypes") or r.get("formattedContractType") or r.get("contractType")
        if isinstance(attrs, list) and attrs:
            contract = ", ".join(str(x) for x in attrs)
        elif isinstance(attrs, str) and attrs:
            contract = attrs
        return OfferRaw(
            source="indeed",
            url=url,
            title=title or f"Offre #{jk}",
            company=company,
            location=location,
            # Pas de défaut "Alternance" : Indeed ne filtre pas le contrat côté requête,
            # masquer le vrai type ferait passer des CDI/stages au filtre alternance.
            contract=contract,
            description=snippet,
        )
    except Exception as e:
        logger.debug("Indeed to_offer error: %s", e)
        return None
