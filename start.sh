#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# --- Config ---
VENV=".venv"
PY="${PYTHON:-python3}"

echo "▸ Vérification de l'environnement..."

if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "⚠  .env créé depuis .env.example — remplis ANTHROPIC_API_KEY avant de lancer une recherche."
  fi
fi

# --- Backend venv + deps ---
if [ ! -d "$VENV" ]; then
  echo "▸ Création du venv Python..."
  $PY -m venv "$VENV"
fi

source "$VENV/bin/activate"

echo "▸ Installation des dépendances Python..."
pip install --quiet --upgrade pip
pip install --quiet -r backend/requirements.txt

# --- Playwright browsers (idempotent : no-op si déjà à jour) ---
echo "▸ Vérification Chromium Playwright..."
python -m playwright install chromium 2>&1 | grep -iE "download|install" || true

# --- Frontend build ---
if [ ! -d "frontend/node_modules" ]; then
  echo "▸ Installation des dépendances frontend..."
  (cd frontend && npm install --silent)
fi

if [ ! -d "frontend/dist" ] || [ "${REBUILD_FRONT:-0}" = "1" ]; then
  echo "▸ Build du frontend..."
  (cd frontend && npm run build)
fi

# --- Load env ---
set -a
source .env
set +a

# --- Launch backend ---
echo ""
echo "▸ Démarrage sur http://localhost:${PORT:-8787}"
echo ""

exec python -m backend.app.main
