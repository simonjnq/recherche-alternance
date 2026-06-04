"""Orchestrateur 'Lancer la recherche' : scrape → dedup → score → generate → save."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from . import db as dbm
from .config import OFFERS_DIR, load_profile, all_keywords
from .contract_filter import is_alternance
from .relevance import is_relevant
from .llm.cv_adapter import adapt_cv
from .llm.cv_fit import fit_cv_html
from .llm.cv_profile import ensure_structured_profile, profile_to_text
from .llm.letter import generate_letter
from .llm.scoring import score_offer
from .models import GeneratedDocs, Offer, OfferRaw, SearchRunProgress, SourceProgress
from .scrapers.base import Scraper
from .text_clean import clean_description, clean_offer_title

import time as _time

logger = logging.getLogger(__name__)

ProgressCb = Callable[[SearchRunProgress], Awaitable[None]]


@dataclass
class PipelineState:
    running: bool = False
    last_progress: Optional[SearchRunProgress] = None
    subscribers: set[asyncio.Queue] = field(default_factory=set)

    async def emit(self, progress: SearchRunProgress) -> None:
        self.last_progress = progress
        for q in list(self.subscribers):
            try:
                q.put_nowait(progress)
            except asyncio.QueueFull:
                pass


STATE = PipelineState()


SENIOR_TITLE_RE = re.compile(
    r"\b(lead|senior|sr\.?|head\s+of|director|directeur|principal|staff|chief|cto|cdo|cpo|vp)\b",
    re.IGNORECASE,
)


def generation_block_reason(offer: Offer) -> str | None:
    """Retourne une raison de skipper la génération CV/lettre, ou None si OK.

    On évite de brûler des appels LLM sur des offres dégradées (description vide,
    contrat hors alternance, titres seniors qui ne correspondent pas à un alternant).
    """
    desc = (offer.description or "").strip()
    if len(desc) < 120:
        return "description trop courte (<120 caractères)"
    contract = (offer.contract or "").lower()
    if contract and not any(
        k in contract for k in ("altern", "apprent", "stage")
    ):
        return f"contrat non éligible ({offer.contract})"
    title = offer.title or ""
    if SENIOR_TITLE_RE.search(title) and "alternance" not in title.lower():
        return f"titre senior dans l'intitulé ({title[:60]})"
    return None


def _load_scrapers(profile: dict[str, Any]) -> list[Scraper]:
    """Import lazy pour éviter de charger Playwright si la source est désactivée."""
    enabled = profile.get("sources_enabled", {})
    scrapers: list[Scraper] = []
    if enabled.get("la_bonne_alternance"):
        from .scrapers.la_bonne_alternance import LaBonneAlternanceScraper
        scrapers.append(LaBonneAlternanceScraper())
    if enabled.get("indeed"):
        from .scrapers.indeed import IndeedScraper
        scrapers.append(IndeedScraper())
    if enabled.get("wttj"):
        from .scrapers.wttj import WTTJScraper
        scrapers.append(WTTJScraper())
    if enabled.get("hellowork"):
        from .scrapers.hellowork import HelloWorkScraper
        scrapers.append(HelloWorkScraper())
    if enabled.get("apec"):
        from .scrapers.apec import ApecScraper
        scrapers.append(ApecScraper())
    if enabled.get("linkedin"):
        from .scrapers.linkedin import LinkedInScraper
        scrapers.append(LinkedInScraper())
    return scrapers


async def run_search() -> None:
    """Entrypoint du bouton 'Lancer la recherche'."""
    if STATE.running:
        logger.warning("Search already running")
        return
    STATE.running = True
    try:
        await _run_search_inner()
    finally:
        STATE.running = False


async def _run_search_inner() -> None:
    profile = load_profile()
    keywords = all_keywords(profile)
    location = profile.get("location", "Paris")
    max_per = int(profile.get("max_offers_per_source", 30))
    threshold = int(profile.get("score_threshold_generate", 70))

    db = await dbm.connect()
    run_id = await _start_run(db)

    try:
        # --- 1. Scraping (TRUE parallel) ---
        scrapers = _load_scrapers(profile)
        per_source: dict[str, SourceProgress] = {
            s.source: SourceProgress(source=s.source, state="pending") for s in scrapers
        }
        start_times: dict[str, float] = {}

        async def emit_state(message: str | None = None) -> None:
            done_count = sum(1 for p in per_source.values() if p.state in ("done", "error", "skipped"))
            await STATE.emit(SearchRunProgress(
                stage="scraping",
                current=done_count,
                total=len(scrapers),
                message=message or f"Scraping en cours ({done_count}/{len(scrapers)} sources terminées)",
                per_source=list(per_source.values()),
            ))

        await emit_state("Démarrage du scraping en parallèle")

        async def scrape_one(scraper: Scraper) -> list[OfferRaw]:
            start_times[scraper.source] = _time.monotonic()
            per_source[scraper.source].state = "running"
            await emit_state()

            async def on_offer(offer: OfferRaw) -> None:
                p = per_source[scraper.source]
                p.count += 1
                p.last_title = offer.title[:80]
                await emit_state()

            try:
                offers = await scraper.safe_search(keywords, location, max_per, on_offer=on_offer)
                p = per_source[scraper.source]
                p.state = "done"
                p.count = len(offers)
                p.duration_s = round(_time.monotonic() - start_times[scraper.source], 2)
                await emit_state()
                return offers
            except Exception as e:
                logger.exception("Scraper %s crashed: %s", scraper.source, e)
                p = per_source[scraper.source]
                p.state = "error"
                p.error = str(e)[:200]
                p.duration_s = round(_time.monotonic() - start_times[scraper.source], 2)
                await emit_state()
                return []

        scrape_results = await asyncio.gather(
            *(scrape_one(s) for s in scrapers), return_exceptions=False
        )
        raw_offers: list[OfferRaw] = []
        for batch in scrape_results:
            raw_offers.extend(batch)
        logger.info("Scraping total: %d offers (sources: %s)", len(raw_offers),
                    {s: p.count for s, p in per_source.items()})
        await emit_state(f"Scraping terminé : {len(raw_offers)} offres brutes")

        # --- 2. Nettoyage + filtres (alternance + pertinence) + dedup + insert ---
        new_offer_ids: list[int] = []
        dropped_non_alt = 0
        dropped_irrelevant = 0
        for raw in raw_offers:
            raw.title = clean_offer_title(raw.title)
            raw.description = clean_description(raw.description, raw.source)
            # On écarte tôt (ni stocké, ni scoré, pas d'appel LLM) ce qui n'est pas
            # une alternance, puis ce qui est hors domaine ciblé.
            if not is_alternance(raw):
                dropped_non_alt += 1
                continue
            if not is_relevant(raw, keywords):
                dropped_irrelevant += 1
                continue
            oid = await dbm.upsert_offer_raw(db, raw, run_id)
            if oid is not None:
                new_offer_ids.append(oid)
        logger.info(
            "New offers: %d / %d scraped (%d non-alternance, %d hors-domaine écartées)",
            len(new_offer_ids), len(raw_offers), dropped_non_alt, dropped_irrelevant,
        )

        # --- 3. Scoring ---
        await STATE.emit(SearchRunProgress(
            stage="scoring", total=len(new_offer_ids), message="Analyse des offres",
        ))
        scored_offers: list[Offer] = []
        sem = asyncio.Semaphore(4)

        async def score_one(i: int, oid: int) -> None:
            async with sem:
                offer = await dbm.get_offer(db, oid)
                if not offer:
                    return
                scored = await score_offer(offer, profile)
                await dbm.set_offer_scoring(db, oid, scored)
                offer.skills = scored.skills
                offer.score = scored.score
                offer.reasoning = scored.reasoning
                offer.red_flags = scored.red_flags
                scored_offers.append(offer)
                await STATE.emit(SearchRunProgress(
                    stage="scoring", current=i, total=len(new_offer_ids),
                    message=f"{offer.title[:50]} → {scored.score}",
                    offer_id=oid,
                ))

        await asyncio.gather(*(score_one(i, oid) for i, oid in enumerate(new_offer_ids, 1)))

        # --- 4. Génération CV + lettre pour offres score >= threshold ---
        eligible = [o for o in scored_offers if o.score >= threshold]
        skipped: list[tuple[Offer, str]] = []
        top: list[Offer] = []
        for o in eligible:
            reason = generation_block_reason(o)
            if reason:
                skipped.append((o, reason))
                logger.info("Skip génération offer %s: %s", o.id, reason)
            else:
                top.append(o)
        top.sort(key=lambda o: o.score, reverse=True)
        default_cv = await dbm.get_default_cv(db)

        if not default_cv:
            logger.warning("Pas de CV par défaut, génération skippée")
            await STATE.emit(SearchRunProgress(
                stage="done", message=f"Terminé — pas de CV (upload d'abord). {len(scored_offers)} offres analysées.",
            ))
            await _finish_run(db, run_id, {"scraped": len(raw_offers), "new": len(new_offer_ids), "dropped_non_alt": dropped_non_alt, "dropped_irrelevant": dropped_irrelevant, "scored": len(scored_offers), "generated": 0})
            return

        # Profil structuré du CV — une seule extraction LLM par run, partagée.
        try:
            structured = await ensure_structured_profile(db, default_cv)
            structured_text = profile_to_text(structured) if structured else None
        except Exception as e:
            logger.warning("Profil structuré indisponible (%s) — fallback HTML brut", e)
            structured_text = None

        await STATE.emit(SearchRunProgress(
            stage="generating", total=len(top), message="Génération CV + lettres",
        ))
        gen_sem = asyncio.Semaphore(2)

        async def generate_one(i: int, offer: Offer) -> None:
            async with gen_sem:
                try:
                    cv_html = await adapt_cv(default_cv.html_content, offer, profile_text=structured_text)
                    cv_html = await fit_cv_html(cv_html)
                    letter_md = await generate_letter(
                        offer, default_cv.html_content, profile, profile_text=structured_text,
                    )
                    folder = OFFERS_DIR / offer.slug()
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / "offer.json").write_text(
                        json.dumps(offer.model_dump(mode="json"), indent=2, ensure_ascii=False, default=str)
                    )
                    cv_path = folder / "cv.html"
                    cv_path.write_text(cv_html)
                    letter_path = folder / "letter.md"
                    letter_path.write_text(letter_md)
                    await dbm.add_generated(db, GeneratedDocs(
                        offer_id=offer.id or 0, cv_id=default_cv.id or 0,
                        adapted_cv_path=str(cv_path), letter_path=str(letter_path),
                    ))
                    await STATE.emit(SearchRunProgress(
                        stage="generating", current=i, total=len(top),
                        message=f"Généré : {offer.title[:50]}", offer_id=offer.id,
                    ))
                except Exception as e:
                    logger.exception("Génération KO pour offer %s: %s", offer.id, e)

        await asyncio.gather(*(generate_one(i, o) for i, o in enumerate(top, 1)))

        skip_msg = f", {len(skipped)} skip" if skipped else ""
        filt = dropped_non_alt + dropped_irrelevant
        filt_msg = f", {filt} écartées (hors alternance/domaine)" if filt else ""
        await STATE.emit(SearchRunProgress(
            stage="done",
            message=f"Terminé — {len(scored_offers)} nouvelles offres, {len(top)} candidatures générées{skip_msg}{filt_msg}.",
        ))
        await _finish_run(db, run_id, {
            "scraped": len(raw_offers), "new": len(new_offer_ids),
            "dropped_non_alt": dropped_non_alt, "dropped_irrelevant": dropped_irrelevant,
            "scored": len(scored_offers), "generated": len(top),
            "skipped_generation": len(skipped),
        })
    except Exception as e:
        logger.exception("Pipeline error: %s", e)
        await STATE.emit(SearchRunProgress(stage="error", message=f"Erreur: {e}"))
        await _finish_run(db, run_id, {"error": str(e)})
    finally:
        await db.close()


async def _start_run(db) -> int:
    cur = await db.execute(
        "INSERT INTO search_runs (started_at, status) VALUES (?, ?)",
        (datetime.utcnow().isoformat(), "running"),
    )
    await db.commit()
    return cur.lastrowid or 0


async def _finish_run(db, run_id: int, stats: dict[str, Any]) -> None:
    await db.execute(
        "UPDATE search_runs SET finished_at=?, stats_json=?, status=? WHERE id=?",
        (datetime.utcnow().isoformat(), json.dumps(stats), "done", run_id),
    )
    await db.commit()


async def regenerate_for_offer(offer_id: int) -> Optional[Path]:
    """Regénère CV+lettre pour une offre déjà scorée (bouton 'Refaire'/'Générer')."""
    profile = load_profile()
    db = await dbm.connect()
    try:
        offer = await dbm.get_offer(db, offer_id)
        if not offer:
            return None
        cv = await dbm.get_default_cv(db)
        if not cv:
            raise RuntimeError("Pas de CV par défaut. Upload d'abord un CV.")
        try:
            structured = await ensure_structured_profile(db, cv)
            structured_text = profile_to_text(structured) if structured else None
        except Exception as e:
            logger.warning("Profil structuré indisponible (%s)", e)
            structured_text = None
        cv_html = await adapt_cv(cv.html_content, offer, profile_text=structured_text)
        cv_html = await fit_cv_html(cv_html)
        letter_md = await generate_letter(
            offer, cv.html_content, profile, profile_text=structured_text,
        )
        folder = OFFERS_DIR / offer.slug()
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "offer.json").write_text(
            json.dumps(offer.model_dump(mode="json"), indent=2, ensure_ascii=False, default=str)
        )
        (folder / "cv.html").write_text(cv_html)
        (folder / "letter.md").write_text(letter_md)
        await dbm.add_generated(db, GeneratedDocs(
            offer_id=offer.id or 0, cv_id=cv.id or 0,
            adapted_cv_path=str(folder / "cv.html"), letter_path=str(folder / "letter.md"),
        ))
        return folder
    finally:
        await db.close()
