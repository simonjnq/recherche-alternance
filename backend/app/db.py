"""Accès SQLite (aiosqlite). Schéma auto-créé au premier lancement."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

import aiosqlite

from .config import DB_PATH
from .models import CV, GeneratedDocs, Offer, OfferRaw, OfferScored

SCHEMA = """
CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    contract TEXT,
    salary TEXT,
    description TEXT,
    raw_html TEXT,
    posted_at TEXT,
    skills_json TEXT,
    score INTEGER DEFAULT 0,
    reasoning TEXT,
    red_flags_json TEXT,
    is_favorite INTEGER DEFAULT 0,
    is_hidden INTEGER DEFAULT 0,
    first_run_id INTEGER,
    scraped_at TEXT,
    scored_at TEXT
);

CREATE TABLE IF NOT EXISTS cvs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    html_content TEXT NOT NULL,
    uploaded_at TEXT,
    is_default INTEGER DEFAULT 0,
    structured_json TEXT
);

CREATE TABLE IF NOT EXISTS generated_docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id INTEGER NOT NULL,
    cv_id INTEGER NOT NULL,
    adapted_cv_path TEXT,
    letter_path TEXT,
    generated_at TEXT,
    FOREIGN KEY(offer_id) REFERENCES offers(id),
    FOREIGN KEY(cv_id) REFERENCES cvs(id)
);

CREATE TABLE IF NOT EXISTS search_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    stats_json TEXT,
    status TEXT
);

CREATE INDEX IF NOT EXISTS idx_offers_score ON offers(score DESC);
CREATE INDEX IF NOT EXISTS idx_offers_source ON offers(source);
CREATE INDEX IF NOT EXISTS idx_offers_favorite ON offers(is_favorite);
"""


MIGRATIONS = [
    # (table, column, ddl)
    ("cvs", "structured_json", "ALTER TABLE cvs ADD COLUMN structured_json TEXT"),
    ("offers", "first_run_id", "ALTER TABLE offers ADD COLUMN first_run_id INTEGER"),
]


async def _apply_migrations(db: aiosqlite.Connection) -> None:
    for table, column, ddl in MIGRATIONS:
        cur = await db.execute(f"PRAGMA table_info({table})")
        cols = {row[1] for row in await cur.fetchall()}
        if column not in cols:
            try:
                await db.execute(ddl)
                await db.commit()
            except Exception:
                pass


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await _apply_migrations(db)
        await db.commit()


async def connect() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


# --- Offers ---

async def upsert_offer_raw(
    db: aiosqlite.Connection, raw: OfferRaw, run_id: Optional[int] = None
) -> Optional[int]:
    """Insère si nouvelle (sur dedup_key). Retourne l'id si inséré, None si doublon.

    `run_id` rattache l'offre au run qui l'a découverte (sert à isoler les
    nouveautés du dernier run dans l'UI).
    """
    key = raw.dedup_key()
    cur = await db.execute("SELECT id FROM offers WHERE dedup_key = ?", (key,))
    existing = await cur.fetchone()
    if existing:
        return None
    now = datetime.utcnow().isoformat()
    cur = await db.execute(
        """INSERT INTO offers (dedup_key, source, url, title, company, location, contract,
                               salary, description, raw_html, posted_at, first_run_id, scraped_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (key, raw.source, raw.url, raw.title, raw.company, raw.location, raw.contract,
         raw.salary, raw.description, raw.raw_html, raw.posted_at, run_id, now),
    )
    await db.commit()
    return cur.lastrowid


async def latest_run_id(db: aiosqlite.Connection) -> Optional[int]:
    """ID du run le plus récent (sert à marquer les offres 'nouvelles')."""
    cur = await db.execute("SELECT MAX(id) AS m FROM search_runs")
    row = await cur.fetchone()
    return row["m"] if row and row["m"] is not None else None


async def set_offer_scoring(db: aiosqlite.Connection, offer_id: int, scored: OfferScored) -> None:
    now = datetime.utcnow().isoformat()
    await db.execute(
        """UPDATE offers SET skills_json=?, score=?, reasoning=?, red_flags_json=?, scored_at=?
           WHERE id=?""",
        (json.dumps(scored.skills, ensure_ascii=False), scored.score, scored.reasoning,
         json.dumps(scored.red_flags, ensure_ascii=False), now, offer_id),
    )
    await db.commit()


async def list_offers(
    db: aiosqlite.Connection,
    min_score: int = 0,
    favorites_only: bool = False,
    source: Optional[str] = None,
    search: Optional[str] = None,
    new_only: bool = False,
    limit: int = 500,
) -> list[Offer]:
    latest = await latest_run_id(db)
    where = ["is_hidden = 0", "score >= ?"]
    params: list[Any] = [min_score]
    if favorites_only:
        where.append("is_favorite = 1")
    if source:
        where.append("source = ?")
        params.append(source)
    if new_only and latest is not None:
        where.append("first_run_id = ?")
        params.append(latest)
    if search:
        where.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    sql = f"SELECT * FROM offers WHERE {' AND '.join(where)} ORDER BY score DESC, scraped_at DESC LIMIT ?"
    params.append(limit)
    cur = await db.execute(sql, params)
    rows = await cur.fetchall()
    return [_row_to_offer(r, latest) for r in rows]


async def get_offer(db: aiosqlite.Connection, offer_id: int) -> Optional[Offer]:
    latest = await latest_run_id(db)
    cur = await db.execute("SELECT * FROM offers WHERE id = ?", (offer_id,))
    row = await cur.fetchone()
    return _row_to_offer(row, latest) if row else None


async def set_favorite(db: aiosqlite.Connection, offer_id: int, value: bool) -> None:
    await db.execute("UPDATE offers SET is_favorite=? WHERE id=?", (1 if value else 0, offer_id))
    await db.commit()


async def hide_offer(db: aiosqlite.Connection, offer_id: int) -> None:
    await db.execute("UPDATE offers SET is_hidden=1 WHERE id=?", (offer_id,))
    await db.commit()


# --- CVs ---

async def add_cv(db: aiosqlite.Connection, filename: str, html: str, is_default: bool = False) -> int:
    now = datetime.utcnow().isoformat()
    if is_default:
        await db.execute("UPDATE cvs SET is_default=0")
    cur = await db.execute(
        "INSERT INTO cvs (filename, html_content, uploaded_at, is_default) VALUES (?,?,?,?)",
        (filename, html, now, 1 if is_default else 0),
    )
    await db.commit()
    return cur.lastrowid or 0


async def list_cvs(db: aiosqlite.Connection) -> list[CV]:
    cur = await db.execute("SELECT * FROM cvs ORDER BY uploaded_at DESC")
    rows = await cur.fetchall()
    return [_row_to_cv(r) for r in rows]


async def get_default_cv(db: aiosqlite.Connection) -> Optional[CV]:
    cur = await db.execute("SELECT * FROM cvs WHERE is_default=1 LIMIT 1")
    row = await cur.fetchone()
    if row:
        return _row_to_cv(row)
    cur = await db.execute("SELECT * FROM cvs ORDER BY uploaded_at DESC LIMIT 1")
    row = await cur.fetchone()
    return _row_to_cv(row) if row else None


async def delete_cv(db: aiosqlite.Connection, cv_id: int) -> None:
    await db.execute("DELETE FROM cvs WHERE id=?", (cv_id,))
    await db.commit()


async def set_default_cv(db: aiosqlite.Connection, cv_id: int) -> None:
    await db.execute("UPDATE cvs SET is_default=0")
    await db.execute("UPDATE cvs SET is_default=1 WHERE id=?", (cv_id,))
    await db.commit()


async def get_cv_structured(db: aiosqlite.Connection, cv_id: int) -> Optional[dict[str, Any]]:
    cur = await db.execute("SELECT structured_json FROM cvs WHERE id=?", (cv_id,))
    row = await cur.fetchone()
    if not row or not row[0]:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


async def set_cv_structured(db: aiosqlite.Connection, cv_id: int, structured: dict[str, Any]) -> None:
    await db.execute(
        "UPDATE cvs SET structured_json=? WHERE id=?",
        (json.dumps(structured, ensure_ascii=False), cv_id),
    )
    await db.commit()


# --- Generated docs ---

async def add_generated(db: aiosqlite.Connection, docs: GeneratedDocs) -> int:
    now = datetime.utcnow().isoformat()
    cur = await db.execute(
        """INSERT INTO generated_docs (offer_id, cv_id, adapted_cv_path, letter_path, generated_at)
           VALUES (?,?,?,?,?)""",
        (docs.offer_id, docs.cv_id, docs.adapted_cv_path, docs.letter_path, now),
    )
    await db.commit()
    return cur.lastrowid or 0


async def get_docs_for_offer(db: aiosqlite.Connection, offer_id: int) -> Optional[GeneratedDocs]:
    cur = await db.execute(
        "SELECT * FROM generated_docs WHERE offer_id=? ORDER BY generated_at DESC LIMIT 1",
        (offer_id,),
    )
    row = await cur.fetchone()
    if not row:
        return None
    return GeneratedDocs(
        id=row["id"], offer_id=row["offer_id"], cv_id=row["cv_id"],
        adapted_cv_path=row["adapted_cv_path"], letter_path=row["letter_path"],
        generated_at=datetime.fromisoformat(row["generated_at"]) if row["generated_at"] else None,
    )


# --- Row mappers ---

def _row_to_offer(row: aiosqlite.Row, latest_run: Optional[int] = None) -> Offer:
    first_run = row["first_run_id"]
    return Offer(
        id=row["id"],
        dedup_key_=row["dedup_key"],
        source=row["source"],
        url=row["url"],
        title=row["title"],
        company=row["company"],
        location=row["location"],
        contract=row["contract"],
        salary=row["salary"],
        description=row["description"] or "",
        raw_html=row["raw_html"],
        posted_at=row["posted_at"],
        skills=json.loads(row["skills_json"]) if row["skills_json"] else [],
        score=row["score"] or 0,
        reasoning=row["reasoning"] or "",
        red_flags=json.loads(row["red_flags_json"]) if row["red_flags_json"] else [],
        is_favorite=bool(row["is_favorite"]),
        is_hidden=bool(row["is_hidden"]),
        first_run_id=first_run,
        is_new=(latest_run is not None and first_run == latest_run),
        scraped_at=datetime.fromisoformat(row["scraped_at"]) if row["scraped_at"] else None,
        scored_at=datetime.fromisoformat(row["scored_at"]) if row["scored_at"] else None,
    )


def _row_to_cv(row: aiosqlite.Row) -> CV:
    return CV(
        id=row["id"],
        filename=row["filename"],
        html_content=row["html_content"],
        uploaded_at=datetime.fromisoformat(row["uploaded_at"]) if row["uploaded_at"] else None,
        is_default=bool(row["is_default"]),
    )
