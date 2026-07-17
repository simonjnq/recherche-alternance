"""Interface commune des scrapers + helpers httpx/JSON.

Un scraper produit des OfferRaw à partir de mots-clés. `safe_search` accepte un
budget temps et un callback live pour le progrès.
"""
from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from typing import AsyncIterator, Awaitable, Callable, Optional

import httpx

from ..models import OfferRaw, Source

OnOfferCb = Optional[Callable[[OfferRaw], Awaitable[None]]]

logger = logging.getLogger(__name__)

USER_AGENTS = [
    # Chrome récents (Mac, Windows, Linux) — limites les fingerprintings simples
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Firefox récents
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Safari Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
]

# UA mobiles — Indeed mobile est moins protégé.
MOBILE_USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
]


def pick_user_agent() -> str:
    return random.choice(USER_AGENTS)


def pick_mobile_user_agent() -> str:
    return random.choice(MOBILE_USER_AGENTS)


async def polite_delay(min_s: float = 0.5, max_s: float = 1.6) -> None:
    await asyncio.sleep(random.uniform(min_s, max_s))


def browser_headers(referer: str | None = None, mobile: bool = False) -> dict[str, str]:
    """En-têtes proches d'un navigateur réel — beaucoup de sites filtrent l'absence de Sec-Fetch-*."""
    ua = pick_mobile_user_agent() if mobile else pick_user_agent()
    h = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        # On omet 'br' — brotli n'est pas décodé sans le paquet `brotli` (pas dans requirements).
        "Accept-Encoding": "gzip, deflate",
        "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?1" if mobile else "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none" if referer is None else "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",
        "Connection": "keep-alive",
    }
    if referer:
        h["Referer"] = referer
    return h


class Scraper(ABC):
    source: Source
    max_per_keyword: int = 10
    # Budget par défaut (s) : si la méthode `search` n'a pas terminé dans ce délai,
    # on coupe et on garde ce qui a été yield. La pipeline le surcharge.
    budget_s: float = 90.0

    def unavailable(self) -> Optional[str]:
        """Raison pour laquelle la source est inutilisable (ex. clé d'API manquante),
        ou None si elle est prête. Permet à la pipeline de l'afficher comme « ignorée »
        au lieu de la lancer pour rien et de renvoyer 0 sans explication."""
        return None

    @abstractmethod
    async def search(self, keywords: list[str], location: str, max_per_source: int) -> AsyncIterator[OfferRaw]:
        """Yield des OfferRaw. Doit gérer ses erreurs en interne (log + skip)."""
        raise NotImplementedError
        yield  # pragma: no cover

    async def safe_search(
        self,
        keywords: list[str],
        location: str,
        max_per_source: int,
        on_offer: OnOfferCb = None,
        budget_s: float | None = None,
    ) -> list[OfferRaw]:
        """Wrapper qui catch tout + applique un budget temps.

        Un scraper qui plante ou prend trop longtemps ne bloque JAMAIS les autres.
        Si `on_offer` est fourni, appelé à chaque offre trouvée (progrès live).
        """
        results: list[OfferRaw] = []
        deadline = asyncio.get_event_loop().time() + (budget_s or self.budget_s)

        async def _run() -> None:
            try:
                async for offer in self.search(keywords, location, max_per_source):
                    results.append(offer)
                    if on_offer is not None:
                        try:
                            await on_offer(offer)
                        except Exception as e:
                            logger.debug("on_offer callback failed: %s", e)
                    if len(results) >= max_per_source:
                        break
                    if asyncio.get_event_loop().time() > deadline:
                        logger.info("Scraper %s: budget atteint, on coupe", self.source)
                        break
            except Exception as e:
                logger.exception("Scraper %s failed: %s", self.source, e)

        try:
            await asyncio.wait_for(
                _run(),
                timeout=max(1.0, deadline - asyncio.get_event_loop().time()),
            )
        except asyncio.TimeoutError:
            logger.warning("Scraper %s: timeout dur (%ss) — on garde %d offres déjà collectées",
                           self.source, budget_s or self.budget_s, len(results))
        return results


# ---------------------------------------------------------------------------
# Helpers httpx — utilisés par les scrapers "no-Playwright" (WTTJ, Indeed v2)
# ---------------------------------------------------------------------------

async def fetch_text(
    client: httpx.AsyncClient,
    url: str,
    referer: str | None = None,
    mobile: bool = False,
    timeout: float = 12.0,
) -> tuple[int, str]:
    """GET avec headers navigateur + retours (status, body). Ne lève jamais."""
    try:
        r = await client.get(
            url,
            headers=browser_headers(referer=referer, mobile=mobile),
            timeout=timeout,
            follow_redirects=True,
        )
        return r.status_code, r.text or ""
    except Exception as e:
        logger.debug("fetch_text %s failed: %s", url, e)
        return 0, ""
