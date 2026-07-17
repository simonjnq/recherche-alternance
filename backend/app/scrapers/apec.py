"""Scraper APEC — API publique JSON (POST /cms/webservices/rechercheOffre).

L'Apec utilise un webservice JSON pour leur recherche : on l'appelle directement,
zéro Playwright. Plus rapide, plus fiable et plus propre que de scraper la SPA.

`typesContrat` :
- 101888 : Apprentissage
- 101889 : Professionnalisation
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, AsyncIterator

import httpx

from ..models import OfferRaw
from .base import Scraper, browser_headers, polite_delay

logger = logging.getLogger(__name__)

API_URL = "https://www.apec.fr/cms/webservices/rechercheOffre"
JOB_URL_TMPL = "https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/{num}"


class ApecScraper(Scraper):
    source = "apec"
    budget_s = 45.0
    parallel_keywords = 3
    per_keyword = 50

    async def search(
        self, keywords: list[str], location: str, max_per_source: int
    ) -> AsyncIterator[OfferRaw]:
        seen: set[str] = set()
        yielded = 0
        headers = {
            **browser_headers(referer="https://www.apec.fr/candidat/recherche-emploi.html/emploi"),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            sem = asyncio.Semaphore(self.parallel_keywords)

            async def one(kw: str) -> list[OfferRaw]:
                async with sem:
                    res = await self._search_kw(client, kw, location)
                    await polite_delay(0.3, 0.9)
                    return res

            tasks = [asyncio.create_task(one(kw)) for kw in keywords]
            try:
                for task in asyncio.as_completed(tasks):
                    for o in await task:
                        if o.url in seen:
                            continue
                        seen.add(o.url)
                        yield o
                        yielded += 1
                        if yielded >= max_per_source:
                            return
            finally:
                for t in tasks:
                    if not t.done():
                        t.cancel()

    async def _search_kw(
        self, client: httpx.AsyncClient, keyword: str, location: str
    ) -> list[OfferRaw]:
        payload: dict[str, Any] = {
            "motsCles": keyword,
            "typesContrat": ["101888", "101889"],     # Apprentissage + Professionnalisation
            "sorts": [{"type": "DATE", "direction": "DESCENDING"}],  # priorise le frais
            "pagination": {"startIndex": 0, "range": self.per_keyword},
        }
        # La zone géographique de l'API exige des codes INSEE complexes. On filtre côté
        # client : on garde toutes les offres dont la lieuTexte contient `location`
        # (insensible à la casse / aux accents).
        target_loc = (location or "").strip().lower()

        try:
            r = await client.post(API_URL, json=payload)
        except Exception as e:
            logger.warning("Apec kw=%r: %s", keyword, e)
            return []
        if r.status_code != 200:
            logger.info("Apec kw=%r → HTTP %s", keyword, r.status_code)
            return []
        try:
            data = r.json()
        except Exception:
            return []
        rows = data.get("resultats") or data.get("offres") or []
        offers: list[OfferRaw] = []
        for row in rows:
            o = _row_to_offer(row)
            if not o:
                continue
            if target_loc and o.location and target_loc not in o.location.lower():
                continue
            offers.append(o)
        logger.info("Apec kw=%r → %d offres (loc=%s)", keyword, len(offers), target_loc or "FR")
        return offers


def _row_to_offer(r: dict[str, Any]) -> OfferRaw | None:
    try:
        num = (r.get("numeroOffre") or "").strip()
        if not num:
            return None
        title = (r.get("intitule") or "").strip()
        if not title:
            return None
        company = (r.get("nomCommercial") or r.get("entreprise") or "").strip() or None
        location = (r.get("lieuTexte") or "").strip() or None
        salary = (r.get("salaireTexte") or "").strip() or None
        raw_text = r.get("texteOffre") or ""
        text = re.sub(r"<[^>]+>", " ", raw_text)
        text = re.sub(r"\s+", " ", text).strip()[:3000]
        url = JOB_URL_TMPL.format(num=num)
        return OfferRaw(
            source="apec",
            url=url,
            title=title,
            company=company,
            location=location,
            # PAS de contrat en dur : l'API APEC renvoie typeContrat=101888
            # ("Apprentissage") même pour des postes seniors/CDI — son filtre
            # typesContrat n'est pas fiable. On laisse None : le filtre alternance
            # central tranche à partir du texte réel de l'offre.
            contract=None,
            salary=salary,
            description=text,
        )
    except Exception as e:
        logger.debug("Apec parse error: %s", e)
        return None
