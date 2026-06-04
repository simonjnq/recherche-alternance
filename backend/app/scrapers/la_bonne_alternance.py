"""Scraper La Bonne Alternance (API officielle France Travail / beta.gouv).

On utilise httpx et non Playwright : l'API est publique (pas d'auth pour /jobs/search).
Si les endpoints évoluent, on essaie plusieurs variantes.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, AsyncIterator

import httpx

from ..models import OfferRaw
from .base import Scraper, pick_user_agent, polite_delay

logger = logging.getLogger(__name__)

# Endpoint public (pas d'auth requise) : v1/jobsEtFormations sur .beta.gouv.fr.
# v3 existe mais exige un Bearer token (inscription développeur).
LBA_BASE = "https://labonnealternance.apprentissage.beta.gouv.fr"
LBA_ENDPOINTS = [f"{LBA_BASE}/api/v1/jobsEtFormations"]
GEO_API = "https://geo.api.gouv.fr/communes"

# Codes ROME pertinents tech/IA/growth/produit
DEFAULT_ROMES = [
    "M1805",  # Études et développement informatique
    "M1810",  # Production et exploitation de systèmes d'information
    "E1101",  # Animation de site multimédia
    "M1703",  # Management et gestion de produit
    "M1402",  # Conseil en organisation et management d'entreprise
    "E1402",  # Élaboration de plan média
]

CALLER = "recherche-alternance-local"
FRANCE_TRAVAIL_SEARCH = (
    "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
)
FRANCE_TRAVAIL_TOKEN_URL = (
    "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
)


class LaBonneAlternanceScraper(Scraper):
    source = "la_bonne_alternance"

    async def search(
        self, keywords: list[str], location: str, max_per_source: int
    ) -> AsyncIterator[OfferRaw]:
        yielded = 0
        seen_urls: set[str] = set()

        async with httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": pick_user_agent(), "Accept": "application/json"},
            follow_redirects=True,
        ) as client:
            insee = await _geocode_insee(client, location)
            logger.info("LBA: location=%r → insee=%s", location, insee)

            # 1) API LBA publique
            try:
                async for offer in self._search_lba(
                    client, keywords, insee, seen_urls, max_per_source - yielded
                ):
                    yield offer
                    yielded += 1
                    if yielded >= max_per_source:
                        return
            except Exception as e:
                logger.warning("LBA public API failed: %s", e)

            # 2) (optionnel) France Travail si OAuth configuré
            client_id = os.getenv("FRANCE_TRAVAIL_CLIENT_ID", "").strip()
            client_secret = os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET", "").strip()
            if client_id and client_secret:
                try:
                    token = await self._get_ft_token(client, client_id, client_secret)
                    if token:
                        async for offer in self._search_france_travail(
                            client, token, keywords, seen_urls, max_per_source - yielded
                        ):
                            yield offer
                            yielded += 1
                            if yielded >= max_per_source:
                                return
                except Exception as e:
                    logger.warning("France Travail fallback failed: %s", e)
            else:
                logger.info(
                    "FRANCE_TRAVAIL_CLIENT_ID/SECRET absents — fallback France Travail ignoré."
                )

    # ------------------------------------------------------------------
    # LBA public
    # ------------------------------------------------------------------
    async def _search_lba(
        self,
        client: httpx.AsyncClient,
        keywords: list[str],
        insee: str,
        seen_urls: set[str],
        remaining: int,
    ) -> AsyncIterator[OfferRaw]:
        if remaining <= 0:
            return

        # /api/v1/jobsEtFormations exige insee. On couvre un large rayon pour maximiser
        # les résultats et on filtre côté client via keywords.
        params = {
            "romes": ",".join(DEFAULT_ROMES),
            "caller": CALLER,
            "insee": insee,
            "radius": 30,
        }

        raw: dict[str, Any] | None = None
        for endpoint in LBA_ENDPOINTS:
            try:
                r = await client.get(endpoint, params=params)
                if r.status_code != 200:
                    logger.debug("LBA %s → %s", endpoint, r.status_code)
                    continue
                raw = r.json()
                logger.info("LBA endpoint OK: %s", endpoint)
                break
            except Exception as e:
                logger.debug("LBA %s fail: %s", endpoint, e)
                continue
            finally:
                await polite_delay(0.5, 1.5)

        if not raw:
            logger.warning("LBA: aucun endpoint n'a répondu.")
            return

        jobs = _extract_lba_jobs(raw)
        logger.info("LBA: %d offres brutes", len(jobs))

        # Filtre par tokens individuels (mot par mot) — plus permissif qu'un match de phrase.
        # Les offres passent aussi si la liste keywords est vide.
        # La pertinence fine est tranchée par le scoring LLM.
        kw_tokens = _keyword_tokens(keywords)
        seen_dedup: set[str] = set()
        yielded = 0
        for job in jobs:
            offer = _lba_job_to_offer(job)
            if not offer:
                continue
            if offer.url in seen_urls:
                continue
            # LBA renvoie massivement le même poste dupliqué (même peJobs 20x pour une même
            # annonce). On dedup par titre+entreprise+lieu avant de yield.
            dk = offer.dedup_key()
            if dk in seen_dedup:
                continue
            seen_dedup.add(dk)
            if kw_tokens and not _matches_any_token(offer, kw_tokens):
                continue
            seen_urls.add(offer.url)
            yield offer
            yielded += 1
            if yielded >= remaining:
                return

    # ------------------------------------------------------------------
    # France Travail (optionnel, OAuth)
    # ------------------------------------------------------------------
    async def _get_ft_token(
        self, client: httpx.AsyncClient, client_id: str, client_secret: str
    ) -> str | None:
        try:
            r = await client.post(
                FRANCE_TRAVAIL_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": "api_offresdemploiv2 o2dsoffre",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15.0,
            )
            if r.status_code != 200:
                logger.warning("France Travail token: HTTP %s", r.status_code)
                return None
            return r.json().get("access_token")
        except Exception as e:
            logger.warning("France Travail token error: %s", e)
            return None

    async def _search_france_travail(
        self,
        client: httpx.AsyncClient,
        token: str,
        keywords: list[str],
        seen_urls: set[str],
        remaining: int,
    ) -> AsyncIterator[OfferRaw]:
        if remaining <= 0:
            return
        headers = {"Authorization": f"Bearer {token}"}
        yielded = 0
        for kw in keywords:
            if yielded >= remaining:
                break
            try:
                r = await client.get(
                    FRANCE_TRAVAIL_SEARCH,
                    params={
                        "motsCles": kw,
                        "typeContrat": "E2,FS",  # E2 apprentissage, FS alternance pro
                        "range": "0-49",
                    },
                    headers=headers,
                )
                if r.status_code not in (200, 206):
                    logger.debug("FT %r → %s", kw, r.status_code)
                    continue
                data = r.json()
                for job in data.get("resultats", []):
                    offer = _ft_job_to_offer(job)
                    if not offer or offer.url in seen_urls:
                        continue
                    seen_urls.add(offer.url)
                    yield offer
                    yielded += 1
                    if yielded >= remaining:
                        return
            except Exception as e:
                logger.warning("FT keyword %r failed: %s", kw, e)
                continue
            finally:
                await polite_delay(1.0, 2.5)


# ----------------------------------------------------------------------
# Helpers de parsing
# ----------------------------------------------------------------------
def _extract_lba_jobs(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """La réponse /api/v1/jobsEtFormations a la forme:
    {formations: {results:[...]}, jobs: {peJobs:{results:[]}, matchas:{results:[]},
                                           partnerJobs:{results:[]}, lbaCompanies:{results:[]}}}
    On ne garde que les vraies offres d'emploi (pas les lbaCompanies qui sont des leads
    sans poste précis).
    """
    jobs: list[dict[str, Any]] = []
    containers = raw.get("jobs") if isinstance(raw.get("jobs"), dict) else raw
    if not isinstance(containers, dict):
        return jobs
    for key in ("peJobs", "matchas", "partnerJobs"):
        v = containers.get(key)
        if isinstance(v, dict):
            results = v.get("results")
            if isinstance(results, list):
                jobs.extend(results)
        elif isinstance(v, list):
            jobs.extend(v)
    return jobs


async def _geocode_insee(client: httpx.AsyncClient, city: str) -> str:
    """Convertit un nom de ville en code INSEE via geo.api.gouv.fr. Fallback Paris."""
    fallback = "75056"  # Paris
    city = (city or "").strip()
    if not city:
        return fallback
    try:
        r = await client.get(
            GEO_API,
            params={"nom": city, "fields": "code,nom,population", "limit": 5, "boost": "population"},
            timeout=10.0,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                code = data[0].get("code")
                if code:
                    return str(code)
    except Exception as e:
        logger.debug("Geo lookup failed for %r: %s", city, e)
    return fallback


def _lba_job_to_offer(job: dict[str, Any]) -> OfferRaw | None:
    try:
        title = (
            job.get("title")
            or job.get("intitule")
            or (job.get("job") or {}).get("title")
            or (job.get("offer") or {}).get("title")
            or ""
        ).strip()
        if not title:
            return None

        company = None
        comp = job.get("company") or job.get("entreprise") or {}
        if isinstance(comp, dict):
            company = comp.get("name") or comp.get("nom")
        company = company or job.get("companyName")

        location = None
        place = job.get("place") or job.get("lieuTravail") or {}
        if isinstance(place, dict):
            location = place.get("fullAddress") or place.get("city") or place.get("libelle")
        location = location or job.get("city")

        # URL : priorité à une URL canonique, sinon fallback sur l'ID LBA
        url = (
            job.get("url")
            or job.get("applicationUrl")
            or job.get("origineOffre", {}).get("urlOrigine")
            if isinstance(job.get("origineOffre"), dict)
            else job.get("url")
        )
        if not url:
            jid = job.get("id") or job.get("_id") or job.get("jobId")
            if jid:
                url = f"https://labonnealternance.apprentissage.beta.gouv.fr/recherche-apprentissage?job={jid}"
            else:
                return None

        description = (
            job.get("description")
            or (job.get("job") or {}).get("description")
            or job.get("jobDescription")
            or ""
        )
        contract = job.get("contractType") or job.get("typeContrat") or "Alternance"

        return OfferRaw(
            source="la_bonne_alternance",
            url=str(url),
            title=title,
            company=company,
            location=location,
            contract=str(contract) if contract else "Alternance",
            description=str(description)[:20000],
        )
    except Exception as e:
        logger.debug("LBA parse error: %s", e)
        return None


def _ft_job_to_offer(job: dict[str, Any]) -> OfferRaw | None:
    try:
        title = (job.get("intitule") or "").strip()
        if not title:
            return None
        company = (job.get("entreprise") or {}).get("nom")
        location = (job.get("lieuTravail") or {}).get("libelle")
        url = (job.get("origineOffre") or {}).get("urlOrigine") or (
            f"https://candidat.francetravail.fr/offres/recherche/detail/{job.get('id', '')}"
        )
        desc = job.get("description") or ""
        contract = job.get("typeContratLibelle") or job.get("typeContrat") or "Alternance"
        return OfferRaw(
            source="la_bonne_alternance",
            url=str(url),
            title=title,
            company=company,
            location=location,
            contract=str(contract),
            description=str(desc)[:20000],
        )
    except Exception as e:
        logger.debug("FT parse error: %s", e)
        return None


def _matches_any_keyword(offer: OfferRaw, kw_lower: list[str]) -> bool:
    hay = f"{offer.title} {offer.company or ''} {offer.description}".lower()
    return any(kw in hay for kw in kw_lower)


# Tokens à ignorer quand on tokenise les keywords utilisateur (trop génériques).
_STOP_TOKENS = {
    "alternance", "apprentissage", "paris", "ile", "france",
    "de", "du", "la", "le", "les", "et", "ou", "en", "un", "une",
    "pour", "sur", "par", "avec", "dans", "des",
}


def _keyword_tokens(keywords: list[str]) -> set[str]:
    """Casse chaque keyword en mots, garde ceux >= 2 chars et non-stop.

    min_len=2 pour laisser passer IA, AI, PM, UX, UI — sigles importants.
    """
    out: set[str] = set()
    for k in keywords:
        for tok in re.split(r"[^a-zA-Z0-9]+", k.lower()):
            if len(tok) >= 2 and tok not in _STOP_TOKENS:
                out.add(tok)
    return out


def _matches_any_token(offer: OfferRaw, tokens: set[str]) -> bool:
    hay = f"{offer.title} {offer.company or ''} {offer.description}".lower()
    return any(tok in hay for tok in tokens)
