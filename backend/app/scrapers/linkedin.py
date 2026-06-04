"""Scraper LinkedIn — endpoint public "invité" (jobs-guest), sans login.

IMPORTANT : on n'utilise JAMAIS de session connectée ici. L'endpoint
`/jobs-guest/jobs/api/...` est servi publiquement par LinkedIn, sans cookie ni
compte → aucun risque pour le compte utilisateur. Le seul risque est un
rate-limiting par IP (429) : on reste donc conservateur (1 page/mot-clé, délais,
échec silencieux) et la source est désactivable comme les autres.

LinkedIn n'expose pas de filtre "alternance" fiable côté requête : on l'obtient
en suffixant chaque mot-clé par « alternance », puis on récupère la description
réelle de chaque offre gardée (endpoint jobPosting invité) pour que le filtre
alternance central + le scoring travaillent sur du vrai texte.
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

BASE_URL = "https://www.linkedin.com"
SEARCH_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    "?keywords={kw}&location={loc}&f_TPR=r604800&start={start}"  # r604800 = 7 derniers jours
)
JOB_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

_JOB_ID_RE = re.compile(r"(?:/jobs/view/|currentJobId=|jobPosting:)(\d{6,})")


class LinkedInScraper(Scraper):
    source = "linkedin"
    budget_s = 50.0
    pages = 1                  # conservateur : 1 page (~25 offres) par mot-clé
    parallel_keywords = 2
    detail_concurrency = 3     # fetch description : limité pour ménager l'IP

    async def search(
        self, keywords: list[str], location: str, max_per_source: int
    ) -> AsyncIterator[OfferRaw]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1) Récupère les cards (titre/entreprise/lieu/url) pour tous les mots-clés.
            kw_sem = asyncio.Semaphore(self.parallel_keywords)

            async def list_one(kw: str) -> list[dict]:
                async with kw_sem:
                    res = await self._list_keyword(client, kw, location)
                    await polite_delay(0.5, 1.4)
                    return res

            tasks = [asyncio.create_task(list_one(kw)) for kw in keywords]
            cards: list[dict] = []
            seen_ids: set[str] = set()
            try:
                for task in asyncio.as_completed(tasks):
                    for c in await task:
                        if c["job_id"] in seen_ids:
                            continue
                        seen_ids.add(c["job_id"])
                        cards.append(c)
            finally:
                for t in tasks:
                    if not t.done():
                        t.cancel()

            cards = cards[:max_per_source]
            logger.info("LinkedIn: %d cards uniques à enrichir", len(cards))

            # 2) Enrichit avec la description réelle (best-effort) puis yield.
            det_sem = asyncio.Semaphore(self.detail_concurrency)

            async def enrich(c: dict) -> OfferRaw:
                async with det_sem:
                    desc, contract = await self._fetch_detail(client, c["job_id"])
                    await polite_delay(0.4, 1.0)
                return OfferRaw(
                    source="linkedin",
                    url=c["url"],
                    title=c["title"],
                    company=c.get("company"),
                    location=c.get("location"),
                    contract=contract,
                    description=desc or c.get("title") or "",
                    posted_at=c.get("posted_at"),
                )

            enrich_tasks = [asyncio.create_task(enrich(c)) for c in cards]
            try:
                for task in asyncio.as_completed(enrich_tasks):
                    yield await task
            finally:
                for t in enrich_tasks:
                    if not t.done():
                        t.cancel()

    async def _list_keyword(
        self, client: httpx.AsyncClient, keyword: str, location: str
    ) -> list[dict]:
        # LinkedIn n'a pas de filtre contrat "alternance" → on le force dans la requête.
        q = keyword if re.search(r"alternan|apprenti", keyword, re.I) else f"{keyword} alternance"
        out: list[dict] = []
        for page in range(self.pages):
            url = SEARCH_URL.format(
                kw=quote_plus(q), loc=quote_plus(location or "France"), start=page * 25
            )
            status, body = await fetch_text(client, url, referer=BASE_URL + "/jobs")
            if status != 200 or not body:
                logger.info("LinkedIn kw=%r p=%d → HTTP %s", keyword, page, status)
                break
            cards = _parse_cards(body)
            if not cards:
                break
            out.extend(cards)
            if page + 1 < self.pages:
                await polite_delay(0.5, 1.2)
        logger.info("LinkedIn kw=%r → %d cards", keyword, len(out))
        return out

    async def _fetch_detail(
        self, client: httpx.AsyncClient, job_id: str
    ) -> tuple[str, str | None]:
        """Description + type de contrat depuis l'endpoint jobPosting invité. Best-effort."""
        url = JOB_DETAIL_URL.format(job_id=job_id)
        status, body = await fetch_text(client, url, referer=BASE_URL + "/jobs", timeout=10.0)
        if status != 200 or not body:
            return "", None
        return _parse_detail(body)


# ---------------------------------------------------------------------------
# Parsing HTML (bs4)
# ---------------------------------------------------------------------------

def _parse_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for li in soup.select("li"):
        link = li.select_one("a.base-card__full-link, a.base-search-card__title-link, a[href*='/jobs/view/']")
        href = (link.get("href") if link else "") or ""
        job_id = _job_id_from(li, href)
        if not job_id:
            continue
        title_el = li.select_one("h3.base-search-card__title, h3")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            continue
        comp_el = li.select_one("h4.base-search-card__subtitle, a.hidden-nested-link, h4")
        company = comp_el.get_text(strip=True) if comp_el else None
        loc_el = li.select_one("span.job-search-card__location")
        location = loc_el.get_text(strip=True) if loc_el else None
        time_el = li.select_one("time")
        posted_at = (time_el.get("datetime") if time_el else None) or None
        out.append({
            "job_id": job_id,
            "url": f"{BASE_URL}/jobs/view/{job_id}",
            "title": title,
            "company": company,
            "location": location,
            "posted_at": posted_at,
        })
    return out


def _job_id_from(li, href: str) -> str | None:
    # 1) data-entity-urn="urn:li:jobPosting:1234"
    div = li.select_one("[data-entity-urn]")
    if div:
        m = _JOB_ID_RE.search(div.get("data-entity-urn") or "")
        if m:
            return m.group(1)
    # 2) depuis le href de la card
    m = _JOB_ID_RE.search(href)
    return m.group(1) if m else None


def _parse_detail(html: str) -> tuple[str, str | None]:
    soup = BeautifulSoup(html, "lxml")
    desc_el = soup.select_one(
        "div.show-more-less-html__markup, div.description__text, section.description"
    )
    description = desc_el.get_text("\n", strip=True)[:20000] if desc_el else ""

    contract: str | None = None
    # Critères "Type d'emploi : Alternance / CDI / Stage…"
    for item in soup.select("li.description__job-criteria-item"):
        head = item.select_one("h3, .description__job-criteria-subheader")
        val = item.select_one("span, .description__job-criteria-text")
        if not head or not val:
            continue
        label = head.get_text(strip=True).lower()
        if "type" in label and ("emploi" in label or "contrat" in label):
            contract = val.get_text(strip=True)
            break
    return description, contract
