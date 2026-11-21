"""Resa della discovery sulle micro-attività: canali social come contatto e motivi degli scarti."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.orm import sessionmaker

import app.discovery.osm as osm_module
from app.config import Settings
from app.discovery.service import contact_channels, execute_discovery
from app.discovery.types import DiscoveryCandidate
from app.models.entities import Company

ELEMENTS = [
    # Solo profilo Instagram nei tag OSM: niente sito, telefono o email.
    {"type": "node", "id": 901, "lat": 45.521, "lon": 9.593,
     "tags": {"name": "Acconciature Giulia", "shop": "hairdresser", "addr:city": "Romano di Lombardia",
              "contact:instagram": "acconciature_giulia"}},
    # "Sito" che è una pagina Facebook.
    {"type": "node", "id": 902, "lat": 45.522, "lon": 9.594,
     "tags": {"name": "Barber Shop Romano", "shop": "hairdresser", "website": "https://www.facebook.com/barberromano"}},
    {"type": "node", "id": 903, "lat": 45.523, "lon": 9.595,
     "tags": {"name": "Parrucchiere Mario", "shop": "hairdresser", "phone": "+39 0363 111111"}},
    # Nessun contatto: scartata con require_contactable.
    {"type": "node", "id": 904, "lat": 45.524, "lon": 9.596,
     "tags": {"name": "Salone Senza Contatti", "shop": "hairdresser"}},
    # Senza nome e di altro settore: scarti lato OSM.
    {"type": "node", "id": 905, "lat": 45.525, "lon": 9.597, "tags": {"shop": "hairdresser"}},
    {"type": "node", "id": 906, "lat": 45.526, "lon": 9.598, "tags": {"name": "Bar Centrale", "amenity": "bar"}},
]


class Network:
    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, params=None):
        return _Response([{"osm_type": "relation", "osm_id": 43000, "boundingbox": ["45.50", "45.54", "9.56", "9.62"],
                           "display_name": "Romano di Lombardia, Bergamo, Lombardia, Italia"}])

    def post(self, url, data=None):
        return _Response({"elements": ELEMENTS})


class _Response:
    status_code = 200
    text = "{}"

    def __init__(self, payload) -> None:
        self._payload = payload

    def json(self):
        return self._payload


def test_instagram_only_business_counts_as_contactable() -> None:
    tags = {"shop": "hairdresser", "contact:instagram": "acconciature_giulia"}
    candidate = DiscoveryCandidate(name="Acconciature Giulia", extra={"osm_tags": tags})
    assert contact_channels(candidate) == ["instagram"]
    assert contact_channels(DiscoveryCandidate(name="X", website_url="https://www.facebook.com/x")) == ["facebook"]
    assert contact_channels(DiscoveryCandidate(name="Y")) == []


@pytest.fixture
def discovery(client, db_session, sqlite_engine, monkeypatch):
    monkeypatch.setattr("app.api.discovery.execute_discovery", lambda run_id: None)
    factory = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.db.get_session_factory", lambda: factory)
    monkeypatch.setattr(osm_module.httpx, "Client", Network())
    monkeypatch.setattr(osm_module.time, "sleep", lambda _s: None)

    created = client.post("/discoveries", json={
        "industry": "parrucchiere", "location": "Romano di Lombardia, Bergamo, Lombardia",
        "max_results": 50, "extended": True, "require_contactable": True,
    }).json()
    execute_discovery(UUID(created["id"]), Settings())
    return client.get(f"/discoveries/{created['id']}").json()


def test_instagram_only_osm_business_is_kept_as_ig_contact(discovery, db_session) -> None:
    names = {item["name"] for item in discovery["companies"]}
    assert "Acconciature Giulia" in names
    giulia = next(item for item in discovery["companies"] if item["name"] == "Acconciature Giulia")
    assert giulia["instagram_handle"] == "acconciature_giulia"
    assert {"label": "Instagram", "url": "https://instagram.com/acconciature_giulia"} in giulia["social_links"]
    # Salvato anche nella colonna: filtrabile con channel=ig e usato per la deduplica.
    stored = db_session.query(Company).filter_by(name="Acconciature Giulia").one()
    assert stored.instagram_handle == "acconciature_giulia"


def test_run_reports_kept_channels_and_discard_reasons(discovery) -> None:
    assert discovery["status"] == "completed"
    assert discovery["total_found"] == 3
    stats = discovery["stats"]
    assert stats["candidates"] == 4
    assert stats["kept"] == 3
    assert stats["discarded"]["uncontactable"] == 1
    assert stats["contact_channels"] == {"facebook": 1, "instagram": 1, "phone": 1}
    assert stats["osm"]["osm_elements"] == 6
    assert stats["osm"]["unnamed"] == 1
    assert stats["osm"]["other_sector"] == 1
    assert "1 escluse (incontattabili)" in discovery["progress_label"]
