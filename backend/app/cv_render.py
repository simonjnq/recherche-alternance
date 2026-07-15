"""Rendu HTML d'un CV à partir d'un modèle structuré + style.

C'est le moteur du nouvel éditeur visuel : au lieu de faire produire le HTML
final par un LLM à chaque modif, on garde une donnée structurée et on génère le
HTML déterministement ici. Le LLM ne sert plus qu'à :
- adapter le contenu au moment de la 1ʳᵉ génération (cv_adapter)
- reformuler un champ ponctuel (ai-bullet)

Le HTML produit doit conserver EXACTEMENT la même structure que le template
historique (classes, structure des sections) pour que `fit_cv_html` continue à
fonctionner.
"""
from __future__ import annotations

import html as _html
from typing import Any

from .config import get_profile_photo_data_url


def _esc(s: str | None) -> str:
    return _html.escape((s or "").strip(), quote=True)


def _initials(name: str | None) -> str:
    name = (name or "").strip()
    if not name:
        return "—"
    parts = [p for p in name.split() if p]
    if not parts:
        return "—"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


DEFAULT_STYLE: dict[str, Any] = {
    "accent_color": "#2d52c4",
    "density": 1.0,
    "photo_enabled": True,
    "font": "Poppins",      # Poppins | Inter | Manrope
    "template": "modern_2col",  # modern_2col | minimal_1col | bold_header
}

FONT_LINK = {
    "Poppins": (
        "https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap"
    ),
    "Inter": (
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
    ),
    "Manrope": (
        "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap"
    ),
}


def _safe_color(s: str | None, fallback: str = "#2d52c4") -> str:
    if not s:
        return fallback
    s = s.strip()
    if not s.startswith("#") or len(s) not in (4, 7):
        return fallback
    if not all(c in "0123456789abcdefABCDEF" for c in s[1:]):
        return fallback
    return s


def _lighten_hex(hex_color: str, factor: float = 0.92) -> str:
    """Renvoie une teinte très claire (fond sidebar) dérivée de l'accent."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return "#f4f6fc"
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def _build_style_block(style: dict[str, Any]) -> tuple[str, dict[str, str]]:
    accent = _safe_color(style.get("accent_color"), "#2d52c4")
    sidebar_bg = _lighten_hex(accent, 0.92)
    sidebar_border = _lighten_hex(accent, 0.78)
    chip_bg = _lighten_hex(accent, 0.86)
    project_bg = _lighten_hex(accent, 0.88)
    project_border = _lighten_hex(accent, 0.75)
    card_bg = _lighten_hex(accent, 0.94)
    density = float(style.get("density") or 1.0)
    density = max(0.7, min(1.5, density))
    font = style.get("font") or "Poppins"
    if font not in FONT_LINK:
        font = "Poppins"

    inline_root = (
        f"--accent:{accent};--sidebar-bg:{sidebar_bg};--sidebar-border:{sidebar_border};"
        f"--chip-bg:{chip_bg};--project-bg:{project_bg};--project-border:{project_border};"
        f"--card-bg:{card_bg};--density:{density:.3f};--font:'{font}'"
    )
    return inline_root, {
        "accent": accent,
        "sidebar_bg": sidebar_bg,
        "card_bg": card_bg,
        "chip_bg": chip_bg,
        "project_bg": project_bg,
        "project_border": project_border,
        "sidebar_border": sidebar_border,
        "font": font,
    }


STYLES_CSS = """
@page { size: A4; margin: 0; }
html, body { margin: 0; padding: 0; background: #fff; }
body {
  font-family: var(--font, 'Poppins'), -apple-system, 'Segoe UI', sans-serif;
  color: #14141f;
  font-size: 9pt;
  line-height: 1.5;
  width: 210mm;
  height: 297mm;
  overflow: hidden;
  /* Deux densités INDÉPENDANTES : sidebar et main remplissent chacune leur
     colonne (cv_fit.py fait un binary-search par colonne). Si --sidebar-density
     ou --main-density n'est pas défini, on retombe sur --density (legacy). */
  --sd: var(--sidebar-density, var(--density));
  --md: var(--main-density, var(--density));
  /* Main */
  --bullet-lh: calc(1.4 + (var(--md) - 1) * 0.55);
  --bullet-gap: calc(2px + (var(--md) - 1) * 11px);
  --exp-gap: calc(10px + (var(--md) - 1) * 22px);
  --proj-gap: calc(8px + (var(--md) - 1) * 16px);
  --intro-lh: calc(1.55 + (var(--md) - 1) * 0.5);
  --main-pad-y: calc(28px + (var(--md) - 1) * 30px);
  --section-gap: calc(14px + (var(--md) - 1) * 24px);
  /* Sidebar */
  --sidebar-pad-y: calc(28px + (var(--sd) - 1) * 30px);
  --sidebar-gap: calc(13px + (var(--sd) - 1) * 22px);
  --text-muted: #6b7280;
  --text-soft: #4a4a55;
  --rule: #e5e7eb;
}
.page { display: flex; width: 210mm; height: 297mm; }

/* ---------- Sidebar ---------- */
.sidebar {
  width: 68mm;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--sidebar-border);
  padding: var(--sidebar-pad-y) 16px var(--sidebar-pad-y);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: var(--sidebar-gap);
  min-width: 0;
  overflow: hidden;
}
.sidebar > .head { display: flex; flex-direction: column; gap: 8px; }
.sidebar > .sections { display: flex; flex-direction: column; flex: 1; gap: var(--sidebar-gap); }
.sidebar .photo {
  width: 92px; height: 92px;
  border-radius: 50%;
  border: 2.5px solid var(--accent);
  background: var(--chip-bg) center/cover no-repeat;
  margin: 0 auto;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 26pt; color: var(--accent);
}
.sidebar h1 {
  font-size: 12.5pt; font-weight: 700; margin: 0; text-align: center; color: #14141f;
  letter-spacing: -0.01em;
}
.sidebar .role {
  font-size: 9pt; text-align: center; color: var(--accent); font-weight: 600;
  margin-top: 2px; line-height: 1.3;
}
.sidebar h2 {
  font-size: 7.5pt; text-transform: uppercase; letter-spacing: 0.9px;
  font-weight: 700; color: var(--accent);
  margin: 0 0 7px; padding-bottom: 4px;
  border-bottom: 1px solid var(--sidebar-border);
}
.sidebar section { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.contact { font-size: 8.5pt; color: var(--text-soft); }
.contact div { margin-bottom: 2px; word-break: break-word; line-height: 1.4; }
.formation .degree { font-size: 8.5pt; font-weight: 600; color: #14141f; line-height: 1.35; }
.formation .school { font-size: 8pt; color: var(--text-muted); }
.formation .date { font-size: 7.8pt; font-style: italic; color: var(--text-muted); margin-top: 2px; }
.formation + .formation { margin-top: 6px; }

/* ---------- Tags : un par ligne dès qu'ils ne tiennent pas ---------- */
.tag-rows {
  display: flex; flex-wrap: wrap; gap: 4px;
  min-width: 0;
}
.tag {
  background: var(--chip-bg); color: var(--accent);
  font-size: 7.8pt; font-weight: 500;
  padding: 3px 7px; border-radius: 4px;
  line-height: 1.3;
  max-width: 100%;
  box-sizing: border-box;
  /* PAS de white-space: nowrap → un long skill wrap proprement */
  word-break: break-word;
  hyphens: auto;
}

.soft-list, .lang-list, .stack-list {
  list-style: none; margin: 0; padding: 0;
  display: flex; flex-direction: column; gap: 3px;
  font-size: 8.5pt; color: var(--text-soft);
  line-height: 1.4;
}
.lang-list li .lvl { color: var(--text-muted); font-style: italic; }
.stack-list li { line-height: 1.4; }

/* ---------- Main ---------- */
.main {
  flex: 1;
  padding: var(--main-pad-y) 22px var(--main-pad-y) 24px;
  box-sizing: border-box;
  display: flex; flex-direction: column;
  gap: var(--section-gap);
  min-width: 0;
}
.main > .top { display: flex; flex-direction: column; gap: var(--section-gap); }
.main > .flow { display: flex; flex-direction: column; flex: 1; gap: var(--section-gap); }
.main > .flow > section { display: flex; flex-direction: column; }
.intro {
  font-size: 9pt; font-style: italic; color: var(--text-soft);
  line-height: var(--intro-lh);
  border-left: 2.5px solid var(--accent);
  padding: 1px 0 1px 11px;
  margin: 0;
}
.main h2 {
  font-size: 11.5pt; font-weight: 700; margin: 0 0 7px;
  color: #14141f;
  letter-spacing: -0.01em;
}
.main h2 .accent { color: var(--accent); font-weight: 700; }

/* Expériences — épuré : juste une fine border-left, pas de fond */
.exp-card {
  border-left: 2.5px solid var(--accent);
  padding: 0 0 0 13px;
  background: transparent;
}
.exp-card + .exp-card { margin-top: var(--exp-gap); }
.exp-head {
  display: flex; align-items: baseline; justify-content: space-between; gap: 10px;
  margin-bottom: 1px;
}
.exp-head .company {
  color: var(--accent); font-size: 9.5pt; font-weight: 700;
  letter-spacing: -0.005em;
}
.exp-head .date {
  font-size: 7.8pt; font-style: italic; color: var(--text-muted);
  white-space: nowrap; flex-shrink: 0;
}
.exp-role { font-size: 9pt; font-weight: 600; color: #14141f; margin-bottom: 4px; }
.exp-bullets { list-style: none; margin: 0; padding: 0; }
.exp-bullets li {
  position: relative; padding-left: 11px;
  font-size: 8.5pt; color: var(--text-soft);
  line-height: var(--bullet-lh); margin-bottom: var(--bullet-gap);
}
.exp-bullets li::before {
  content: ''; position: absolute; left: 0; top: 7px;
  width: 4px; height: 4px; border-radius: 50%; background: var(--accent);
}

/* Projets — minimaliste : titre + ligne, séparateur fin entre items */
.projects-card {
  background: transparent;
  border: none;
  padding: 0;
}
.projects-card + .projects-card {
  margin-top: var(--proj-gap);
  padding-top: var(--proj-gap);
  border-top: 1px solid var(--rule);
}
.projects-card .proj-title { font-size: 9pt; font-weight: 600; color: #14141f; margin-bottom: 2px; }
.projects-card .proj-line { font-size: 8.5pt; color: var(--text-soft); line-height: 1.45; }
""".strip()


def _chunked(lst: list[str], n: int) -> list[list[str]]:
    return [lst[i : i + n] for i in range(0, len(lst), n)]


# Caps de RENDU (l'éditeur garde tout, mais ce qui s'affiche / s'imprime
# est borné pour préserver la lisibilité A4). L'utilisateur peut réordonner
# dans l'éditeur pour promouvoir les items importants au-dessus de la coupe.
RENDER_LIMITS = {
    "hard_skills": 99,   # pas de limite d'affichage des compétences
    "soft_skills": 99,
    "tools": 99,
    "languages": 4,
    "experiences": 4,
    "bullets_per_exp": 6,
    "projects_pedagogical": 2,
    "projects_personal": 2,
    "summary_chars": 600,
}


def _shorten_skill(s: str) -> str:
    """Si un skill est trop long pour un tag (>26 chars), on le compacte un peu.

    Ne tronque PAS le sens : remplace " / " par "/", "et" par "&", etc. — affichage propre.
    Au-delà de 32 chars on coupe en deux et on laisse le wrap CSS faire son boulot.
    """
    s = (s or "").strip()
    if len(s) <= 26:
        return s
    # Compactage léger
    s = s.replace(" / ", "/").replace(" & ", "&")
    return s


def _render_modern_2col(structured: dict[str, Any], s: dict[str, Any]) -> str:
    """Template historique : sidebar bleue 68mm + main avec cards expé/projets."""
    inline_root, _palette = _build_style_block(s)
    font = s.get("font") or "Poppins"
    font_link = FONT_LINK.get(font, FONT_LINK["Poppins"])

    name = _esc(structured.get("name"))
    role = _esc(structured.get("role"))
    contact = structured.get("contact") or {}
    intro = _esc(structured.get("intro"))

    photo_data_url = get_profile_photo_data_url() if s.get("photo_enabled") else None
    if photo_data_url:
        photo_html = (
            f'<div class="photo" style="background-image:url(\'{photo_data_url}\');'
            f'background-size:cover;background-position:center;color:transparent;"></div>'
        )
    else:
        photo_html = f'<div class="photo">{_esc(structured.get("photo_initials") or _initials(structured.get("name")))}</div>'

    # ---- Sidebar sections ----
    sidebar_sections: list[str] = []

    contact_bits = []
    if contact.get("email"):
        contact_bits.append(f"<div>{_esc(contact.get('email'))}</div>")
    if contact.get("phone"):
        contact_bits.append(f"<div>{_esc(contact.get('phone'))}</div>")
    if contact.get("linkedin"):
        contact_bits.append(f"<div>{_esc(contact.get('linkedin'))}</div>")
    if contact.get("location"):
        contact_bits.append(f"<div>{_esc(contact.get('location'))}</div>")
    if contact_bits:
        sidebar_sections.append(
            '<section data-path="contact"><h2>Contact</h2>'
            f'<div class="contact">{"".join(contact_bits)}</div></section>'
        )

    formations = structured.get("formations") or []
    if formations:
        items = []
        for i, f in enumerate(formations):
            items.append(
                f'<div class="formation" data-path="formations.{i}">'
                f'<div class="degree">{_esc(f.get("degree"))}</div>'
                f'<div class="school">{_esc(f.get("school"))}</div>'
                f'<div class="date">{_esc(f.get("period"))}</div></div>'
            )
        sidebar_sections.append(
            '<section data-path="formations"><h2>Formation</h2>' + "".join(items) + "</section>"
        )

    hard = structured.get("hard_skills") or []
    if hard:
        tags_html = "".join(
            f'<span class="tag" data-path="hard_skills.{i}">{_esc(_shorten_skill(skill))}</span>'
            for i, skill in enumerate(hard[:RENDER_LIMITS["hard_skills"]])
        )
        sidebar_sections.append(
            '<section data-path="hard_skills"><h2>Hard Skills</h2>'
            f'<div class="tag-rows">{tags_html}</div></section>'
        )

    soft = structured.get("soft_skills") or []
    if soft:
        lis = "".join(
            f'<li data-path="soft_skills.{i}">{_esc(x)}</li>'
            for i, x in enumerate(soft[: RENDER_LIMITS["soft_skills"]])
        )
        sidebar_sections.append(
            '<section data-path="soft_skills"><h2>Soft Skills</h2>'
            f'<ul class="soft-list">{lis}</ul></section>'
        )

    tools = structured.get("tools") or []
    if tools:
        joined = ", ".join(_esc(t) for t in tools[: RENDER_LIMITS["tools"]])
        sidebar_sections.append(
            '<section data-path="tools"><h2>Stack &amp; Outils</h2>'
            f'<ul class="stack-list"><li>{joined}</li></ul></section>'
        )

    languages = structured.get("languages") or []
    if languages:
        lis = []
        for i, lg in enumerate(languages[: RENDER_LIMITS["languages"]]):
            name_l = _esc(lg.get("name"))
            level = _esc(lg.get("level"))
            lvl_html = f' <span class="lvl">— {level}</span>' if level else ""
            lis.append(f'<li data-path="languages.{i}">{name_l}{lvl_html}</li>')
        sidebar_sections.append(
            '<section data-path="languages"><h2>Langues</h2>'
            f'<ul class="lang-list">{"".join(lis)}</ul></section>'
        )

    sidebar_html = (
        '<aside class="sidebar" data-path="sidebar">'
        '<div class="head">'
        + photo_html
        + '<div>'
        + f'<h1 data-path="name">{name or "Prénom Nom"}</h1>'
        + (f'<div class="role" data-path="role">{role}</div>' if role else "")
        + '</div></div>'
        + '<div class="sections">'
        + "".join(sidebar_sections)
        + '</div></aside>'
    )

    # ---- Main ----
    main_sections: list[str] = []
    if intro:
        main_sections.append(f'<p class="intro" data-path="intro">{intro}</p>')

    experiences = structured.get("experiences") or []
    if experiences:
        cards = []
        for i, e in enumerate(experiences[: RENDER_LIMITS["experiences"]]):
            bullets = (e.get("bullets") or [])[: RENDER_LIMITS["bullets_per_exp"]]
            bullets_html = "".join(
                f'<li data-path="experiences.{i}.bullets.{j}">{_esc(b)}</li>'
                for j, b in enumerate(bullets)
            )
            cards.append(
                f'<div class="exp-card" data-path="experiences.{i}">'
                '<div class="exp-head">'
                f'<span class="company" data-path="experiences.{i}.company">{_esc(e.get("company"))}</span>'
                f'<span class="date" data-path="experiences.{i}.period">{_esc(e.get("period"))}</span>'
                '</div>'
                f'<div class="exp-role" data-path="experiences.{i}.role">{_esc(e.get("role"))}</div>'
                f'<ul class="exp-bullets">{bullets_html}</ul>'
                '</div>'
            )
        main_sections.append(
            '<section data-path="experiences"><h2>Expériences <span class="accent">professionnelles</span></h2>'
            + "".join(cards) + "</section>"
        )

    projects_p = structured.get("projects_pedagogical") or []
    if projects_p:
        cards = []
        for i, p in enumerate(projects_p[: RENDER_LIMITS["projects_pedagogical"]]):
            cards.append(
                f'<div class="projects-card" data-path="projects_pedagogical.{i}">'
                f'<div class="proj-title" data-path="projects_pedagogical.{i}.name">{_esc(p.get("name"))}</div>'
                f'<div class="proj-line" data-path="projects_pedagogical.{i}.summary">{_esc(p.get("summary"))}</div>'
                '</div>'
            )
        main_sections.append(
            '<section data-path="projects_pedagogical"><h2>Projets <span class="accent">pédagogiques</span></h2>'
            + "".join(cards) + "</section>"
        )

    projects_perso = structured.get("projects_personal") or []
    if projects_perso:
        cards = []
        for i, p in enumerate(projects_perso[: RENDER_LIMITS["projects_personal"]]):
            cards.append(
                f'<div class="projects-card" data-path="projects_personal.{i}">'
                f'<div class="proj-title" data-path="projects_personal.{i}.name">{_esc(p.get("name"))}</div>'
                f'<div class="proj-line" data-path="projects_personal.{i}.summary">{_esc(p.get("summary"))}</div>'
                '</div>'
            )
        main_sections.append(
            '<section data-path="projects_personal"><h2>Projets <span class="accent">personnels</span></h2>'
            + "".join(cards) + "</section>"
        )

    main_html = (
        '<main class="main" data-path="main">'
        '<div class="top">'
        + (main_sections[0] if main_sections and 'class="intro"' in main_sections[0] else "")
        + '</div>'
        '<div class="flow">'
        + "".join(s for s in main_sections if 'class="intro"' not in s)
        + '</div>'
        '</main>'
    )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>CV</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{font_link}" rel="stylesheet">
<style>{STYLES_CSS}
{EDITOR_OVERLAY_CSS}
</style>
</head>
<body style="{inline_root}">
<div class="page">{sidebar_html}{main_html}</div>
<script>{EDITOR_BRIDGE_JS}</script>
</body>
</html>"""


# Overlay visuel (hover/sélection/édition inline). Actif uniquement quand body
# porte la classe `editor-on`. Pour le PDF, sans cette classe rien ne s'affiche.
EDITOR_OVERLAY_CSS = """
body.editor-on [data-path] { cursor: pointer; transition: outline-color .12s ease, background-color .12s ease; outline: 1px dashed transparent; outline-offset: 2px; }
body.editor-on [data-path]:hover { outline-color: rgba(0,0,0,.18); }
body.editor-on [data-path].editor-selected { outline: 2px solid var(--accent); outline-offset: 2px; background: color-mix(in srgb, var(--accent) 6%, transparent); }
body.editor-on [data-path][contenteditable="true"] { outline: 2px solid var(--accent); background: #fff; cursor: text; box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 18%, transparent); }
body.editor-on [data-path][contenteditable="true"]:focus { outline: 2px solid var(--accent); }
""".strip()

# Pont avec le parent (React) — messages sortants :
#   {type:'cv-ready'}                                  bridge prêt
#   {type:'cv-select', path, rect}                     clic simple sur un bloc
#   {type:'cv-edit-start', path}                       double-clic → entrée en édition
#   {type:'cv-edit-commit', path, value}               Enter / blur → texte modifié
#   {type:'cv-edit-cancel', path}                      Escape pendant l'édition
# Messages entrants :
#   {type:'cv-editor-mode', on}                        active/désactive l'overlay
#   {type:'cv-select', path}                           surligne depuis l'extérieur
#   {type:'cv-focus-edit', path}                       met le bloc en édition
EDITOR_BRIDGE_JS = """
(function(){
  var EDITOR = false;
  var editing = null;          // élément actuellement contenteditable
  var editingPath = null;
  var editingOriginal = '';

  function findPathTarget(el){
    while (el && el !== document.body && !el.getAttribute('data-path')) el = el.parentElement;
    return (el && el !== document.body) ? el : null;
  }
  function clearSelection(){
    document.querySelectorAll('.editor-selected').forEach(function(el){el.classList.remove('editor-selected');});
  }
  function applySelection(path){
    clearSelection();
    if (!path) return;
    var el = document.querySelector('[data-path="'+CSS.escape(path)+'"]');
    if (el) {
      el.classList.add('editor-selected');
      emitSelect(path, el);
    }
  }
  function emitSelect(path, el){
    var r = el.getBoundingClientRect();
    parent.postMessage({type:'cv-select', path: path, rect: {top:r.top, left:r.left, width:r.width, height:r.height}}, '*');
  }
  function isEditablePath(path){
    // Conteneurs structuraux : pas en édition inline (on les sélectionne, c'est tout)
    if (!path) return false;
    var leafLike = /\\.bullets\\.\\d+$|\\.company$|\\.role$|\\.period$|\\.name$|\\.summary$|\\.degree$|\\.school$|\\.location$|^name$|^role$|^intro$|^hard_skills\\.\\d+$|^soft_skills\\.\\d+$|^tools\\.\\d+$/;
    return leafLike.test(path);
  }
  function commitEdit(){
    if (!editing) return;
    var path = editingPath;
    var value = (editing.innerText || '').replace(/\\s+/g,' ').trim();
    editing.removeAttribute('contenteditable');
    editing.removeEventListener('keydown', onEditKey);
    editing = null; editingPath = null;
    parent.postMessage({type:'cv-edit-commit', path: path, value: value}, '*');
  }
  function cancelEdit(){
    if (!editing) return;
    editing.innerText = editingOriginal;
    editing.removeAttribute('contenteditable');
    editing.removeEventListener('keydown', onEditKey);
    parent.postMessage({type:'cv-edit-cancel', path: editingPath}, '*');
    editing = null; editingPath = null;
  }
  function onEditKey(e){
    if (e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); commitEdit(); return; }
    if (e.key === 'Escape'){ e.preventDefault(); cancelEdit(); return; }
  }
  function startEdit(el, path){
    if (editing && editing !== el) commitEdit();
    if (!isEditablePath(path)) return;
    editingPath = path;
    editing = el;
    editingOriginal = el.innerText;
    el.setAttribute('contenteditable', 'true');
    el.spellcheck = false;
    el.addEventListener('keydown', onEditKey);
    el.focus();
    // Sélectionner tout le texte
    var range = document.createRange();
    range.selectNodeContents(el);
    var sel = window.getSelection();
    sel.removeAllRanges(); sel.addRange(range);
    parent.postMessage({type:'cv-edit-start', path: path}, '*');
  }

  document.addEventListener('click', function(e){
    if (!EDITOR) return;
    if (editing && editing.contains(e.target)) return;  // clic à l'intérieur d'un champ en édition
    var t = findPathTarget(e.target);
    if (!t) return;
    e.preventDefault();
    e.stopPropagation();
    var path = t.getAttribute('data-path');
    if (editing) commitEdit();
    applySelection(path);
  }, true);

  document.addEventListener('dblclick', function(e){
    if (!EDITOR) return;
    var t = findPathTarget(e.target);
    if (!t) return;
    e.preventDefault();
    e.stopPropagation();
    var path = t.getAttribute('data-path');
    startEdit(t, path);
  }, true);

  // Blur → commit
  document.addEventListener('focusout', function(e){
    if (editing && e.target === editing){
      // léger délai pour permettre escape/enter de gérer leurs cas
      setTimeout(function(){ if (editing === e.target) commitEdit(); }, 50);
    }
  }, true);

  window.addEventListener('message', function(ev){
    var d = ev.data || {};
    if (d.type === 'cv-editor-mode'){
      EDITOR = !!d.on;
      document.body.classList.toggle('editor-on', EDITOR);
      if (!EDITOR){ if (editing) cancelEdit(); clearSelection(); }
    } else if (d.type === 'cv-select'){
      applySelection(d.path);
    } else if (d.type === 'cv-focus-edit'){
      var el = document.querySelector('[data-path="'+CSS.escape(d.path)+'"]');
      if (el) startEdit(el, d.path);
    }
  });

  // Resize → ré-émet la bbox de la sélection
  window.addEventListener('resize', function(){
    var el = document.querySelector('.editor-selected');
    if (el) emitSelect(el.getAttribute('data-path'), el);
  });

  parent.postMessage({type:'cv-ready'}, '*');
})();
""".strip()


# ============================================================================
# Template minimal_1col — single column, sérif, beaucoup de blanc
# ============================================================================

MINIMAL_1COL_CSS = """
@page { size: A4; margin: 0; }
html, body { margin: 0; padding: 0; background: #fff; }
body {
  font-family: var(--font, 'Poppins'), -apple-system, 'Segoe UI', sans-serif;
  color: #1a1a1f;
  font-size: 9.5pt;
  line-height: 1.55;
  width: 210mm;
  height: 297mm;
  overflow: hidden;
  --md: var(--main-density, var(--density, 1));
  --pad-x: calc(20mm);
  --pad-y: calc(16mm + (var(--md) - 1) * 8mm);
  --section-gap: calc(16px + (var(--md) - 1) * 14px);
  --bullet-gap: calc(3px + (var(--md) - 1) * 7px);
  --bullet-lh: calc(1.45 + (var(--md) - 1) * 0.35);
  --exp-gap: calc(11px + (var(--md) - 1) * 14px);
  --proj-gap: calc(9px + (var(--md) - 1) * 11px);
  --muted: #6b7280;
  --soft: #4a4a55;
  --rule: #e5e7eb;
}
.page {
  width: 210mm; height: 297mm; box-sizing: border-box;
  padding: var(--pad-y) var(--pad-x);
  display: flex; flex-direction: column; gap: var(--section-gap);
}
.head {
  display: flex; align-items: center; gap: 18px;
  padding-bottom: 14px; border-bottom: 1px solid var(--rule);
}
.photo {
  width: 74px; height: 74px; border-radius: 50%;
  border: 2px solid var(--accent);
  background: #f4f6fc center/cover no-repeat;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 20pt; color: var(--accent);
  flex-shrink: 0;
}
.identity { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.identity h1 {
  margin: 0; font-size: 17pt; font-weight: 700; letter-spacing: -0.015em;
}
.identity .role {
  font-size: 10pt; font-weight: 500; color: var(--accent);
  margin-top: 1px;
}
.identity .contact {
  margin-top: 4px; font-size: 8.5pt; color: var(--muted);
  display: flex; flex-wrap: wrap; gap: 4px 14px;
}
.identity .contact span:not(:last-child)::after {
  content: ''; display: inline-block; width: 3px; height: 3px;
  border-radius: 50%; background: var(--muted); margin-left: 14px;
  vertical-align: middle;
}
.intro {
  font-size: 9.5pt; font-style: italic; color: var(--soft);
  line-height: 1.5;
  margin: 0;
}
section { display: flex; flex-direction: column; }
section h2 {
  font-size: 9pt; font-weight: 700; margin: 0 0 10px;
  text-transform: uppercase; letter-spacing: 1.5px;
  color: var(--accent);
}
.exp-card { padding: 0; background: transparent; }
.exp-card + .exp-card { margin-top: var(--exp-gap); }
.exp-head {
  display: flex; justify-content: space-between; align-items: baseline; gap: 12px;
  margin-bottom: 2px;
}
.exp-head .company { font-size: 10pt; font-weight: 600; color: #1a1a1f; }
.exp-head .date { font-size: 8.5pt; font-style: italic; color: var(--muted); white-space: nowrap; }
.exp-role { font-size: 9pt; font-weight: 500; color: var(--accent); margin-bottom: 5px; }
.exp-bullets { list-style: none; margin: 0; padding: 0; }
.exp-bullets li {
  position: relative; padding-left: 14px;
  font-size: 8.8pt; color: var(--soft);
  line-height: var(--bullet-lh); margin-bottom: var(--bullet-gap);
}
.exp-bullets li::before {
  content: '—'; position: absolute; left: 0; top: 0; color: var(--accent);
}
.projects-card {
  background: transparent; border: none; padding: 0;
}
.projects-card + .projects-card {
  margin-top: var(--proj-gap);
  padding-top: var(--proj-gap);
  border-top: 1px solid var(--rule);
}
.projects-card .proj-title { font-size: 9.5pt; font-weight: 600; color: #1a1a1f; margin-bottom: 2px; }
.projects-card .proj-line { font-size: 8.8pt; color: var(--soft); line-height: 1.5; }
.formation { font-size: 9pt; }
.formation + .formation { margin-top: 6px; }
.formation .degree { font-weight: 600; }
.formation .school { color: var(--muted); }
.formation .date { color: var(--muted); font-style: italic; font-size: 8.3pt; }
.bottom-grid {
  display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px;
  padding-top: 8px; border-top: 1px solid var(--rule);
}
.skills-inline {
  font-size: 8.8pt; color: var(--soft); line-height: 1.55;
}
.lang-inline { font-size: 8.8pt; color: var(--soft); line-height: 1.7; }
.lang-inline .lvl { color: var(--muted); font-style: italic; }
""".strip()


def _render_minimal_1col(structured: dict[str, Any], s: dict[str, Any]) -> str:
    inline_root, _palette = _build_style_block(s)
    font_link = FONT_LINK.get(s.get("font") or "Poppins", FONT_LINK["Poppins"])

    name = _esc(structured.get("name")) or "Prénom Nom"
    role = _esc(structured.get("role"))
    contact = structured.get("contact") or {}
    intro = _esc(structured.get("intro"))

    photo_data_url = get_profile_photo_data_url() if s.get("photo_enabled") else None
    if photo_data_url:
        photo_html = (
            f'<div class="photo" style="background-image:url(\'{photo_data_url}\');'
            f'background-size:cover;background-position:center;color:transparent;"></div>'
        )
    else:
        photo_html = f'<div class="photo">{_initials(structured.get("name"))}</div>'

    contact_spans = []
    for key in ("email", "phone", "location", "linkedin"):
        v = _esc(contact.get(key))
        if v:
            contact_spans.append(f'<span>{v}</span>')
    contact_html = ('<div class="contact">' + "".join(contact_spans) + '</div>') if contact_spans else ""

    head_html = (
        '<div class="head">'
        + photo_html
        + '<div class="identity">'
        + f'<h1 data-path="name">{name}</h1>'
        + (f'<div class="role" data-path="role">{role}</div>' if role else "")
        + contact_html
        + '</div></div>'
    )

    body_parts: list[str] = []
    if intro:
        body_parts.append(f'<p class="intro" data-path="intro">{intro}</p>')

    experiences = structured.get("experiences") or []
    if experiences:
        cards = []
        for i, e in enumerate(experiences[: RENDER_LIMITS["experiences"]]):
            bullets = (e.get("bullets") or [])[: RENDER_LIMITS["bullets_per_exp"]]
            bullets_html = "".join(
                f'<li data-path="experiences.{i}.bullets.{j}">{_esc(b)}</li>'
                for j, b in enumerate(bullets)
            )
            cards.append(
                f'<div class="exp-card" data-path="experiences.{i}">'
                '<div class="exp-head">'
                f'<span class="company" data-path="experiences.{i}.company">{_esc(e.get("company"))}</span>'
                f'<span class="date" data-path="experiences.{i}.period">{_esc(e.get("period"))}</span>'
                '</div>'
                f'<div class="exp-role" data-path="experiences.{i}.role">{_esc(e.get("role"))}</div>'
                f'<ul class="exp-bullets">{bullets_html}</ul>'
                '</div>'
            )
        body_parts.append(
            '<section data-path="experiences"><h2>Expérience</h2>' + "".join(cards) + "</section>"
        )

    projects_p = structured.get("projects_pedagogical") or []
    projects_perso = structured.get("projects_personal") or []
    all_projects = []
    for i, p in enumerate(projects_p[: RENDER_LIMITS["projects_pedagogical"]]):
        all_projects.append(
            f'<div class="projects-card" data-path="projects_pedagogical.{i}">'
            f'<div class="proj-title" data-path="projects_pedagogical.{i}.name">{_esc(p.get("name"))}</div>'
            f'<div class="proj-line" data-path="projects_pedagogical.{i}.summary">{_esc(p.get("summary"))}</div>'
            '</div>'
        )
    for i, p in enumerate(projects_perso[: RENDER_LIMITS["projects_personal"]]):
        all_projects.append(
            f'<div class="projects-card" data-path="projects_personal.{i}">'
            f'<div class="proj-title" data-path="projects_personal.{i}.name">{_esc(p.get("name"))}</div>'
            f'<div class="proj-line" data-path="projects_personal.{i}.summary">{_esc(p.get("summary"))}</div>'
            '</div>'
        )
    if all_projects:
        body_parts.append(
            '<section><h2>Projets</h2>' + "".join(all_projects) + "</section>"
        )

    # Bottom grid : Skills (hard + tools mergés) / Langues / Formation
    hard = structured.get("hard_skills") or []
    tools = structured.get("tools") or []
    skills_combined = list(dict.fromkeys(hard[: RENDER_LIMITS["hard_skills"]] + tools[: RENDER_LIMITS["tools"]]))
    skills_inline = " · ".join(_esc(_shorten_skill(x)) for x in skills_combined)

    languages = structured.get("languages") or []
    lang_lines = []
    for i, lg in enumerate(languages[: RENDER_LIMITS["languages"]]):
        nm = _esc(lg.get("name"))
        lv = _esc(lg.get("level"))
        line = nm + (f' <span class="lvl">— {lv}</span>' if lv else "")
        lang_lines.append(f'<div data-path="languages.{i}">{line}</div>')

    formations = structured.get("formations") or []
    form_blocks = []
    for i, f in enumerate(formations[:2]):
        form_blocks.append(
            f'<div class="formation" data-path="formations.{i}">'
            f'<div class="degree">{_esc(f.get("degree"))}</div>'
            f'<div class="school">{_esc(f.get("school"))}</div>'
            f'<div class="date">{_esc(f.get("period"))}</div>'
            '</div>'
        )

    bottom_html = (
        '<div class="bottom-grid">'
        + ('<section data-path="hard_skills"><h2>Compétences</h2>'
           f'<div class="skills-inline">{skills_inline}</div></section>' if skills_inline else '<div></div>')
        + ('<section data-path="languages"><h2>Langues</h2>'
           f'<div class="lang-inline">{"".join(lang_lines)}</div></section>' if lang_lines else '<div></div>')
        + ('<section data-path="formations"><h2>Formation</h2>'
           + "".join(form_blocks) + '</section>' if form_blocks else '<div></div>')
        + '</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>CV</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{font_link}" rel="stylesheet">
<style>{MINIMAL_1COL_CSS}
{EDITOR_OVERLAY_CSS}
</style>
</head>
<body style="{inline_root}">
<div class="page">
{head_html}
{"".join(body_parts)}
{bottom_html}
</div>
<script>{EDITOR_BRIDGE_JS}</script>
</body>
</html>"""


# ============================================================================
# Template bold_header — bande de couleur en haut, 2col 35/65
# ============================================================================

BOLD_HEADER_CSS = """
@page { size: A4; margin: 0; }
html, body { margin: 0; padding: 0; background: #fff; }
body {
  font-family: var(--font, 'Poppins'), -apple-system, 'Segoe UI', sans-serif;
  color: #1a1a1f;
  font-size: 9pt;
  line-height: 1.5;
  width: 210mm;
  height: 297mm;
  overflow: hidden;
  --sd: var(--sidebar-density, var(--density, 1));
  --md: var(--main-density, var(--density, 1));
  --header-h: 78px;
  --bullet-lh: calc(1.4 + (var(--md) - 1) * 0.5);
  --bullet-gap: calc(2px + (var(--md) - 1) * 10px);
  --exp-gap: calc(11px + (var(--md) - 1) * 20px);
  --section-gap: calc(14px + (var(--md) - 1) * 22px);
  --sidebar-gap: calc(14px + (var(--sd) - 1) * 20px);
  --pad-x: 18mm;
  --pad-y: 14mm;
  --muted: #6b7280;
  --soft: #4a4a55;
  --rule: #e5e7eb;
}
.page { width: 210mm; height: 297mm; box-sizing: border-box; display: flex; flex-direction: column; }
.banner {
  background: var(--accent);
  color: #fff;
  padding: 20px var(--pad-x) 20px var(--pad-x);
  display: flex; align-items: center; gap: 22px;
}
.banner .photo {
  width: 80px; height: 80px; border-radius: 50%;
  background: rgba(255,255,255,.18) center/cover no-repeat;
  border: 3px solid rgba(255,255,255,.7);
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 22pt; color: #fff;
  flex-shrink: 0;
}
.banner .who { flex: 1; min-width: 0; }
.banner h1 {
  margin: 0; font-size: 22pt; font-weight: 800;
  letter-spacing: -0.02em; line-height: 1.05;
}
.banner .role {
  font-size: 11pt; font-weight: 500; opacity: .95;
  margin-top: 4px;
}
.banner .contact {
  font-size: 8.5pt; opacity: .9; margin-top: 6px;
  display: flex; flex-wrap: wrap; gap: 3px 14px;
}
.banner .contact span:not(:last-child)::after {
  content: '·'; margin-left: 14px; opacity: .6;
}
.body-2col {
  display: flex; flex: 1; min-height: 0;
}
.col-left {
  width: 35%; padding: var(--pad-y) 16px var(--pad-y) var(--pad-x);
  box-sizing: border-box;
  display: flex; flex-direction: column; gap: var(--sidebar-gap);
}
.col-right {
  flex: 1; padding: var(--pad-y) var(--pad-x) var(--pad-y) 16px;
  box-sizing: border-box;
  display: flex; flex-direction: column; gap: var(--section-gap);
  min-width: 0;
}
.col-left h2, .col-right h2 {
  font-size: 9pt; margin: 0 0 8px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 1.3px;
  color: var(--accent);
  padding-bottom: 4px; border-bottom: 2px solid var(--accent);
  display: inline-block; align-self: flex-start;
}
.col-left section, .col-right section { display: flex; flex-direction: column; min-width: 0; }
.intro {
  font-size: 9pt; font-style: italic; color: var(--soft);
  margin: 0; padding: 8px 12px;
  background: color-mix(in srgb, var(--accent) 5%, transparent);
  border-left: 3px solid var(--accent);
  line-height: 1.55;
}
.contact-block { font-size: 8.7pt; color: var(--soft); line-height: 1.55; }
.contact-block div { margin-bottom: 2px; word-break: break-word; }
.formation { margin-bottom: 8px; }
.formation .degree { font-size: 9pt; font-weight: 600; line-height: 1.3; }
.formation .school { font-size: 8.5pt; color: var(--muted); }
.formation .date { font-size: 8pt; color: var(--muted); font-style: italic; }
.tag-rows { display: flex; flex-wrap: wrap; gap: 4px; min-width: 0; }
.tag {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  color: var(--accent);
  font-size: 7.8pt; font-weight: 600;
  padding: 3px 7px; border-radius: 999px;
  line-height: 1.3; max-width: 100%; box-sizing: border-box;
  word-break: break-word;
}
.soft-list, .lang-list, .stack-list {
  list-style: none; margin: 0; padding: 0;
  font-size: 8.7pt; color: var(--soft); line-height: 1.6;
}
.lang-list .lvl { color: var(--muted); font-style: italic; }
.exp-card { padding: 0 0 0 14px; border-left: 2px solid var(--accent); }
.exp-card + .exp-card { margin-top: var(--exp-gap); }
.exp-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 1px; }
.exp-head .company { font-size: 9.7pt; font-weight: 700; color: var(--accent); }
.exp-head .date { font-size: 8pt; color: var(--muted); font-style: italic; white-space: nowrap; }
.exp-role { font-size: 9pt; font-weight: 600; margin-bottom: 4px; }
.exp-bullets { list-style: none; margin: 0; padding: 0; }
.exp-bullets li {
  position: relative; padding-left: 12px;
  font-size: 8.5pt; color: var(--soft);
  line-height: var(--bullet-lh); margin-bottom: var(--bullet-gap);
}
.exp-bullets li::before {
  content: '▸'; position: absolute; left: 0; top: 0;
  color: var(--accent); font-size: 8pt;
}
.projects-card { background: transparent; padding: 0; }
.projects-card + .projects-card { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--rule); }
.projects-card .proj-title { font-size: 9pt; font-weight: 600; }
.projects-card .proj-line { font-size: 8.5pt; color: var(--soft); line-height: 1.5; }
""".strip()


def _render_bold_header(structured: dict[str, Any], s: dict[str, Any]) -> str:
    inline_root, _palette = _build_style_block(s)
    font_link = FONT_LINK.get(s.get("font") or "Poppins", FONT_LINK["Poppins"])

    name = _esc(structured.get("name")) or "Prénom Nom"
    role = _esc(structured.get("role"))
    contact = structured.get("contact") or {}
    intro = _esc(structured.get("intro"))

    photo_data_url = get_profile_photo_data_url() if s.get("photo_enabled") else None
    if photo_data_url:
        photo_html = (
            f'<div class="photo" style="background-image:url(\'{photo_data_url}\');'
            f'background-size:cover;background-position:center;color:transparent;"></div>'
        )
    else:
        photo_html = f'<div class="photo">{_initials(structured.get("name"))}</div>'

    contact_spans = []
    for key in ("email", "phone", "location", "linkedin"):
        v = _esc(contact.get(key))
        if v:
            contact_spans.append(f'<span>{v}</span>')
    contact_html = ('<div class="contact">' + "".join(contact_spans) + '</div>') if contact_spans else ""

    banner_html = (
        '<div class="banner">'
        + photo_html
        + '<div class="who">'
        + f'<h1 data-path="name">{name}</h1>'
        + (f'<div class="role" data-path="role">{role}</div>' if role else "")
        + contact_html
        + '</div></div>'
    )

    # Left col : contact détaillé (déjà en banner) + formations + langues + soft skills + tools + hard skills tags
    left_sections: list[str] = []

    formations = structured.get("formations") or []
    if formations:
        items = []
        for i, f in enumerate(formations):
            items.append(
                f'<div class="formation" data-path="formations.{i}">'
                f'<div class="degree">{_esc(f.get("degree"))}</div>'
                f'<div class="school">{_esc(f.get("school"))}</div>'
                f'<div class="date">{_esc(f.get("period"))}</div>'
                '</div>'
            )
        left_sections.append('<section data-path="formations"><h2>Formation</h2>' + "".join(items) + '</section>')

    hard = structured.get("hard_skills") or []
    if hard:
        tags_html = "".join(
            f'<span class="tag" data-path="hard_skills.{i}">{_esc(_shorten_skill(skill))}</span>'
            for i, skill in enumerate(hard[: RENDER_LIMITS["hard_skills"]])
        )
        left_sections.append(
            '<section data-path="hard_skills"><h2>Compétences</h2>'
            f'<div class="tag-rows">{tags_html}</div></section>'
        )

    tools = structured.get("tools") or []
    if tools:
        joined = ", ".join(_esc(t) for t in tools[: RENDER_LIMITS["tools"]])
        left_sections.append(
            '<section data-path="tools"><h2>Stack</h2>'
            f'<ul class="stack-list"><li>{joined}</li></ul></section>'
        )

    soft = structured.get("soft_skills") or []
    if soft:
        lis = "".join(f'<li data-path="soft_skills.{i}">{_esc(x)}</li>' for i, x in enumerate(soft[: RENDER_LIMITS["soft_skills"]]))
        left_sections.append(
            '<section data-path="soft_skills"><h2>Soft Skills</h2>'
            f'<ul class="soft-list">{lis}</ul></section>'
        )

    languages = structured.get("languages") or []
    if languages:
        lis = []
        for i, lg in enumerate(languages[: RENDER_LIMITS["languages"]]):
            nm = _esc(lg.get("name"))
            lv = _esc(lg.get("level"))
            lvl_html = f' <span class="lvl">— {lv}</span>' if lv else ""
            lis.append(f'<li data-path="languages.{i}">{nm}{lvl_html}</li>')
        left_sections.append(
            '<section data-path="languages"><h2>Langues</h2>'
            f'<ul class="lang-list">{"".join(lis)}</ul></section>'
        )

    # Right col : intro + expériences + projets
    right_sections: list[str] = []
    if intro:
        right_sections.append(f'<p class="intro" data-path="intro">{intro}</p>')

    experiences = structured.get("experiences") or []
    if experiences:
        cards = []
        for i, e in enumerate(experiences[: RENDER_LIMITS["experiences"]]):
            bullets = (e.get("bullets") or [])[: RENDER_LIMITS["bullets_per_exp"]]
            bullets_html = "".join(
                f'<li data-path="experiences.{i}.bullets.{j}">{_esc(b)}</li>'
                for j, b in enumerate(bullets)
            )
            cards.append(
                f'<div class="exp-card" data-path="experiences.{i}">'
                '<div class="exp-head">'
                f'<span class="company" data-path="experiences.{i}.company">{_esc(e.get("company"))}</span>'
                f'<span class="date" data-path="experiences.{i}.period">{_esc(e.get("period"))}</span>'
                '</div>'
                f'<div class="exp-role" data-path="experiences.{i}.role">{_esc(e.get("role"))}</div>'
                f'<ul class="exp-bullets">{bullets_html}</ul>'
                '</div>'
            )
        right_sections.append('<section data-path="experiences"><h2>Expérience</h2>' + "".join(cards) + '</section>')

    projects_p = structured.get("projects_pedagogical") or []
    projects_perso = structured.get("projects_personal") or []
    all_p = []
    for i, p in enumerate(projects_p[: RENDER_LIMITS["projects_pedagogical"]]):
        all_p.append(
            f'<div class="projects-card" data-path="projects_pedagogical.{i}">'
            f'<div class="proj-title" data-path="projects_pedagogical.{i}.name">{_esc(p.get("name"))}</div>'
            f'<div class="proj-line" data-path="projects_pedagogical.{i}.summary">{_esc(p.get("summary"))}</div>'
            '</div>'
        )
    for i, p in enumerate(projects_perso[: RENDER_LIMITS["projects_personal"]]):
        all_p.append(
            f'<div class="projects-card" data-path="projects_personal.{i}">'
            f'<div class="proj-title" data-path="projects_personal.{i}.name">{_esc(p.get("name"))}</div>'
            f'<div class="proj-line" data-path="projects_personal.{i}.summary">{_esc(p.get("summary"))}</div>'
            '</div>'
        )
    if all_p:
        right_sections.append('<section><h2>Projets</h2>' + "".join(all_p) + '</section>')

    body_html = (
        '<div class="body-2col">'
        + '<aside class="col-left">' + "".join(left_sections) + '</aside>'
        + '<main class="col-right">' + "".join(right_sections) + '</main>'
        + '</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>CV</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{font_link}" rel="stylesheet">
<style>{BOLD_HEADER_CSS}
{EDITOR_OVERLAY_CSS}
</style>
</head>
<body style="{inline_root}">
{banner_html}
{body_html}
<script>{EDITOR_BRIDGE_JS}</script>
</body>
</html>"""


# ============================================================================
# Registry + dispatcher
# ============================================================================

TEMPLATES = {
    "modern_2col": {
        "fn": _render_modern_2col,
        "label": "Moderne 2 colonnes",
        "description": "Sidebar bleue + main, cards expériences. Le défaut.",
    },
    "minimal_1col": {
        "fn": _render_minimal_1col,
        "label": "Minimaliste 1 colonne",
        "description": "Une colonne centrée, beaucoup d'espace, sobre.",
    },
    "bold_header": {
        "fn": _render_bold_header,
        "label": "Bandeau couleur",
        "description": "Header coloré pleine largeur, body 2 colonnes 35/65.",
    },
}


def list_templates() -> list[dict[str, str]]:
    """Liste des templates disponibles pour l'UI."""
    return [
        {"key": k, "label": v["label"], "description": v["description"]}
        for k, v in TEMPLATES.items()
    ]


def render_cv(structured: dict[str, Any], style: dict[str, Any] | None = None) -> str:
    """Dispatcher : choisit le template selon `style.template`."""
    s = {**DEFAULT_STYLE, **(style or {})}
    tpl = s.get("template") or "modern_2col"
    entry = TEMPLATES.get(tpl) or TEMPLATES["modern_2col"]
    return entry["fn"](structured, s)
