from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import anthropic
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from tenacity import RetryError

from .config import FRONTEND_DIST, HOST, PORT
from .db import init_db
from .routes import cvs, offers, search, ws

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def _llm_error_response(exc: BaseException) -> JSONResponse | None:
    """Traduit une erreur Anthropic (éventuellement enveloppée par tenacity) en
    réponse HTTP claire. Retourne None si ce n'est pas une erreur LLM connue."""
    inner: BaseException = exc
    if isinstance(exc, RetryError) and exc.last_attempt is not None:
        try:
            inner = exc.last_attempt.exception() or exc
        except Exception:
            inner = exc
    if not isinstance(inner, anthropic.APIError):
        return None
    msg = str(inner)
    low = msg.lower()
    if "credit balance" in low or "billing" in low or "insufficient" in low:
        return JSONResponse(
            status_code=402,
            content={"detail": "Crédit Anthropic insuffisant. Ajoute des crédits sur "
                               "console.anthropic.com → Plans & Billing, puis réessaie."},
        )
    if isinstance(inner, anthropic.RateLimitError) or "rate limit" in low:
        return JSONResponse(
            status_code=429,
            content={"detail": "Limite de débit Anthropic atteinte. Réessaie dans un moment."},
        )
    if isinstance(inner, anthropic.AuthenticationError) or "api key" in low or "x-api-key" in low:
        return JSONResponse(
            status_code=401,
            content={"detail": "Clé API Anthropic invalide ou manquante (ANTHROPIC_API_KEY)."},
        )
    return JSONResponse(status_code=502, content={"detail": f"Erreur API Anthropic : {msg[:300]}"})


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Recherche Alternance", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RetryError)
async def _retry_error_handler(request: Request, exc: RetryError):
    resp = _llm_error_response(exc)
    if resp is not None:
        return resp
    logger.exception("RetryError non géré: %s", exc)
    return JSONResponse(status_code=500, content={"detail": f"Erreur interne : {str(exc)[:300]}"})


@app.exception_handler(anthropic.APIError)
async def _anthropic_error_handler(request: Request, exc: anthropic.APIError):
    resp = _llm_error_response(exc)
    if resp is not None:
        return resp
    return JSONResponse(status_code=502, content={"detail": f"Erreur API Anthropic : {str(exc)[:300]}"})


app.include_router(offers.router)
app.include_router(offers.templates_router)
app.include_router(cvs.router)
app.include_router(search.router)
app.include_router(ws.router)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True}


# --- Static frontend ---
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        target = FRONTEND_DIST / full_path
        if target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/")
    async def no_frontend() -> dict:
        return {
            "message": "Frontend non build. Lance `cd frontend && npm install && npm run build`, puis relance.",
            "api_docs": "/docs",
        }


def main() -> None:
    import uvicorn
    uvicorn.run("backend.app.main:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()
