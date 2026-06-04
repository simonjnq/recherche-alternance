"""LinkedIn — mode manuel uniquement.

L'utilisateur colle une URL d'offre LinkedIn. On charge la page via Playwright
et on extrait ce qu'on peut (OG metadata + contenu visible public).
LinkedIn affiche souvent un wall d'authentification : on retombe alors sur les
métadonnées OG (titre, description, company) qui restent accessibles.
"""
from __future__ import annotations

import logging
import re

from playwright.async_api import TimeoutError as PWTimeoutError, async_playwright

try:
    from playwright_stealth import stealth_async  # type: ignore
except Exception:  # pragma: no cover
    async def stealth_async(page):  # type: ignore
        return None

from ..models import OfferRaw
from .base import pick_user_agent, polite_delay

logger = logging.getLogger(__name__)


async def parse_linkedin_url(url: str) -> OfferRaw:
    title = ""
    company: str | None = None
    location: str | None = None
    description = ""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent=pick_user_agent(),
                locale="fr-FR",
                viewport={"width": 1440, "height": 900},
            )
            page = await context.new_page()
            try:
                await stealth_async(page)
            except Exception:
                pass

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except PWTimeoutError:
                logger.warning("LinkedIn timeout on %s", url)

            await polite_delay(1.0, 2.0)

            # 1) Contenu public visible (si accessible sans login)
            try:
                title_el = await page.query_selector(
                    "h1.top-card-layout__title, h1.topcard__title, h1"
                )
                if title_el:
                    title = (await title_el.inner_text()).strip()
            except Exception:
                pass

            try:
                company_el = await page.query_selector(
                    "a.topcard__org-name-link, span.topcard__flavor--black-link, a[data-tracking-control-name='public_jobs_topcard-org-name']"
                )
                if company_el:
                    company = (await company_el.inner_text()).strip()
            except Exception:
                pass

            try:
                loc_el = await page.query_selector(
                    "span.topcard__flavor--bullet, span.topcard__flavor:nth-of-type(2)"
                )
                if loc_el:
                    location = (await loc_el.inner_text()).strip()
            except Exception:
                pass

            try:
                desc_el = await page.query_selector(
                    "div.show-more-less-html__markup, div.description__text, section.description"
                )
                if desc_el:
                    description = (await desc_el.inner_text()).strip()
            except Exception:
                pass

            # 2) Fallback OG metadata
            if not title:
                og_title = await page.evaluate(
                    "() => document.querySelector('meta[property=\"og:title\"]')?.content || ''"
                )
                title = (og_title or "").strip()
            if not description:
                og_desc = await page.evaluate(
                    "() => document.querySelector('meta[property=\"og:description\"]')?.content || ''"
                )
                description = (og_desc or "").strip()

            if title and not company:
                m = re.search(r" chez ([^|·\-]+)$", title)
                if m:
                    company = m.group(1).strip()
        finally:
            await browser.close()

    if not title:
        title = "Offre LinkedIn (titre non extrait — ouvrir le lien)"

    return OfferRaw(
        source="linkedin_manual",
        url=url,
        title=title,
        company=company,
        location=location,
        contract=None,
        description=description or "Contenu non accessible publiquement. Ouvrir le lien dans le navigateur pour voir l'offre complète.",
    )
