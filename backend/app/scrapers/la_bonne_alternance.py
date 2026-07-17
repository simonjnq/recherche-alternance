"""Scraper La Bonne Alternance — nouvelle API v3 (api.apprentissage.beta.gouv.fr).

L'ancienne API publique (labonnealternance.apprentissage.beta.gouv.fr/api/v1/...)
a été DÉCOMMISSIONNÉE (HTTP 410). La nouvelle exige une clé d'API gratuite :
  1. Créer un compte sur https://api.apprentissage.beta.gouv.fr
  2. Générer un jeton, le mettre dans .env :  LBA_API_KEY=...
Sans clé, la source est simplement ignorée (log explicite), les autres tournent.

Fallback optionnel : France Travail (OAuth) si FRANCE_TRAVAIL_CLIENT_ID/SECRET.
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

# Nouvelle API v3 (clé requise).
LBA_V3_SEARCH = "https://api.apprentissage.beta.gouv.fr/api/job/v1/search"
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

FRANCE_TRAVAIL_SEARCH = (
    "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
)
FRANCE_TRAVAIL_TOKEN_URL = (
    "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
)

PARIS_LATLON = (48.8566, 2.3522)


class LaBonneAlternanceScraper(Scraper):
    source = "la_bonne_alternance"

    def unavailable(self) -> str | None:
        if not os.getenv("LBA_API_KEY", "").strip():
            return (
                "clé LBA_API_KEY manquante — clé gratuite sur "
                "api.apprentissage.beta.gouv.fr, puis LBA_API_KEY=... dans .env"
            )
        return None

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
            lat, lon = await _geocode_latlon(client, location)
            logger.info("LBA: location=%r → lat=%.4f lon=%.4f", location, lat, lon)

            # 1) API LBA v3 (clé requise)
            try:
                async for offer in self._search_v3(
                    client, keywords, lat, lon, seen_urls, max_per_source - yielded
                ):
                    yield offer
                    yielded += 1
                    if yielded >= max_per_source:
                        return
            except Exception as e:
                logger.warning("LBA v3 failed: %s", e)

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

    # ------------------------------------------------------------------
    # LBA v3
    # ------------------------------------------------------------------
    async def _search_v3(
        self,
        client: httpx.AsyncClient,
        keywords: list[str],
        lat: float,
        lon: float,
        seen_urls: set[str],
        remaining: int,
    ) -> AsyncIterator[OfferRaw]:
        if remaining <= 0:
            return
        api_key = os.getenv("LBA_API_KEY", "").strip()
        if not api_key:
            logger.warning(
                "LBA: LBA_API_KEY absente — source ignorée. Crée une clé gratuite sur "
                "https://api.apprentissage.beta.gouv.fr puis ajoute LBA_API_KEY=... dans .env"
            )
            return

        params = {
            "latitude": f"{lat:.6f}",
            "longitude": f"{lon:.6f}",
            "radius": "30",
            "romes": ",".join(DEFAULT_ROMES),
        }
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        try:
            r = await client.get(LBA_V3_SEARCH, params=params, headers=headers)
        except Exception as e:
            logger.warning("LBA v3 request error: %s", e)
            return
        if r.status_code == 401:
            logger.warning("LBA v3: 401 — clé LBA_API_KEY invalide/expirée.")
            return
        if r.status_code not in (200, 206):
            logger.info("LBA v3 → HTTP %s", r.status_code)
            return
        try:
            data = r.json()
        except Exception:
            return

        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            logger.info("LBA v3: réponse inattendue (pas de 'jobs').")
            return
        logger.info("LBA v3: %d offres brutes", len(jobs))

        kw_tokens = _keyword_tokens(keywords)
        seen_dedup: set[str] = set()
        yielded = 0
        for job in jobs:
            offer = _v3_job_to_offer(job)
            if not offer or offer.url in seen_urls:
                continue
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
        await polite_delay(0.3, 0.8)

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
async def _geocode_latlon(client: httpx.AsyncClient, city: str) -> tuple[float, float]:
    """Nom de ville → (lat, lon) via geo.api.gouv.fr. Fallback Paris."""
    city = (city or "").strip()
    if not city:
        return PARIS_LATLON
    try:
        r = await client.get(
            GEO_API,
            params={"nom": city, "fields": "centre", "boost": "population", "limit": 1},
            timeout=10.0,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                coords = ((data[0] or {}).get("centre") or {}).get("coordinates")
                if isinstance(coords, list) and len(coords) == 2:
                    lon, lat = float(coords[0]), float(coords[1])
                    return lat, lon
    except Exception as e:
        logger.debug("Geo lookup failed for %r: %s", city, e)
    return PARIS_LATLON


def _v3_job_to_offer(job: dict[str, Any]) -> OfferRaw | None:
    """Mappe un job de l'API v3 ({offer, workplace, apply, contract}) en OfferRaw."""
    try:
        if not isinstance(job, dict):
            return None
        offer = job.get("offer") or {}
        workplace = job.get("workplace") or {}
        apply = job.get("apply") or {}
        contract = job.get("contract") or {}

        title = (offer.get("title") or "").strip()
        if not title:
            return None

        company = (
            workplace.get("name")
            or workplace.get("brand")
            or workplace.get("legal_name")
        )

        location = None
        loc = workplace.get("location") or {}
        if isinstance(loc, dict):
            location = loc.get("address")

        url = apply.get("url")
        if not url:
            jid = (job.get("identifier") or {}).get("id")
            if not jid:
                return None
            url = f"https://labonnealternance.apprentissage.beta.gouv.fr/recherche?type=offre&itemId={jid}"

        ctype = contract.get("type")
        if isinstance(ctype, list) and ctype:
            contract_str = ", ".join(str(x) for x in ctype)
        elif isinstance(ctype, str) and ctype:
            contract_str = ctype
        else:
            contract_str = "Alternance"

        description = str(offer.get("description") or "")[:20000]
        posted = None
        pub = offer.get("publication") or {}
        if isinstance(pub, dict):
            posted = pub.get("creation")

        return OfferRaw(
            source="la_bonne_alternance",
            url=str(url),
            title=title,
            company=company,
            location=location,
            contract=contract_str,
            description=description,
            posted_at=posted,
        )
    except Exception as e:
        logger.debug("LBA v3 parse error: %s", e)
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


# Tokens à ignorer quand on tokenise les keywords utilisateur (trop génériques).
_STOP_TOKENS = {
    "alternance", "apprentissage", "paris", "ile", "france",
    "de", "du", "la", "le", "les", "et", "ou", "en", "un", "une",
    "pour", "sur", "par", "avec", "dans", "des",
}


def _keyword_tokens(keywords: list[str]) -> set[str]:
    """Casse chaque keyword en mots, garde ceux >= 2 chars et non-stop."""
    out: set[str] = set()
    for k in keywords:
        for tok in re.split(r"[^a-zA-Z0-9]+", k.lower()):
            if len(tok) >= 2 and tok not in _STOP_TOKENS:
                out.add(tok)
    return out


def _matches_any_token(offer: OfferRaw, tokens: set[str]) -> bool:
    hay = f"{offer.title} {offer.company or ''} {offer.description}".lower()
    return any(tok in hay for tok in tokens)
