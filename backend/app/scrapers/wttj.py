"""Scraper Welcome to the Jungle — httpx + BeautifulSoup.

WTTJ's search SPA (`/fr/jobs?query=…`) is pure client-side Algolia: no SSR data.
But their SEO landing pages `/fr/pages/emploi-alternance-<ville>` are fully
server-rendered with ~20 jobs per page and `?page=N` pagination.

→ On les hit en httpx (HTML 600 KB en 0.5s/page), parse en bs4, filtre par tokens.
Aucune dépendance à Playwright pour WTTJ : massivement plus rapide et fiable.
"""
from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from typing import AsyncIterator
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..models import OfferRaw
from .base import Scraper, fetch_text

logger = logging.getLogger(__name__)

BASE_URL = "https://www.welcometothejungle.com"

KNOWN_CITY_SLUGS = {
    "paris", "lyon", "marseille", "lille", "toulouse", "nantes", "bordeaux",
    "montpellier", "rennes", "strasbourg", "nice", "grenoble",
}

_STOP_TOKENS = {
    "alternance", "apprentissage", "stage", "cdi", "cdd", "remote",
    "paris", "lyon", "marseille", "lille", "ile", "france",
    "de", "du", "la", "le", "les", "et", "ou", "en", "un", "une",
    "pour", "sur", "par", "avec", "dans", "des", "au", "aux",
    "engineer", "engineering", "manager", "junior", "senior",
}


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def keyword_tokens(keywords: list[str]) -> set[str]:
    out: set[str] = set()
    for kw in keywords:
        for tok in re.split(r"[^a-zA-Z0-9]+", _normalize(kw)):
            if len(tok) >= 3 and tok not in _STOP_TOKENS:
                out.add(tok)
            elif tok in {"ia", "ai", "pm", "ml", "ux", "ui"}:
                out.add(tok)
    return out


def _matches_tokens(hay: str, tokens: set[str]) -> bool:
    if not tokens:
        return True
    h = _normalize(hay)
    return any(t in h for t in tokens)


class WTTJScraper(Scraper):
    source = "wttj"
    budget_s = 30.0     # httpx → très rapide, 30s suffit largement
    max_pages = 8       # 8 × 20 = 160 cards scannées max
    parallel_pages = 4

    async def search(
        self, keywords: list[str], location: str, max_per_source: int
    ) -> AsyncIterator[OfferRaw]:
        city_slug = _city_to_slug(location) or "paris"
        tokens = keyword_tokens(keywords)
        logger.info("WTTJ: city=%s, tokens=%s", city_slug, sorted(tokens))

        async with httpx.AsyncClient(timeout=15.0) as client:
            sem = asyncio.Semaphore(self.parallel_pages)

            async def fetch_one(page_num: int) -> list[dict]:
                async with sem:
                    return await self._scrape_page(client, city_slug, page_num)

            # Lance toutes les pages en parallèle, traite dans l'ordre des arrivées
            tasks = [asyncio.create_task(fetch_one(n)) for n in range(1, self.max_pages + 1)]
            seen_urls: set[str] = set()
            yielded = 0
            try:
                for task in asyncio.as_completed(tasks):
                    cards = await task
                    matched = 0
                    for c in cards:
                        if c["url"] in seen_urls:
                            continue
                        seen_urls.add(c["url"])
                        hay = f"{c['title']} {c.get('company') or ''} {c.get('description') or ''}"
                        if not _matches_tokens(hay, tokens):
                            continue
                        matched += 1
                        yield OfferRaw(
                            source="wttj",
                            url=c["url"],
                            title=c["title"],
                            company=c.get("company"),
                            location=c.get("location"),
                            contract=c.get("contract") or "Alternance",
                            description=c.get("description") or "",
                        )
                        yielded += 1
                        if yielded >= max_per_source:
                            return
            finally:
                for t in tasks:
                    if not t.done():
                        t.cancel()
        logger.info("WTTJ done: %d offers yielded", yielded)

    async def _scrape_page(
        self, client: httpx.AsyncClient, city_slug: str, page_num: int
    ) -> list[dict]:
        url = f"{BASE_URL}/fr/pages/emploi-alternance-{city_slug}"
        if page_num > 1:
            url += f"?page={page_num}"
        status, body = await fetch_text(client, url, referer=BASE_URL + "/fr/")
        if status != 200 or not body:
            return []
        cards = _parse_landing_html(body)
        logger.info("WTTJ p=%d → %d cards", page_num, len(cards))
        return cards


# ---------------------------------------------------------------------------
# Parsing HTML (bs4)
# ---------------------------------------------------------------------------

JOB_HREF_RE = re.compile(r"^/fr/companies/[\w\-]+/jobs/[\w\-_]+$")


def _parse_landing_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    seen: set[str] = set()
    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        if not href.startswith("/fr/companies/") or "/jobs/" not in href:
            continue
        href_clean = href.split("?")[0].split("#")[0]
        if href_clean in seen:
            continue
        seen.add(href_clean)
        # On remonte vers le bloc card (parent qui contient toute la card)
        card = a
        for _ in range(6):
            if card.parent is None:
                break
            card = card.parent
            txt = card.get_text("\n", strip=True)
            if len(txt) > 80 and "\n" in txt:
                break
        text = card.get_text("\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            continue
        title = lines[0]
        company = lines[1] if len(lines) > 1 else None
        if company and (len(company) < 2 or re.fullmatch(r"\d+(\.\d+)?", company)):
            company = None
        # contrat + lieu + sector
        contract: str | None = None
        location: str | None = None
        extras: list[str] = []
        for l in lines[2:12]:
            if re.fullmatch(r"(?i)alternance|apprentissage|professionnalisation|stage|cdi|cdd", l) and not contract:
                contract = l
                continue
            if (not location) and 2 < len(l) < 50 and l[0].isupper() and "Télétravail" not in l:
                location = l
                continue
            extras.append(l)
        description = " · ".join(([lines[2]] if len(lines) > 2 else []) + extras)[:1500]
        out.append({
            "url": urljoin(BASE_URL, href_clean),
            "title": title,
            "company": company,
            "location": location,
            "contract": contract,
            "description": description,
        })
    return out


def _city_to_slug(location: str) -> str | None:
    loc = _normalize((location or "").strip())
    if not loc:
        return None
    for s in KNOWN_CITY_SLUGS:
        if s in loc:
            return s
    return None
