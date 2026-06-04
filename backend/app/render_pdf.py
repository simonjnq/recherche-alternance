"""Rendu HTML → PDF via Playwright.

On réutilise le Chromium installé par start.sh. Une seule instance de navigateur
est partagée entre les appels pour éviter de redémarrer Chromium à chaque export.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from playwright.async_api import Browser, async_playwright

logger = logging.getLogger(__name__)

_browser: Optional[Browser] = None
_lock = asyncio.Lock()
_playwright_ctx = None


async def _get_browser() -> Browser:
    global _browser, _playwright_ctx
    if _browser is None or not _browser.is_connected():
        _playwright_ctx = await async_playwright().start()
        _browser = await _playwright_ctx.chromium.launch(headless=True)
    return _browser


async def html_to_pdf(html: str, *, format_: str = "A4", margin_mm: int = 12) -> bytes:
    """Convertit un document HTML complet en PDF."""
    async with _lock:
        browser = await _get_browser()
        ctx = await browser.new_context()
        page = await ctx.new_page()
        try:
            await page.set_content(html, wait_until="networkidle")
            margin = f"{margin_mm}mm"
            pdf = await page.pdf(
                format=format_,
                print_background=True,
                margin={"top": margin, "right": margin, "bottom": margin, "left": margin},
            )
            return pdf
        finally:
            await ctx.close()


async def shutdown() -> None:
    global _browser, _playwright_ctx
    if _browser is not None:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None
    if _playwright_ctx is not None:
        try:
            await _playwright_ctx.stop()
        except Exception:
            pass
        _playwright_ctx = None
