"""Tests des filtres purs (sans réseau ni LLM) : alternance + pertinence + dedup.

Lancer : cd backend && ../.venv/bin/python -m pytest -q
"""
from __future__ import annotations

import pytest

from app.contract_filter import is_alternance
from app.relevance import is_relevant
from app.models import OfferRaw


def mk(title="", description="", contract=None, source="indeed", company=None):
    return OfferRaw(
        source=source, url="http://x", title=title,
        description=description, contract=contract, company=company,
    )


# ----------------------------------------------------------------------
# Filtre alternance
# ----------------------------------------------------------------------
@pytest.mark.parametrize("offer,expected", [
    (mk("Alternance Data Engineer"), True),
    (mk("Growth Engineer", "Contrat de professionnalisation 12 mois"), True),
    (mk("Assistant IA", "Alternance possible, évolution en CDI à la clé"), True),
    (mk("Développeur Python (CDI)", "Poste en CDI, équipe data."), False),
    (mk("Stage marketing", "Stage de 6 mois"), False),
    (mk("Consultant", "Mission freelance"), False),
    # source alternance-only sans signal explicite → on fait confiance
    (mk("Chargé de projet", "desc neutre", source="apec"), True),
    (mk("Chargé de projet", "desc neutre", source="wttj"), True),
    # source non-fiable sans signal → écartée
    (mk("Chargé de projet", "desc neutre", source="indeed"), False),
])
def test_is_alternance(offer, expected):
    assert is_alternance(offer) is expected


# ----------------------------------------------------------------------
# Filtre pertinence (domaine IA/automation/growth/data/produit)
# ----------------------------------------------------------------------
@pytest.mark.parametrize("offer,expected", [
    (mk("Alternance AI Engineer"), True),
    (mk("Développeur automatisation", "workflows n8n et agents IA"), True),
    (mk("Growth Marketing"), True),
    (mk("Data Analyst", "dashboards et analytics"), True),  # combo data+analyst
    (mk("Product Manager Junior"), True),                    # expression forte
    # hors-domaine
    (mk("Apprenti Cuisinier", "cuisine et service en salle"), False),
    (mk("Juriste immobilier sénior", "droit immobilier"), False),
    (mk("Business Developer BtoB", "prospection et vente terrain"), False),
    (mk("Chargé de recrutement", "sourcing candidats RH"), False),
])
def test_is_relevant(offer, expected):
    assert is_relevant(offer, keywords=None) is expected


def test_is_relevant_keyword_phrase_fallback():
    # un mot-clé multi-mots du profil présent tel quel → pertinent
    o = mk("Spécialiste no-code builder", "outils internes")
    assert is_relevant(o, keywords=["no-code builder"]) is True


# ----------------------------------------------------------------------
# Déduplication
# ----------------------------------------------------------------------
def test_dedup_key_stable_and_normalized():
    a = mk("AI Engineer", company="Acme", source="indeed")
    a.location = "Paris"
    b = mk("  ai   engineer ", company="ACME", source="wttj")  # casse/espaces/source diffèrent
    b.location = "PARIS"
    assert a.dedup_key() == b.dedup_key()


def test_dedup_key_differs_on_company():
    a = mk("AI Engineer", company="Acme"); a.location = "Paris"
    b = mk("AI Engineer", company="Globex"); b.location = "Paris"
    assert a.dedup_key() != b.dedup_key()


def test_slug_is_filesystem_safe():
    o = mk("Développeur IA / Agents (F/H)", company="Acme & Co", source="apec")
    slug = o.slug()
    assert slug and all(c.islower() or c.isdigit() or c == "-" for c in slug)
