"""Modèles Pydantic partagés entre scrapers, pipeline, API."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Source = Literal[
    "la_bonne_alternance", "indeed", "wttj", "hellowork", "apec",
    "linkedin", "linkedin_manual",
]


class OfferRaw(BaseModel):
    """Sortie d'un scraper, avant scoring."""
    source: Source
    url: str
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    contract: Optional[str] = None
    salary: Optional[str] = None
    description: str = ""
    raw_html: Optional[str] = None
    posted_at: Optional[str] = None

    def dedup_key(self) -> str:
        norm = f"{_normalize(self.title)}|{_normalize(self.company or '')}|{_normalize(self.location or '')}"
        return hashlib.sha1(norm.encode("utf-8")).hexdigest()

    def slug(self) -> str:
        base = f"{self.source}-{_normalize(self.company or 'n')}-{_normalize(self.title)}"[:80]
        return re.sub(r"[^a-z0-9]+", "-", base).strip("-") or self.dedup_key()[:12]


class OfferScored(BaseModel):
    """Offre après analyse LLM."""
    skills: list[str] = Field(default_factory=list)
    score: int = 0
    reasoning: str = ""
    red_flags: list[str] = Field(default_factory=list)


class Offer(OfferRaw, OfferScored):
    id: Optional[int] = None
    dedup_key_: str = ""
    is_favorite: bool = False
    is_hidden: bool = False
    application_status: Optional[str] = None  # suivi candidature (None = à postuler)
    applied_at: Optional[str] = None     # date de candidature
    follow_up_at: Optional[str] = None   # relance prévue
    notes: Optional[str] = None          # notes libres
    contact: Optional[str] = None        # contact recruteur
    checklist: Optional[dict] = None     # étapes cochées {step: bool}
    board_order: Optional[float] = None  # ordre manuel dans la colonne du board
    seen: bool = False                   # offre déjà consultée
    has_docs: bool = False               # CV+lettre déjà générés
    first_run_id: Optional[int] = None  # run qui a découvert l'offre
    is_new: bool = False                # vraie si découverte au dernier run
    scraped_at: Optional[datetime] = None
    scored_at: Optional[datetime] = None


class CV(BaseModel):
    id: Optional[int] = None
    filename: str
    html_content: str
    uploaded_at: Optional[datetime] = None
    is_default: bool = False


class GeneratedDocs(BaseModel):
    id: Optional[int] = None
    offer_id: int
    cv_id: int
    adapted_cv_path: str
    letter_path: str
    generated_at: Optional[datetime] = None


class SourceProgress(BaseModel):
    """État live d'un scraper pendant la phase scraping."""
    source: str
    state: Literal["pending", "running", "done", "error", "skipped"] = "pending"
    count: int = 0
    duration_s: Optional[float] = None
    error: Optional[str] = None
    last_title: Optional[str] = None


class SearchRunProgress(BaseModel):
    stage: Literal["scraping", "scoring", "generating", "done", "error", "idle"]
    source: Optional[str] = None
    current: int = 0
    total: int = 0
    message: str = ""
    offer_id: Optional[int] = None
    per_source: Optional[list[SourceProgress]] = None


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())
