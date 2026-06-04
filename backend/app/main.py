from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIST, HOST, PORT
from .db import init_db
from .routes import cvs, offers, search, ws

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


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
