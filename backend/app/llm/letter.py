"""Génération lettre de motivation personnalisée (markdown)."""
from __future__ import annotations

import logging
import random
import re
from datetime import date
from pathlib import Path
from typing import Any

from ..models import Offer
from ..text_clean import strip_long_dashes
from .client import cached_system, complete, complete_json

HAIKU = "claude-haiku-4-5-20251001"

ANALYZE_SYSTEM = """Tu es un recruteur expérimenté en alternance. On te donne une offre.
Identifie ce qui compte VRAIMENT pour départager les candidats sur CE poste précis.

Réponds en JSON strict :
{
  "priorities": ["3 critères/compétences réellement décisifs, concrets"],
  "company_angle": "un élément SPÉCIFIQUE de l'offre (produit, mission, contexte, techno) sur lequel un candidat peut accrocher de façon crédible",
  "proof_wanted": "le type de preuve qui convaincrait le plus (ex: 'avoir déjà mis un agent IA en production')",
  "avoid": ["1-2 clichés ou angles à éviter pour ce poste"]
}"""


async def _analyze_offer(offer: Offer) -> dict[str, Any]:
    """Agent 1 (recruteur) : dégage les vraies priorités de l'offre. Cheap (Haiku)."""
    user = f"""Offre :
Titre : {offer.title}
Entreprise : {offer.company or 'n/c'}
Compétences : {', '.join(offer.skills[:10]) if offer.skills else 'n/c'}

Description :
{offer.description[:3500]}

Renvoie UNIQUEMENT le JSON."""
    return await complete_json(system=ANALYZE_SYSTEM, user=user, max_tokens=600, model=HAIKU)

logger = logging.getLogger(__name__)

ADVICE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "examples" / "advice"

DEFAULT_FORBIDDEN_PHRASES = [
    "c'est avec un vif intérêt",
    "je suis passionné",
    "je serais ravi d'échanger",
    "n'hésitez pas à me contacter",
    "je me permets de vous adresser",
    "exactement l'environnement",
    "non pas parce qu'",
    "force de proposition",  # surutilisé
    "votre entreprise",      # trop vague — nommer ou décrire concrètement
    "dynamique et motivé",
    "à la recherche d'un nouveau défi",
    "en pleine croissance",
    "fortement intéressé par",
    "depuis mon plus jeune âge",
    "votre renommée",
    "rejoindre vos équipes",
]

STYLE_GUIDANCE = {
    "natural": (
        "Ton : professionnel mais NATUREL, comme un échange avec un collègue. "
        "Phrases courtes, idées concrètes. Pas de pirouettes rhétoriques."
    ),
    "factual": (
        "Ton : factuel et direct. Pas d'introduction émotionnelle, pas de superlatifs. "
        "Va aux chiffres, aux outils, aux livrables. Une accroche en 1 phrase, point."
    ),
    "story": (
        "Ton : narratif. Para 1 ouvre sur une mini-anecdote précise (un projet concret, "
        "une situation observée) qui mène au poste. Reste sobre, jamais grandiloquent."
    ),
    "direct": (
        "Ton : très direct, presque brut. Aucune politesse superflue. "
        "Tu peux ouvrir par une question rhétorique. 3 paragraphes courts."
    ),
}


def _parse_advice(path: Path) -> tuple[str, str, str] | None:
    """Retourne (topic, title, body_truncated)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return None
    if not raw.startswith("---"):
        return None
    _, fm, body = raw.split("---", 2)
    topic = "general"
    title = ""
    tm = re.search(r"topic:\s*(\S+)", fm)
    if tm:
        topic = tm.group(1).strip()
    tt = re.search(r"title:\s*(.+)", fm)
    if tt:
        title = tt.group(1).strip()
    return topic, title, body.strip()[:1600]


def _pick_advice(offer: Offer, k: int = 3) -> list[tuple[str, str]]:
    """Sélectionne k articles (title, body) pertinents selon la thématique de l'offre."""
    if not ADVICE_DIR.exists():
        return []
    pool: list[tuple[str, str, str]] = []
    for p in sorted(ADVICE_DIR.glob("*.md")):
        parsed = _parse_advice(p)
        if parsed:
            pool.append(parsed)
    if not pool:
        return []

    by_topic: dict[str, list[tuple[str, str]]] = {"lettre": [], "alternance": [], "candidature": [], "cv": []}
    for topic, title, body in pool:
        by_topic.setdefault(topic, []).append((title, body))
    for lst in by_topic.values():
        random.shuffle(lst)

    picked: list[tuple[str, str]] = []
    for topic in ("lettre", "alternance", "candidature"):
        if by_topic.get(topic) and len(picked) < k:
            picked.append(by_topic[topic].pop(0))
    remaining = [x for lst in by_topic.values() for x in lst]
    random.shuffle(remaining)
    while len(picked) < k and remaining:
        picked.append(remaining.pop(0))
    return picked[:k]


def _addressee(offer: Offer) -> str:
    """Retourne 'l'équipe Foo' ou 'l'équipe de recrutement' selon l'info dispo."""
    company = (offer.company or "").strip()
    if company and company.lower() not in ("n/c", "non communiqué", "anonyme"):
        return f"l'équipe {company}"
    return "l'équipe de recrutement"


def _build_system(advice: list[tuple[str, str]], style: str, forbidden: list[str]) -> list[dict[str, Any]]:
    """Construit un system prompt en BLOCS pour permettre le prompt caching.

    Blocs (du plus stable au plus variable, pour maximiser le cache) :
      1. base (règles génériques) — toujours pareil
      2. conseils experts (advice) — un peu variable mais stable sur une session
      3. style + forbidden — varie selon user config
    """
    style_block = STYLE_GUIDANCE.get(style) or STYLE_GUIDANCE["natural"]
    forbidden_block = ""
    if forbidden:
        forbidden_block = (
            "\n\nFORMULES INTERDITES (à NE JAMAIS utiliser, ni paraphraser de près) :\n- "
            + "\n- ".join(forbidden)
        )

    base = f"""Tu rédiges des lettres de motivation pour un étudiant en recherche d'alternance.

Structure attendue (Markdown) :

**[Nom du candidat]**
[Email] · [Téléphone] · [Localisation] · [LinkedIn si dispo]

[Date au format : Ville, le 14 mai 2026]

À l'attention de [destinataire fourni dans le brief]
Objet : Candidature au poste de [Titre du poste exact] en alternance

Madame, Monsieur,

[INTRODUCTION — le pourquoi EUX] PREMIÈRE PHRASE percutante, sans formule d'introduction ("Je me permets…", "Actuellement étudiant…" INTERDITS en ouverture). Accroche sur un élément CONCRET et précis de l'entreprise ou de l'offre (une mission citée, le produit, une valeur affichée, une techno nommée) qui prouve que tu as lu CETTE offre. Réutilise le vocabulaire exact de l'annonce. Si l'entreprise est inconnue, accroche sur la mission cœur du poste.

[VOUS — leurs besoins] Montre que tu as compris ce que le poste exige : reprends 2-3 attentes/compétences clés de l'offre (ses mots-clés, ses priorités) et amène l'idée que ton profil y répond. Centré sur EUX, pas encore sur toi.

[MOI — tes preuves] Ton parcours au service de ces besoins : expériences et réalisations CHIFFRÉES ("j'ai fait X qui a donné Y" plutôt que "je maîtrise X"), outils/projets RÉELS nommés. Si tu cites plusieurs expériences distinctes, SÉPARE-LES en paragraphes courts (une expérience = un paragraphe).

[NOUS — le lien] Fais la jonction : comment ton profil sert concrètement LEURS objectifs, et en quoi ta façon de travailler / tes valeurs collent à leur mission ou culture. Dis ce que tu veux y construire. Évite "cette étape est importante pour ma carrière" (trop centré sur soi).

[CONCLUSION] Enthousiasme sincère + disponibilité pour un échange/entretien + mention que le CV est joint. Court, naturel, sans formule creuse.

Cordialement,
[Nom du candidat]

RÈGLES IMPÉRATIVES
- ~320-360 mots : développe assez pour bien remplir, sans jamais être creux ni délayer.
- Phrases courtes, voix active. Corps en 4-5 paragraphes suivant Introduction / Vous / Moi / Nous / Conclusion (les blocs Vous et Moi peuvent s'enchaîner naturellement).
- CONCRET > générique : chaque phrase doit pouvoir être fausse pour un autre candidat ou une autre boîte. Si une phrase marcherait pour n'importe qui, supprime-la.
- Ton adapté à la structure : plus direct/dynamique pour une startup, un peu plus formel pour un grand groupe. Naturel et humain, jamais robotique.
- Pas d'accumulation d'adjectifs ("rigoureux, dynamique, motivé") : prouve par un fait à la place. Orthographe irréprochable.
- Réutilise les mots-clés/missions exacts de l'offre (effet miroir), sans copier-coller de paragraphes entiers.
- Commence le corps par la formule d'appel « Madame, Monsieur, » (sur sa propre ligne, avant le paragraphe 1).
- N'utilise JAMAIS de tiret long (— em ou – en), nulle part : remplace par une virgule ou « : ».
- Jamais de placeholder entre crochets dans le rendu final : si une info manque (entreprise inconnue, email/téléphone absent), OMETS la ligne ou reformule neutre. Aucune mention "[entreprise]", "[Startup IA]", "[à compléter]".
- N'invente JAMAIS de fait, chiffre, outil ou expérience absent du CV/profil ou de l'offre. Pas de chiffre inventé : n'utilise que ceux présents dans le profil.
- Pas d'emojis, pas de listes à puces dans les paragraphes.
- Le titre dans l'objet reprend exactement le titre de l'offre (nettoyé du nom d'entreprise et des suffixes H/F).

{style_block}{forbidden_block}

SORTIE : UNIQUEMENT le markdown de la lettre, sans texte avant/après, sans ```."""

    parts: list[str] = [base]
    if advice:
        refs = "\n\n".join(
            f"--- Conseil pro #{i+1} : {title} ---\n{body}"
            for i, (title, body) in enumerate(advice)
        )
        parts.append(
            "Conseils experts (extraits Welcome to the Jungle) à appliquer sans jamais "
            "les citer :\n\n" + refs
        )
    return cached_system(parts)


def _contact_line(profile: dict[str, Any]) -> str:
    parts = []
    if profile.get("email"):
        parts.append(profile["email"])
    if profile.get("phone"):
        parts.append(profile["phone"])
    if profile.get("location"):
        parts.append(profile["location"])
    if profile.get("linkedin"):
        parts.append(profile["linkedin"])
    return " · ".join(parts)


async def generate_letter(
    offer: Offer,
    cv_html: str,
    profile: dict[str, Any],
    profile_text: str | None = None,
    extra_instructions: str | None = None,
) -> str:
    candidate_name = (profile.get("name") or "").strip() or "[Votre nom]"
    style = (profile.get("letter_style") or "natural").lower()
    forbidden = list(profile.get("forbidden_phrases") or DEFAULT_FORBIDDEN_PHRASES)

    advice = _pick_advice(offer, k=3)
    system_blocks = _build_system(advice, style, forbidden)

    today = date.today().strftime("%d %B %Y")
    # Mois en français — strftime renvoie en local : on force FR si possible.
    fr_months = ("janvier", "février", "mars", "avril", "mai", "juin",
                 "juillet", "août", "septembre", "octobre", "novembre", "décembre")
    today = f"{date.today().day} {fr_months[date.today().month - 1]} {date.today().year}"
    city = (profile.get("location") or "").split(",")[0].strip() or "—"

    contact_line = _contact_line(profile)
    tagline = (profile.get("tagline") or "").strip()
    signatures = profile.get("signature_achievements") or []
    extra_user_bits: list[str] = []
    if tagline:
        extra_user_bits.append(f"Tagline candidat : {tagline}")
    if signatures:
        bullets = "\n".join(f"- {s}" for s in signatures[:6])
        extra_user_bits.append(f"Réalisations signature du candidat :\n{bullets}")
    custom = (profile.get("custom_instructions") or "").strip()
    if custom:
        extra_user_bits.append(
            "CONSIGNES PERMANENTES DU CANDIDAT (à respecter impérativement) :\n" + custom
        )
    if extra_instructions and extra_instructions.strip():
        extra_user_bits.append(extra_instructions.strip())

    addressee = _addressee(offer)

    # Agent 1 — analyse recruteur (injectée dans la rédaction, jamais citée telle quelle)
    analysis_block = ""
    try:
        a = await _analyze_offer(offer)
        bits: list[str] = []
        prio = a.get("priorities") or []
        if prio:
            bits.append("Priorités du recruteur : " + " ; ".join(str(p) for p in prio[:3]))
        if a.get("company_angle"):
            bits.append("Accroche concrète possible : " + str(a["company_angle"]))
        if a.get("proof_wanted"):
            bits.append("Preuve qui convainc le plus : " + str(a["proof_wanted"]))
        avoid = a.get("avoid") or []
        if avoid:
            bits.append("À éviter : " + " ; ".join(str(x) for x in avoid[:2]))
        if bits:
            analysis_block = (
                "ANALYSE RECRUTEUR (exploite-la pour cibler la lettre, mais ne la cite "
                "ni ne la paraphrase littéralement) :\n" + "\n".join(bits)
            )
    except Exception as e:
        logger.warning("Analyse offre (lettre) indisponible : %s", e)

    extras = "\n".join(extra_user_bits) if extra_user_bits else ""
    skills_line = ", ".join(offer.skills[:8]) if offer.skills else "non extraites"
    if profile_text:
        facts_block = "PROFIL CANDIDAT (source factuelle — pioche tes preuves ICI) :\n" + profile_text
    else:
        facts_block = "Extrait du CV (HTML — choisir les expériences à citer) :\n" + cv_html[:4000]

    user = f"""Brief :
- Candidat : {candidate_name}
- Ligne contact (à utiliser TELLE QUELLE dans l'en-tête si non vide) : {contact_line or '— (aucun contact fourni)'}
- Date à inscrire : {city}, le {today}
- Destinataire : {addressee}
- Titre du poste (à reprendre dans l'objet, nettoyé) : {offer.title}
- Entreprise : {offer.company or 'inconnue (omettre les mentions de nom)'}
- Localisation offre : {offer.location or 'non précisée'}
- Compétences clés de l'offre : {skills_line}

{analysis_block}

{extras}

{facts_block}

Description complète de l'offre :
{offer.description[:4000]}

Rédige la lettre selon la structure et le ton imposés."""

    draft = await complete(
        system=system_blocks,
        user=user,
        max_tokens=1500,
        temperature=0.6,
    )
    draft = _post_clean(draft, forbidden)
    # 2ᵉ passe Haiku — relecture cheap qui supprime les tics et resserre la prose.
    try:
        polished = await _polish(draft, forbidden)
        return _post_clean(polished, forbidden)
    except Exception as e:
        logger.warning("Polish pass failed (%s) — keep draft", e)
        return draft


POLISH_SYSTEM = """Tu es un relecteur senior. On te donne une lettre de motivation en markdown. Ta tâche :

1. Supprimer les phrases creuses, les formules rebattues et les tournures interdites listées.
2. Test du "n'importe qui" : toute phrase qui marcherait pour un autre candidat OU une autre entreprise → réécris-la pour la rendre spécifique, ou supprime-la.
3. La 1ʳᵉ phrase doit accrocher sur un élément concret de l'offre, sans formule d'intro ("Je me permets", "Actuellement étudiant" interdits en ouverture).
4. Privilégier les preuves chiffrées et le vocabulaire de l'offre ; supprimer les adjectifs vides (dynamique, motivé, rigoureux…).
5. Longueur : ~320-360 mots dans le corps (hors en-tête/objet/signature). Développe assez pour bien remplir, sépare les expériences en paragraphes distincts, sans jamais délayer.
6. Ne PAS changer les faits, noms, dates, chiffres, l'objet, ni la structure en-tête/signature. Ne JAMAIS inventer.
7. Ne JAMAIS introduire de placeholder entre crochets. Garde le français et le registre.

Renvoie UNIQUEMENT la lettre relue en markdown — sans introduction, sans commentaire, sans ```."""


async def _polish(draft: str, forbidden: list[str]) -> str:
    forbidden_block = ""
    if forbidden:
        forbidden_block = "\nTournures interdites :\n- " + "\n- ".join(forbidden)
    user = f"""Lettre brouillon à reluire :

{draft}
{forbidden_block}

Renvoie la version reluite."""
    return await complete(
        system=POLISH_SYSTEM,
        user=user,
        max_tokens=1500,
        temperature=0.3,
        model="claude-haiku-4-5-20251001",
    )


PLACEHOLDER_RE = re.compile(r"\[[^\]]{1,40}\]")


def _post_clean(md: str, forbidden: list[str]) -> str:
    """Garde-fou : retire les éventuels placeholders crochetés qui auraient échappé au LLM."""
    out = md.strip()
    # Supprime les placeholders genre [Entreprise], [à compléter], [Nom]…
    # On garde les listes markdown si jamais (pas de match sur "- " donc OK).
    def _strip_ph(m: re.Match) -> str:
        token = m.group(0).lower()
        if any(k in token for k in ("entreprise", "compl", "à remplir", "nom de", "votre nom", "startup")):
            return ""
        return m.group(0)
    out = PLACEHOLDER_RE.sub(_strip_ph, out)
    out = strip_long_dashes(out)  # l'utilisateur ne veut aucun tiret long
    # Resserre les espaces résiduels
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out + "\n"
