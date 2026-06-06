"""Auto-fit du CV pour remplir la page A4 sans déborder.

Le template CV expose deux variables CSS indépendantes :
  --sidebar-density (0.7 → compact, 2.0 → aéré)
  --main-density    (0.7 → compact, 2.0 → aéré)

On rend le HTML dans Playwright à la résolution A4 (794×1123 px à 96 dpi),
puis on fait une recherche binaire SÉPARÉE pour chaque colonne, ce qui évite
le bug "main rempli / sidebar vide en bas" quand le contenu est inégal.

Les densités sont ensuite injectées en inline `style="..."` sur le <body>.
"""
from __future__ import annotations

import logging
import re

from ..render_pdf import _get_browser, _lock

logger = logging.getLogger(__name__)

# A4 à 96 dpi
PAGE_H_PX = 1123
PAGE_W_PX = 794

MIN_DENSITY = 0.7
MAX_DENSITY = 2.0
TARGET_FILL_MIN = 1090      # ≤ 3% de vide en bas (~33px)
MAX_ITER = 9


async def fit_cv_html(html: str, base_density: float | None = None) -> str:
    """Trouve la meilleure densité par colonne et injecte les variables.

    Deux modes :
    - `base_density is None` (pipeline / CV généré) : auto-fit libre — on vise un
      remplissage ∈ [TARGET_FILL_MIN, PAGE_H_PX], densité de référence 1.0.
    - `base_density` fourni (densité choisie dans l'éditeur) : on l'ANCRE — on la
      garde telle quelle, et on ne compresse QUE si la colonne déborde la page.
      On n'écrase jamais le choix de l'utilisateur pour "remplir" du vide.
    """
    anchored = base_density is not None
    base = 1.0
    if anchored:
        try:
            base = max(MIN_DENSITY, min(MAX_DENSITY, float(base_density)))
        except (TypeError, ValueError):
            base, anchored = 1.0, False

    sidebar_d = base
    main_d = base
    try:
        async with _lock:
            browser = await _get_browser()
            ctx = await browser.new_context(viewport={"width": PAGE_W_PX, "height": PAGE_H_PX})
            page = await ctx.new_page()
            try:
                await page.set_content(html, wait_until="networkidle")

                async def measure(sd: float, md: float) -> tuple[int, int]:
                    res = await page.evaluate(
                        """([sd, md]) => {
                            document.body.style.setProperty('--sidebar-density', String(sd));
                            document.body.style.setProperty('--main-density', String(md));

                            // On désactive temporairement les stretchs (flex:1 sur .sections / .flow,
                            // height:297mm sur .page) pour obtenir la hauteur naturelle du contenu.
                            const sb = document.querySelector('.sidebar');
                            const mn = document.querySelector('.main');
                            const sec = document.querySelector('.sidebar > .sections');
                            const flow = document.querySelector('.main > .flow');
                            const page = document.querySelector('.page');

                            const saved = [];
                            function force(el, props) {
                                if (!el) return;
                                const prev = {};
                                for (const k in props) { prev[k] = el.style.getPropertyValue(k); el.style.setProperty(k, props[k], 'important'); }
                                saved.push([el, prev]);
                            }
                            force(page,  { 'height': 'auto', 'align-items': 'flex-start' });
                            force(sb,    { 'height': 'auto', 'align-self': 'flex-start' });
                            force(mn,    { 'height': 'auto', 'align-self': 'flex-start' });
                            force(sec,   { 'flex': 'none' });
                            force(flow,  { 'flex': 'none' });

                            void document.body.offsetHeight;  // reflow

                            const sbH = sb ? sb.scrollHeight : 0;
                            const mnH = mn ? mn.scrollHeight : 0;

                            // Restore
                            for (const [el, prev] of saved) {
                                for (const k in prev) {
                                    if (prev[k]) el.style.setProperty(k, prev[k]);
                                    else el.style.removeProperty(k);
                                }
                            }
                            return [sbH, mnH];
                        }""",
                        [sd, md],
                    )
                    return int(res[0]), int(res[1])

                # Premier essai : à la densité d'ancrage (base)
                sb, mn = await measure(base, base)
                logger.info("CV fit init (base=%.3f): sidebar=%d main=%d", base, sb, mn)

                # Indépendance par colonne : on cherche la meilleure densité pour chaque
                sidebar_d = await _fit_column(
                    measure_h=lambda d: _measure_sidebar(measure, d, main_d_fixed=base),
                    current_h=sb,
                    base=base,
                    anchored=anchored,
                )
                main_d = await _fit_column(
                    measure_h=lambda d: _measure_main(measure, d, sidebar_d_fixed=sidebar_d),
                    current_h=mn,
                    base=base,
                    anchored=anchored,
                )
                logger.info("CV fit final: sd=%.3f md=%.3f (anchored=%s)", sidebar_d, main_d, anchored)
            finally:
                await ctx.close()
    except Exception as e:
        logger.warning("CV auto-fit a échoué (%s) — densité d'ancrage %.3f", e, base)
        sidebar_d = base
        main_d = base

    return _inject_densities(html, sidebar_d, main_d)


# --- helpers : isole la mesure d'une seule colonne en fixant l'autre ---


async def _measure_sidebar(measure, sd: float, main_d_fixed: float) -> int:
    sb, _ = await measure(sd, main_d_fixed)
    return sb


async def _measure_main(measure, md: float, sidebar_d_fixed: float) -> int:
    _, mn = await measure(sidebar_d_fixed, md)
    return mn


async def _fit_column(measure_h, current_h: int, base: float = 1.0, anchored: bool = False) -> float:
    """Densité d'une colonne.

    - mode ancré (densité choisie par l'utilisateur) : on garde `base`, on ne
      compresse (entre MIN_DENSITY et base) QUE si la colonne déborde la page.
      On n'étire jamais pour combler du vide — l'aéré est un choix assumé.
    - mode libre (auto) : on vise [TARGET_FILL_MIN, PAGE_H_PX] autour de 1.0.
    """
    if anchored:
        if current_h > PAGE_H_PX:
            return await _binary_search(measure_h, MIN_DENSITY, base)
        return base

    # Cas A : déjà à pile la bonne hauteur
    if TARGET_FILL_MIN <= current_h <= PAGE_H_PX:
        return 1.0

    if current_h > PAGE_H_PX:
        # Overflow → compresser entre MIN_DENSITY et 1.0
        return await _binary_search(measure_h, MIN_DENSITY, 1.0)

    # current_h < TARGET_FILL_MIN → étirer entre 1.0 et MAX_DENSITY
    return await _binary_search(measure_h, 1.0, MAX_DENSITY)


async def _binary_search(measure_h, lo: float, hi: float) -> float:
    """Cherche la densité dans [lo, hi] qui place la hauteur dans [TARGET_FILL_MIN, PAGE_H_PX]."""
    best_safe: float | None = None
    # On préfère la plus haute densité qui ne déborde pas ; à hauteur ≥ TARGET on retourne tout de suite
    for _ in range(MAX_ITER):
        if hi - lo < 0.04:
            break
        mid = (lo + hi) / 2
        h = await measure_h(mid)
        if h > PAGE_H_PX:
            hi = mid
        else:
            best_safe = mid
            if h >= TARGET_FILL_MIN:
                return mid
            lo = mid
    return best_safe if best_safe is not None else MIN_DENSITY


BODY_OPEN_RE = re.compile(r"<body\b([^>]*)>", re.IGNORECASE)


def _inject_densities(html: str, sidebar_d: float, main_d: float) -> str:
    """Pose --sidebar-density et --main-density sur le <body>, écrase --density si présente."""
    def _fmt(v: float) -> str:
        s = f"{v:.3f}".rstrip("0").rstrip(".")
        return s or "0"

    style_decl = f"--sidebar-density:{_fmt(sidebar_d)};--main-density:{_fmt(main_d)}"

    def _sub(m: re.Match) -> str:
        attrs = m.group(1) or ""
        style_match = re.search(r'style="([^"]*)"', attrs, re.IGNORECASE)
        if style_match:
            existing = style_match.group(1)
            # Retire les anciennes densités si présentes
            cleaned = re.sub(r"--(sidebar-|main-)?density\s*:\s*[^;\"]+;?", "", existing).strip().strip(";")
            new_style = f"{cleaned};{style_decl}" if cleaned else style_decl
            attrs = re.sub(
                r'style="[^"]*"',
                f'style="{new_style}"',
                attrs,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            attrs = f'{attrs} style="{style_decl}"'
        return f"<body{attrs}>"

    new_html, n = BODY_OPEN_RE.subn(_sub, html, count=1)
    return new_html if n else html
