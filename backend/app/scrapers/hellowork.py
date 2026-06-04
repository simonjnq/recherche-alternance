"""Scraper HelloWork — httpx + bs4, SSR friendly.

HelloWork SSR ses pages de recherche : on récupère les cards (titre, entreprise,
lieu, contrat, salaire, ancienneté) en une simple requête HTTP.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import AsyncIterator
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup

from ..models import OfferRaw
from .base import Scraper, fetch_text, polite_delay

logger = logging.getLogger(__name__)

BASE_URL = "https://www.hellowork.com"
# &p=N → pagination ; &tri=Date → priorise le frais.
SEARCH_URL = "https://www.hellowork.com/fr-fr/emploi/recherche.html?k={kw}&l={loc}&c=Alternance&tri=Date&p={page}"


class HelloWorkScraper(Scraper):
    source = "hellowork"
    budget_s = 45.0
    max_per_keyword = 30
    parallel_keywords = 3
    pages = 2

    async def search(
        self, keywords: list[str], location: str, max_per_source: int
    ) -> AsyncIterator[OfferRaw]:
        seen_urls: set[str] = set()
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
                        if o.url in seen_urls:
                            continue
                        seen_urls.add(o.url)
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
        seen: set[str] = set()
        for page in range(1, self.pages + 1):
            url = SEARCH_URL.format(kw=quote_plus(keyword), loc=quote_plus(location), page=page)
            status, body = await fetch_text(client, url, referer=BASE_URL + "/")
            if status != 200 or not body:
                logger.info("HelloWork kw=%r p=%d → HTTP %s", keyword, page, status)
                break
            offers = _parse_hellowork(body)
            if not offers:
                break
            for o in offers:
                if o.url in seen:
                    continue
                seen.add(o.url)
                out.append(o)
            if len(out) >= self.max_per_keyword:
                break
            if page < self.pages:
                await polite_delay(0.3, 0.9)
        logger.info("HelloWork kw=%r → %d offres (%d pages)", keyword, len(out), self.pages)
        return out[: self.max_per_keyword]


def _parse_hellowork(html: str) -> list[OfferRaw]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("li[data-id-storage-target]") or soup.find_all("article")
    out: list[OfferRaw] = []
    for c in cards:
        a = c.find("a", href=re.compile(r"/fr-fr/emplois/\d+"))
        if not a:
            continue
        href = a.get("href") or ""
        if not href.startswith("/fr-fr/emplois/"):
            continue
        full = urljoin(BASE_URL, href.split("?")[0])
        # Card text en lignes "Title | Company | Location | Contract | Salary | …"
        text = c.get_text("\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            continue
        # Indeed-style heuristics
        title = lines[0]
        company = lines[1] if len(lines) > 1 else None
        location = None
        contract = None
        salary = None
        extras: list[str] = []
        for l in lines[2:14]:
            if not location and re.search(r"^\w[\w '\-]*\s*-\s*\d{2,3}$", l):  # "Paris - 75"
                location = l
                continue
            if not location and re.match(r"^Paris\s+\d{1,2}e\b", l):
                location = l
                continue
            if not contract and re.fullmatch(r"(?i)alternance|apprentissage|professionnalisation|stage|cdi|cdd", l):
                contract = l
                continue
            if not salary and "€" in l:
                salary = l
                continue
            if l.lower().startswith(("voir l", "il y a", "+ ")):
                continue
            extras.append(l)
        description = " · ".join(extras[:6])[:1500]
        out.append(
            OfferRaw(
                source="hellowork",
                url=full,
                title=title,
                company=company,
                location=location,
                contract=contract or "Alternance",
                salary=salary,
                description=description,
            )
        )
    return out
