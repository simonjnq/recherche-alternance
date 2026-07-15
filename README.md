# Recherche Alternance — moteur de candidature local

Application **locale** qui automatise une recherche d'emploi de bout en bout : un bouton
**« Lancer la recherche »** déclenche le scraping multi-sources → filtrage → scoring par IA →
(à la demande) génération d'un CV et d'une lettre adaptés à chaque offre, le tout suivi dans
un board de candidature façon Kanban.

> Configurée par défaut pour une recherche d'**alternance dans l'IA / automatisation / growth /
> data-produit**, mais **adaptable** à d'autres contrats (CDI, stage…) et d'autres domaines —
> voir [Adapter à une autre recherche](#adapter-à-une-autre-recherche).

Tout tourne sur ta machine. Aucune donnée n'est envoyée ailleurs que vers l'API Claude
(scoring + génération). Pas de compte, pas de cloud.

---

## Fonctionnalités

**Trouver les offres**
- **Scraping multi-sources** : La Bonne Alternance (API v3), Indeed, Welcome to the Jungle,
  HelloWork, APEC, LinkedIn (endpoint public invité, sans login). Pagination + tri par date.
- **Coller une offre** ratée par le scraping : tu colles le texte, l'IA en extrait les champs,
  la score et l'ajoute à la liste comme n'importe quelle offre.
- **Filtres avant scoring** (économisent les appels LLM) : type de contrat, pertinence par
  domaine (réglable), blocage d'entreprises (écoles/CFA), déduplication.
- **Scoring IA** (Claude) : score 0-100, compétences extraites, points d'attention.

**Générer & améliorer la candidature**
- **CV + lettre adaptés** à l'offre, **à la demande** (pour maîtriser le coût). Le CV puise dans
  **TOUS tes CV** uploadés (profils fusionnés) — pas de « CV par défaut ».
- **Lettre en pipeline multi-agents** : analyse recruteur de l'offre → rédaction structurée
  (Introduction / Vous / Moi / Nous / Conclusion) → relecture experte.
- **Agent recruteur** dans l'éditeur : verdict (entretien / mitigé / non), score, forces,
  faiblesses et **corrections cochables** — applique-les au CV **ou** à la lettre séparément.
- **Consignes permanentes** : tes retours récurrents (mémorisés) injectés à chaque génération
  et édition IA ; journal des instructions pour repérer les récurrences.
- **Éditeur CV visuel** (WYSIWYG, densité, gabarits de style) + export PDF.

**Suivre**
- **Board de suivi Kanban** : À postuler → Postulé → Entretien → Retenu / Non retenu, avec
  dates, relances, notes, checklist, taux de réponse, export CSV.
- **Vue Stats**, mode sombre, raccourcis clavier, sélection multiple, comparateur d'offres.
- **Sauvegarde/restauration** complète en JSON.

## Stack

- **Backend** : Python 3.11+ (fonctionne aussi en 3.9), FastAPI, SQLite (aiosqlite),
  httpx + BeautifulSoup (scraping), Playwright (rendu PDF + LinkedIn manuel), Anthropic SDK.
- **Frontend** : React 18 + Vite + TypeScript + Tailwind.
- **Communication** : HTTP REST + WebSocket sur `localhost:8787`.

---

## Démarrage

### Prérequis
- Python 3.11+ (ou 3.9), Node.js 18+, une clé API Anthropic.

### Installation

```bash
git clone https://github.com/simonjnq/recherche-alternance.git
cd recherche-alternance

cp .env.example .env
# édite .env et renseigne ANTHROPIC_API_KEY=sk-ant-...

./start.sh
```

`start.sh` crée le venv, installe les dépendances Python + npm, build le frontend, installe
Chromium (Playwright) et démarre le serveur. Ouvre ensuite **http://localhost:8787**.

Pour rebuilder le frontend après des changements : `REBUILD_FRONT=1 ./start.sh`.

### Clés d'API (`.env`)

| Variable | Requis | Pour quoi |
|---|---|---|
| `ANTHROPIC_API_KEY` | **Oui** | Scoring + génération CV/lettre |
| `LBA_API_KEY` | Optionnel | La Bonne Alternance v3 — [clé gratuite ici](https://api.apprentissage.beta.gouv.fr). Sans elle, cette source est ignorée. |
| `FRANCE_TRAVAIL_CLIENT_ID` / `_SECRET` | Optionnel | Fallback France Travail |

### Premier lancement
1. Onglet **CVs** : dépose ton CV (HTML) et marque-le par défaut.
2. Onglet **Paramètres** : renseigne ton profil, tes mots-clés, ta localisation.
3. Clique **« Lancer la recherche »**.
4. Les offres pertinentes apparaissent scorées ; génère CV+lettre à la demande depuis le détail.

### Coût indicatif
Scraping = gratuit. Scoring ≈ **0,008 €/offre**. Génération CV+lettre ≈ **0,07 €/candidature**
(à la demande). Un premier run « modéré » ≈ 1,5-2,5 € de scoring ; les runs suivants sont quasi
gratuits grâce à la déduplication. Voir l'estimateur sous le bouton « Lancer ».

---

## Architecture

```
backend/app/
  main.py            FastAPI + montage du frontend + gestion d'erreurs LLM
  config.py          Profil utilisateur (data/profile.json) + constantes
  models.py          Modèles Pydantic (Offer, CV, …)
  db.py              SQLite + migrations
  pipeline.py        Orchestrateur « Lancer la recherche »
  contract_filter.py Filtre type de contrat (alternance par défaut)
  relevance.py       Filtre de pertinence par domaine
  scrapers/          1 fichier par source (héritent de base.Scraper)
  llm/               client.py, scoring.py, cv_adapter.py, letter.py, …
  routes/            offers.py, cvs.py, search.py, ws.py
frontend/src/        App.tsx, api.ts, components/
data/                db.sqlite, profile.json, cvs/, offers/  (tous gitignorés)
```

Pipeline : charger profil → scraper en parallèle → **filtrer** (contrat + pertinence + blocage
+ dédup) → **scorer** (Claude) → sauver → génération CV/lettre à la demande.

---

## Adapter à une autre recherche

Le projet est paramétrable à 3 niveaux, du plus simple au plus profond.

### Niveau 1 — Sans toucher au code (Paramètres / `data/profile.json`)

`data/profile.json` est créé au premier lancement (modèle : `data/profile.example.json`).
Éditable via l'onglet **Paramètres** :

- **`keywords`** : tes mots-clés de recherche, par catégories libres.
- **`location`** : ville ciblée.
- **`contract_types`** : libellés affichés (`["alternance"]`, `["CDI"]`, `["stage"]`…).
- **`relevance_strong`** : mots qui **gardent** une offre (signal fort de ton domaine).
- **`relevance_excluded`** : mots qui **écartent** une offre.
- **`blocked_companies`** : entreprises bannies (écoles/CFA, ESN…).
- **`sources_enabled`**, **`score_threshold_generate`**, **`max_offers_per_source`**,
  **`auto_generate`**.

👉 Pour **changer de domaine** (ex. cybersécurité, finance, design…), il suffit souvent de
réécrire `keywords` + `relevance_strong`/`relevance_excluded`.

### Niveau 2 — Affiner le filtre de pertinence (`backend/app/relevance.py`)

Pour un réglage de domaine plus fin que les mots du profil, édite les listes :
`_STRONG_WORDS`, `_STRONG_PHRASES` (signaux forts du domaine) et `_GENERIC` (mots qui ne
comptent qu'en combo). Ex. pour le design : remplacer par `figma`, `ux`, `ui`, `design system`…

### Niveau 3 — Changer de type de contrat (ex. **CDI**)

L'app est câblée « alternance » à plusieurs endroits. Pour viser le **CDI** :

1. **`backend/app/contract_filter.py`** — la fonction `is_alternance` garde les offres
   alternance et rejette CDI/CDD/stage. Inverse la logique (ou neutralise-la) : signal positif
   = `cdi`, négatif = `stage|alternance|apprentissage`. Pense à `ALTERNANCE_ONLY_SOURCES`
   (sources filtrées « alternance » côté requête — voir point 2).
2. **Scrapers** (`backend/app/scrapers/`) — chaque source filtre le contrat à sa façon :
   - `hellowork.py` : paramètre `&c=Alternance` dans l'URL → mettre `CDI`.
   - `apec.py` : `typesContrat` codes `101888/101889` (apprentissage/pro) → code CDI.
   - `wttj.py` : scrape la page SEO `emploi-alternance-<ville>` → page `emploi-cdi-<ville>`.
   - `indeed.py` : suffixe/URL `sort=date` + filtre texte `"altern"/"apprent"` → adapter.
   - `linkedin.py` : suffixe « alternance » ajouté aux mots-clés → retirer/remplacer.
   - `la_bonne_alternance.py` : source **uniquement alternance** → la désactiver pour le CDI.
3. **`backend/app/llm/scoring.py`** — le barème pénalise les postes senior (logique alternant).
   Pour le CDI, retire cette pénalité et adapte le critère « type de contrat ».
4. **`backend/app/llm/letter.py`** — quelques mentions « alternance » à généraliser.

> En clair : niveaux 1-2 = changement de **domaine** (rapide) ; niveau 3 = changement de
> **type de contrat** (touche filtres + scrapers + prompts).

---

## Vie privée & usage

- 100 % local : `data/` (base, CV, offres, profil, photo) est **gitignoré** et ne quitte jamais
  ta machine. Seuls le scoring et la génération appellent l'API Claude.
- Scraping : usage **personnel**, volumes bas, délais, échec silencieux. LinkedIn n'utilise que
  l'endpoint public invité (jamais ta session connectée).

## Licence

Projet personnel. Réutilise-le librement pour ta propre recherche.
