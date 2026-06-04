# Recherche Alternance — App locale

Application locale de recherche automatisée d'alternance. Un bouton **"Lancer la recherche"** déclenche : scraping multi-sources → scoring → génération CV/lettre personnalisés → sauvegarde.

## Stack

- **Backend** : Python 3.11+, FastAPI, Playwright (scraping), SQLite (stockage), Anthropic SDK (LLM)
- **Frontend** : React 18 + Vite + TypeScript + Tailwind + shadcn/ui
- **Communication** : HTTP REST + WebSocket (progrès live) sur `localhost:8787`
- **Distribution** : `./start.sh` lance backend + sert le frontend statique. App accessible à `http://localhost:8787`

Pas de Tauri/Electron pour l'instant — la webapp locale est plus simple et offre la même UX.

## Architecture

```
backend/app/
  main.py           FastAPI entrypoint + montage frontend statique
  config.py         Mots-clés, profil utilisateur (chargé depuis data/profile.json)
  models.py         Pydantic : Offer, CV, Letter, SearchRun, etc.
  db.py             SQLite (aiosqlite) + migrations
  pipeline.py       Orchestrateur du bouton "Lancer la recherche"
  scrapers/         Un fichier par source. Hérite de base.Scraper
  llm/              client.py (Anthropic), scoring.py, cv_adapter.py, letter.py
  routes/           offers.py, cvs.py, search.py, ws.py

frontend/src/
  App.tsx           Layout principal (sidebar + main)
  api.ts            Client HTTP + WebSocket
  components/       Sidebar, OfferList, OfferDetail, Filters, CVUpload, SearchButton

data/
  db.sqlite         Base locale (créée au premier lancement)
  cvs/              CVs HTML uploadés par l'utilisateur (drag-drop)
  offers/<slug>/    Un dossier par offre : offer.json + cv.html + letter.md
  profile.json      Profil utilisateur (mots-clés, localisation, préférences)
```

## Mots-clés de recherche (par défaut)

Stockés dans `data/profile.json`, éditables via UI :

- **IA/Automation** : automatisation IA, LLM, agent IA, n8n, Zapier, workflow IA
- **Growth** : growth engineer, growth marketing IA, acquisition IA
- **Tech/Builder** : prompt engineer, no-code builder, scraping automatisation
- **Data/Produit** : product manager IA, business analyst IA
- **Combos** : IA alternance Paris, AI engineer alternance, no-code alternance Paris

## Sources d'offres

| Source | Méthode | Robustesse |
|---|---|---|
| **La Bonne Alternance** (France Travail) | API officielle gratuite (httpx) | ★★★★★ |
| **Indeed** | httpx + JSON mosaic (sort=date, 2 pages) | ★★★☆☆ |
| **Welcome to the Jungle** | httpx + bs4 (pages SEO alternance) | ★★★★☆ |
| **HelloWork** | httpx + bs4 (tri=Date, 2 pages) | ★★★★☆ |
| **Apec** | API JSON publique (httpx) | ★★★☆☆ |
| **LinkedIn** (auto) | Endpoint invité `jobs-guest` (httpx, sans login) | ★★★☆☆ |
| **LinkedIn** (manuel) | Utilisateur colle URLs (Playwright) | n/a |

LinkedIn auto : on utilise UNIQUEMENT l'endpoint public `jobs-guest` (anonyme, aucun
cookie/compte) → ne risque pas le compte utilisateur, seul risque = rate-limit IP (429),
géré comme les autres scrapers (volume bas, délais, échec silencieux). On ne scrape
JAMAIS la session connectée (c'est ça qui faisait bannir). LinkedIn n'a pas de filtre
contrat alternance fiable : on suffixe les mots-clés par « alternance » et on récupère la
description réelle de chaque offre (endpoint `jobPosting` invité) pour le scoring.
Mode manuel conservé en parallèle : l'utilisateur colle une URL, le parseur extrait l'OG/contenu public.

## Anti-blocage

- User-Agent réalistes, rotation
- Délais aléatoires entre requêtes (1-4s)
- Retry avec backoff exponentiel
- Respect robots.txt *indicatif* (pas contraignant en usage personnel)
- Playwright en mode `stealth` (plugin `playwright-stealth`)
- Pas de parallélisation agressive : max 2 scrapers simultanés

## Pipeline "Lancer la recherche"

1. Charger profil + mots-clés depuis `data/profile.json`
2. Pour chaque source activée, lancer scraper → collecter offres brutes
3. Déduplication (clé = hash normalisé titre + entreprise + localisation)
4. Pour chaque offre nouvelle : appel Claude pour extraire `skills`, `score` (0-100), `reasoning`
5. Sauvegarder en DB
6. Pour les offres score ≥ seuil (défaut 70) : adapter CV + générer lettre
7. Créer `data/offers/<slug>/` avec `offer.json`, `cv.html`, `letter.md`
8. Progrès poussé via WebSocket à l'UI

## Modèle de données (SQLite)

```sql
offers (id, source, url, title, company, location, contract, salary,
        description, raw_html, skills_json, score, reasoning,
        is_favorite, is_hidden, scraped_at, scored_at)

cvs (id, filename, html_content, uploaded_at, is_default)

generated_docs (id, offer_id, cv_id, adapted_cv_path, letter_path, generated_at)

search_runs (id, started_at, finished_at, stats_json, status)
```

## LLM (Claude API)

- Clé dans `ANTHROPIC_API_KEY` (env var, jamais en dur)
- Modèle par défaut : `claude-sonnet-4-6` (rapport qualité/prix optimal pour scoring + génération)
- Prompt caching activé (profil utilisateur + CVs en cache)
- Coût estimé : ~0.02-0.05€ par offre traitée

## Démarrage

```bash
# Premier lancement
./start.sh
# Ouvre http://localhost:8787
```

`start.sh` : crée venv si absent, installe deps Python, installe deps npm + build frontend, lance Playwright install, démarre FastAPI.

## Conventions

- **Typage strict** : Pydantic côté Python, TypeScript strict côté front
- **Pas de secrets en dur** : tout via `.env` (non commité)
- **Erreurs scraping** : catch + log + continue. Un scraper qui plante ne doit jamais bloquer les autres
- **Tests** : pytest pour backend. Priorité sur pipeline + LLM prompts (snapshots)
- **Commentaires** : uniquement quand le "pourquoi" n'est pas évident
