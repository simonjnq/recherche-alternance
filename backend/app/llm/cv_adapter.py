"""Adaptation d'un CV HTML à une offre précise.

On part du CV source (extrait par `cv_extractor`) et on demande à Claude de
produire un CV HTML qui suit un template A4 strict 2 colonnes, en adaptant
titre, hard skills et ordre/phrasé des bullets à l'offre.
"""
from __future__ import annotations

import logging
import re

from ..config import get_profile_photo_data_url
from ..models import Offer
from ..text_clean import strip_long_dashes
from .client import cached_system, complete

logger = logging.getLogger(__name__)

TEMPLATE_REFERENCE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>CV</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  @page { size: A4; margin: 0; }
  html, body { margin: 0; padding: 0; background: #fff; }
  body {
    font-family: 'Poppins', -apple-system, 'Segoe UI', sans-serif;
    color: #1a1a2e;
    font-size: 9pt;
    line-height: 1.5;
    width: 210mm;
    height: 297mm;
    overflow: hidden;
    /* Densité continue : 0.7 (compact) à 1.5 (aéré). Ajustée automatiquement par l'auto-fit. */
    --density: 1.0;
    --bullet-lh: calc(1.45 + (var(--density) - 1) * 0.6);
    --bullet-gap: calc(3px + (var(--density) - 1) * 8px);
    --card-pad-y: calc(12px + (var(--density) - 1) * 6px);
    --card-pad-x: calc(13px + (var(--density) - 1) * 4px);
    --cards-gap: calc(8px + (var(--density) - 1) * 10px);
    --intro-lh: calc(1.65 + (var(--density) - 1) * 0.5);
    --main-pad-y: calc(26px + (var(--density) - 1) * 20px);
    --section-gap: calc(12px + (var(--density) - 1) * 8px);
    --sidebar-pad-y: calc(26px + (var(--density) - 1) * 16px);
    --sidebar-gap: calc(12px + (var(--density) - 1) * 10px);
  }
  .page { display: flex; width: 210mm; height: 297mm; }

  /* Sidebar */
  .sidebar {
    width: 68mm;
    background: #f4f6fc;
    border-right: 1px solid #d8e0f0;
    padding: var(--sidebar-pad-y) 18px var(--sidebar-pad-y);
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: var(--sidebar-gap);
  }
  .sidebar > .head { display: flex; flex-direction: column; gap: 10px; }
  .sidebar > .sections { display: flex; flex-direction: column; flex: 1; gap: var(--sidebar-gap); }
  .sidebar .photo {
    width: 96px;
    height: 96px;
    border-radius: 50%;
    border: 3px solid #2d52c4;
    background: #e4eaf8 center/cover no-repeat;
    margin: 0 auto;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 28pt; color: #2d52c4;
  }
  .sidebar h1 {
    font-size: 13pt; font-weight: 800; margin: 0; text-align: center; color: #1a1a2e;
  }
  .sidebar .role {
    font-size: 9pt; text-align: center; color: #2d52c4; font-weight: 600; margin-top: 2px;
  }
  .sidebar h2 {
    font-size: 7.5pt; text-transform: uppercase; letter-spacing: 0.8px;
    font-weight: 800; color: #2d52c4; margin: 0 0 6px; padding-bottom: 4px;
    border-bottom: 1px solid #d8e0f0;
  }
  .sidebar section { display: flex; flex-direction: column; gap: 4px; }
  .contact { font-size: 9pt; color: #333; }
  .contact div { margin-bottom: 2px; word-break: break-word; }
  .formation .degree { font-size: 8.5pt; font-weight: 700; color: #1a1a2e; }
  .formation .school { font-size: 8pt; color: #555; }
  .formation .date { font-size: 7.8pt; font-style: italic; color: #999; }
  .tag-rows { display: flex; flex-direction: column; gap: 4px; }
  .tag-row { display: flex; gap: 4px; flex-wrap: nowrap; }
  .tag {
    background: #e4eaf8; color: #2d52c4;
    font-size: 7.8pt; font-weight: 600;
    padding: 3px 8px; border-radius: 4px; white-space: nowrap;
  }
  .soft-list, .lang-list, .stack-list {
    list-style: none; margin: 0; padding: 0;
    display: flex; flex-direction: column; gap: 3px;
    font-size: 8.5pt; color: #333;
  }
  .lang-list li .lvl { color: #999; font-style: italic; }

  /* Main */
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
  .exp-card + .exp-card { margin-top: var(--cards-gap); }
  .intro {
    font-size: 9.5pt; font-style: italic; color: #444; line-height: var(--intro-lh);
    border-left: 3px solid #2d52c4; padding: 2px 0 2px 12px;
  }
  .main h2 {
    font-size: 13pt; font-weight: 800; margin: 0 0 6px; color: #1a1a2e;
  }
  .main h2 .accent { color: #2d52c4; }
  .exp-card {
    background: #f9fafd; border-left: 3px solid #2d52c4;
    border-radius: 6px;
    padding: var(--card-pad-y) var(--card-pad-x) var(--card-pad-y) calc(var(--card-pad-x) - 1px);
  }
  .exp-head {
    display: flex; align-items: baseline; justify-content: space-between; gap: 8px;
    margin-bottom: 2px;
  }
  .exp-head .company { color: #2d52c4; font-size: 9.5pt; font-weight: 800; }
  .exp-head .date { font-size: 8pt; font-style: italic; color: #999; }
  .exp-role { font-size: 9pt; font-weight: 700; color: #1a1a2e; margin-bottom: 5px; }
  .exp-bullets { list-style: none; margin: 0; padding: 0; }
  .exp-bullets li {
    position: relative; padding-left: 14px;
    font-size: 8.5pt; color: #333;
    line-height: var(--bullet-lh); margin-bottom: var(--bullet-gap);
  }
  .exp-bullets li::before {
    content: ''; position: absolute; left: 0; top: 6px;
    width: 6px; height: 6px; border-radius: 50%; background: #2d52c4;
  }
  .projects-card {
    background: #eef2ff; border: 1px solid #c5d0f0;
    border-radius: 6px;
    padding: calc(var(--card-pad-y) - 1px) var(--card-pad-x);
  }
  .projects-card + .projects-card { margin-top: var(--cards-gap); }
  .projects-card .proj-title { font-size: 9pt; font-weight: 700; color: #1a1a2e; }
  .projects-card .proj-line { font-size: 8.5pt; color: #333; line-height: 1.5; }
  .projects-card .proj-line + .proj-title { margin-top: 6px; }
</style>
</head>
<body class="density-normal">
<div class="page">
  <aside class="sidebar">
    <div class="head">
      <div class="photo">XX</div>  <!-- initiales si pas de photo -->
      <div>
        <h1>Prénom Nom</h1>
        <div class="role">Titre adapté à l'offre</div>
      </div>
    </div>
    <div class="sections">
      <section>
        <h2>Contact</h2>
        <div class="contact">
          <div>email@exemple.fr</div>
          <div>+33 6 00 00 00 00</div>
          <div>linkedin.com/in/handle</div>
        </div>
      </section>
      <section>
        <h2>Formation</h2>
        <div class="formation">
          <div class="degree">Nom diplôme</div>
          <div class="school">École / université</div>
          <div class="date">2023 — 2026</div>
        </div>
      </section>
      <section>
        <h2>Hard Skills</h2>
        <div class="tag-rows">
          <div class="tag-row"><span class="tag">Skill 1</span><span class="tag">Skill 2</span></div>
          <!-- max 4 lignes de 2 tags -->
        </div>
      </section>
      <section>
        <h2>Soft Skills</h2>
        <ul class="soft-list"><li>Soft 1</li><li>Soft 2</li><li>Soft 3</li></ul>
      </section>
      <section>
        <h2>Stack &amp; Outils</h2>
        <ul class="stack-list"><li>Outil 1, Outil 2</li></ul>
      </section>
      <section>
        <h2>Langues</h2>
        <ul class="lang-list"><li>Français <span class="lvl">— natif</span></li></ul>
      </section>
    </div>
  </aside>
  <main class="main">
    <div class="top">
      <p class="intro">Phrase d'intro italique adaptée à l'offre.</p>
    </div>
    <div class="flow">
      <section>
        <h2>Expériences <span class="accent">professionnelles</span></h2>
        <div class="exp-card">
          <div class="exp-head"><span class="company">Entreprise</span><span class="date">Mois AAAA — Mois AAAA</span></div>
          <div class="exp-role">Intitulé du poste</div>
          <ul class="exp-bullets">
            <li>Bullet orienté impact aligné avec l'offre.</li>
            <li>Bullet chiffré si possible.</li>
          </ul>
        </div>
      </section>
      <section>
        <h2>Projets <span class="accent">pédagogiques</span></h2>
        <div class="projects-card">
          <div class="proj-title">Nom du projet</div>
          <div class="proj-line">Description courte pertinente pour l'offre.</div>
        </div>
      </section>
      <section>
        <h2>Projets <span class="accent">personnels</span></h2>
        <div class="projects-card">
          <div class="proj-title">Nom du projet</div>
          <div class="proj-line">Description courte.</div>
        </div>
      </section>
    </div>
  </main>
</div>
</body>
</html>
"""

SYSTEM_INTRO = """Tu es un expert en rédaction de CV pour alternance. Tu produis des CV HTML prêts à imprimer en PDF A4.

On va te donner :
1. Un CV SOURCE (HTML) contenant toutes les informations factuelles du candidat.
2. Une OFFRE d'alternance cible.

Ta tâche : renvoyer un CV HTML **complet** qui suit EXACTEMENT le template fourni en référence, en adaptant le contenu textuel à l'offre — sans jamais inventer de faits."""

SYSTEM_TEMPLATE = f"""=== TEMPLATE DE RÉFÉRENCE (structure, classes et CSS à conserver à l'identique) ===
{TEMPLATE_REFERENCE}
=== FIN DU TEMPLATE ==="""

SYSTEM_RULES = """RÈGLES DE FORMAT (impératives)
- A4 strict : 210mm × 297mm, 1 page exactement, aucun débordement.
- @page margin 0 ; le padding est géré par le CSS du template. Ne change pas la feuille de style.
- Police Poppins via Google Fonts (garde les <link> dans <head>).
- Couleur principale #2d52c4, fond sidebar #f4f6fc, cards expé #f9fafd, cards projets #eef2ff.
- Structure 2 colonnes : sidebar 68mm à gauche, main flex:1 à droite.

CAPS DURS DE CONTENU (à NE PAS dépasser — sinon le CV déborde)
- Hard Skills : affiche TOUTES les compétences techniques pertinentes pour l'offre présentes dans le profil (PAS de limite de nombre). Chacune ≤ 22 caractères, UN concept par tag ("n8n", "RAG", "LLM Ops", PAS "Automatisation n8n / Zapier / Make"). Coupe en plusieurs tags si besoin.
- Soft Skills : tous les soft skills pertinents (reste concis, mots simples).
- Stack & Outils : tous les outils pertinents, mots-clés courts séparés par virgule.
- Langues : 3 max.
- Formations : 1-2 max.
- Expériences : 3 max (4 si le candidat n'a que ça). Garde les plus pertinentes pour l'offre.
- Bullets par expérience : 3 max, **≤ 14 mots chacun**. Verbe d'action en premier, résultat ou outil concret en second. Pas de bullets génériques.
- Projets pédagogiques : 2 max. Description ≤ 18 mots.
- Projets personnels : 2 max. Description ≤ 18 mots.
- Intro italique : 1 phrase, 15-25 mots max.
- REMPLISSAGE VERTICAL : la sidebar et le main doivent OCCUPER toute la hauteur A4, sans jamais laisser un gros trou visible entre deux sections. L'aération passe par les micro-espacements (line-height bullets, gap bullets, padding cards, gap cards, padding intro), JAMAIS par un gros margin/gap entre deux sections. NE CHANGE PAS la structure (wrappers `.head` / `.sections` / `.top` / `.flow`).
- DENSITÉ : choisis la classe du <body> selon le volume de contenu :
  - `density-compact` → beaucoup de contenu (≥3 expériences avec ≥4 bullets chacune, plusieurs projets). Objectif : faire tenir sans déborder.
  - `density-normal` → volume moyen (2-3 expériences, 3-5 bullets, 1-2 projets). Valeur par défaut.
  - `density-airy` → peu de contenu (1-2 expériences, ≤3 bullets, 0-1 projet). Objectif : remplir la page en aérant uniformément.
  Écris par exemple `<body class="density-airy">` si le CV source est léger.

RÈGLES DE CONTENU
- Le TITRE sous le nom (div.role) est adapté à l'offre (ex: "Alternance Growth & Automatisation", "Alternance AI Automation & Growth Builder", "Alternance Product Manager IA"). Court, en français.
- Les HARD SKILLS tags sont choisis et ordonnés selon les compétences demandées par l'offre, en puisant uniquement dans ce que montre le CV source (outils, langages, méthodes réellement présents).
- L'ORDRE des expériences peut être réordonné selon la pertinence pour le poste.
- Les BULLETS sont reformulés pour faire ressortir action + impact aligné sur l'offre. Utilise le vocabulaire exact de l'offre quand c'est honnête (ex: si l'offre dit "n8n", garde "n8n" et pas "outil de workflow").
- Les faits factuels (dates, noms d'entreprises, diplômes, écoles, villes, nom, email, téléphone, LinkedIn) restent INCHANGÉS — tu n'inventes rien.
- Si une section n'a pas de contenu dans le CV source (ex: pas de projets personnels), SUPPRIME complètement la balise <section> correspondante. Ne mets jamais de texte placeholder.
- Si pas de photo dans le CV source : mets les initiales dans `.photo` (2 lettres majuscules). Si une image URL ou un data:image est fourni dans le CV source, injecte-la via `style="background-image:url(…)"`.
- Intro : une phrase italique adaptée à l'offre (2 lignes max).

AVANT DE RENDRE, CHECKLIST IMPLICITE
- Pas d'overflow sidebar ni main (si doute, raccourcis bullets ou skills).
- Tags rentrent dans leur ligne.
- 1 page exactement.
- Aucune information inventée.

SORTIE
Retourne UNIQUEMENT le HTML complet (de <!DOCTYPE html> à </html>), sans texte avant ni après, sans balises ```."""


SYSTEM_BLOCKS = cached_system([SYSTEM_INTRO, SYSTEM_TEMPLATE, SYSTEM_RULES])


async def adapt_cv(
    cv_html: str, offer: Offer, profile_text: str | None = None,
    extra_instructions: str | None = None,
) -> str:
    offer_text = f"""Offre :
Titre : {offer.title}
Entreprise : {offer.company or 'n/c'}
Localisation : {offer.location or 'n/c'}
Compétences extraites : {', '.join(offer.skills) if offer.skills else 'n/c'}

Description complète :
{offer.description[:5000]}"""

    if profile_text:
        facts_block = (
            "PROFIL CANDIDAT (source de vérité — c'est dans CE bloc que tu vas piocher "
            "noms, dates, bullets, écoles, compétences. Le HTML qui suit n'est qu'un appui "
            "stylistique secondaire) :\n" + profile_text
        )
    else:
        facts_block = "PROFIL CANDIDAT : (non extrait — utiliser le HTML source comme référence)"

    custom_block = ""
    if extra_instructions and extra_instructions.strip():
        custom_block = (
            "\n\nCONSIGNES PERMANENTES DU CANDIDAT (à respecter impérativement) :\n"
            + extra_instructions.strip()
        )

    user = f"""{facts_block}

---

CV SOURCE (HTML — pour repère stylistique uniquement) :
{cv_html}

---

{offer_text}{custom_block}

Produis la version HTML du CV adaptée à cette offre, en suivant strictement le template."""

    result = await complete(
        system=SYSTEM_BLOCKS,
        user=user,
        max_tokens=8000,
        temperature=0.4,
    )
    result = result.strip()
    if result.startswith("```"):
        result = result.split("```", 2)[1]
        if result.lower().startswith("html"):
            result = result[4:]
        result = result.rsplit("```", 1)[0].strip()

    # Garde-fou : ne JAMAIS livrer un CV resté sur les placeholders du template
    # (arrive si le profil source est vide / extraction LLM ratée).
    _assert_real_cv(result)
    result = strip_long_dashes(result)
    return inject_profile_photo(result)


_PLACEHOLDER_MARKERS = ("Prénom Nom", "email@exemple.fr")


def _assert_real_cv(html: str) -> None:
    """Lève si le CV produit est un placeholder (template non rempli) ou quasi vide."""
    for marker in _PLACEHOLDER_MARKERS:
        if marker in html:
            raise ValueError(
                "CV adapté non rempli (placeholder du template encore présent) — "
                "profil source insuffisant. Vérifie qu'un CV exploitable est uploadé."
            )
    visible = re.sub(r"<(style|script|head)[^>]*>.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    visible = re.sub(r"<[^>]+>", " ", visible)
    visible = re.sub(r"\s+", " ", visible).strip()
    if len(visible) < 250:
        raise ValueError(f"CV adapté trop court ({len(visible)} car.) — génération invalide.")


PHOTO_DIV_RE = re.compile(r'(<div\s+class="photo"[^>]*?)(\s*/?>)(.*?)(</div>)', re.IGNORECASE | re.DOTALL)


def inject_profile_photo(html: str) -> str:
    """Remplace le contenu du div.photo par la photo utilisateur si elle existe."""
    data_url = get_profile_photo_data_url()
    if not data_url:
        return html
    style = (
        f'style="background-image:url(\'{data_url}\');'
        f"background-size:cover;background-position:center;color:transparent;\""
    )

    def _sub(m: re.Match) -> str:
        # strip existing inline style="..."
        open_tag = m.group(1)
        open_tag = re.sub(r'\s+style="[^"]*"', "", open_tag)
        return f"{open_tag} {style}></div>"

    new_html, n = PHOTO_DIV_RE.subn(_sub, html, count=1)
    return new_html if n else html
