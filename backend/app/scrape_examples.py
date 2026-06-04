"""Scrape de conseils pros de rédaction CV / lettre de motivation.

Source : welcometothejungle.com (articles SEO, corps rendu côté serveur).
On récupère le sitemap d'articles, on filtre les URLs pertinentes (lettre,
cv, alternance, candidature, motivation) et on extrait le texte du <main>.

Usage :
    python -m app.scrape_examples
"""
from __future__ import annotations

import asyncio
import gzip
import logging
import random
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "examples" / "advice"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

SITEMAP_URL = "https://www.welcometothejungle.com/sitemaps/articles.0.xml.gz"

# On veut des articles FR qui parlent du "comment" rédiger / adapter un CV ou une lettre.
# On exclut les articles orientés recruteurs ou statistiques.
INCLUDE_KEYS = ("lettre-de-motivation", "lettre-motivation", "letre-motivation", "-cv-", "/cv-", "cv-", "-alternance-", "candidature")
EXCLUDE_KEYS = (
    "recruteurs-",
    "recruteur-",
    "employer-brand",
    "marque-employeur",
    "trop-candidatures",
    "pires-refus",
    "culot-embauche",
    "cv-inverses",
    "recruter-sans-cv",
    "stats",
    "burn-out",
    "demission",
    "travail-reconversion",
)
FR_PREFIX = "https://www.welcometothejungle.com/fr/"

MAX_ARTICLES = 18  # objectif ~15 conseils de qualité, +3 de marge


@dataclass
class Advice:
    url: str
    title: str
    body: str
    topic: str  # "lettre" | "cv" | "alternance" | "candidature"


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s[:80] or "advice"


async def _fetch_sitemap(client: httpx.AsyncClient) -> list[str]:
    r = await client.get(SITEMAP_URL, timeout=30)
    r.raise_for_status()
    try:
        raw = gzip.decompress(r.content).decode("utf-8")
    except OSError:
        raw = r.text
    urls = re.findall(r"<loc>([^<]+)</loc>", raw)
    return urls


def _filter_urls(urls: list[str]) -> list[str]:
    keep: list[str] = []
    seen: set[str] = set()
    for u in urls:
        if not u.startswith(FR_PREFIX):
            continue
        low = u.lower()
        if not any(k in low for k in INCLUDE_KEYS):
            continue
        if any(k in low for k in EXCLUDE_KEYS):
            continue
        if u in seen:
            continue
        seen.add(u)
        keep.append(u)
    return keep


def _topic(url: str) -> str:
    low = url.lower()
    if "alternance" in low:
        return "alternance"
    if "lettre" in low or "motivation" in low:
        return "lettre"
    if "cv" in low:
        return "cv"
    return "candidature"


def _extract_article(html: str, url: str) -> Advice | None:
    soup = BeautifulSoup(html, "lxml")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.split(" | ")[0].strip()
    main = soup.select_one("main")
    if not main:
        return None
    # virer nav, footer, scripts
    for tag in main.select("nav, footer, script, style, aside, [class*='Author'], [class*='Nav']"):
        tag.decompose()
    text = main.get_text("\n", strip=True)
    # Compression : squasher lignes vides
    lines = [l for l in (ln.strip() for ln in text.split("\n")) if l]
    text = "\n".join(lines)
    # Dégager l'en-tête méta (catégorie, date, auteur) : on commence après le "min" de temps de lecture
    m = re.search(r"(\d+\s*min)\b", text)
    if m:
        text = text[m.end():].strip()
    # Couper avant section recommandations/partage
    for cut in ("Partager cet article", "Les thématiques abordées", "Sur le même sujet", "Les articles les plus"):
        i = text.find(cut)
        if i != -1:
            text = text[:i].strip()
    if len(text) < 600:
        return None
    # Limiter la taille stockée (on a juste besoin des principes)
    text = text[:6000]
    return Advice(url=url, title=title, body=text, topic=_topic(url))


def _write(a: Advice) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slugify(a.title or a.url.rsplit("/", 1)[-1])
    path = DATA_DIR / f"{a.topic}-{slug}.md"
    path.write_text(
        f"---\nsource: wttj\nurl: {a.url}\ntitle: {a.title}\ntopic: {a.topic}\n---\n\n{a.body}\n",
        encoding="utf-8",
    )
    return path


async def scrape() -> list[Path]:
    written: list[Path] = []
    async with httpx.AsyncClient(headers={"User-Agent": UA, "Accept-Language": "fr-FR"}) as client:
        try:
            all_urls = await _fetch_sitemap(client)
        except Exception as e:
            logger.error("Sitemap fetch failed: %s", e)
            return []
        candidates = _filter_urls(all_urls)
        logger.info("Sitemap : %d URLs candidates après filtre", len(candidates))
        random.shuffle(candidates)
        # Garantir un mix entre les topics
        by_topic: dict[str, list[str]] = {"lettre": [], "cv": [], "alternance": [], "candidature": []}
        for u in candidates:
            by_topic[_topic(u)].append(u)
        # Interleave pour équilibrer
        queue: list[str] = []
        while any(by_topic.values()) and len(queue) < MAX_ARTICLES * 3:
            for t in ("lettre", "cv", "alternance", "candidature"):
                if by_topic[t]:
                    queue.append(by_topic[t].pop(0))

        for url in queue:
            if len(written) >= MAX_ARTICLES:
                break
            try:
                r = await client.get(url, follow_redirects=True, timeout=20)
                if r.status_code != 200:
                    continue
            except Exception as e:
                logger.debug("fetch err %s: %s", url, e)
                continue
            await asyncio.sleep(random.uniform(1.0, 2.2))
            art = _extract_article(r.text, url)
            if not art:
                continue
            p = _write(art)
            written.append(p)
            logger.info("[%d/%d] %s — %s", len(written), MAX_ARTICLES, art.topic, art.title[:70])
    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    written = asyncio.run(scrape())
    print(f"\nOK — {len(written)} articles écrits dans {DATA_DIR}")


if __name__ == "__main__":
    main()
