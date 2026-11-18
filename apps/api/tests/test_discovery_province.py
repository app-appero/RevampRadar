"""Discovery per provincia: località, filtro sui confini e ricerca per comuni su timeout Overpass."""

from __future__ import annotations

from uuid import UUID

import httpx
import pytest
from sqlalchemy.orm import sessionmaker

import app.discovery.osm as osm_module
from app.config import Settings
from app.discovery.osm import OpenStreetMapProvider
from app.discovery.province import (
    compose_location,
    filter_by_province,
    lookup_province,
    point_in_geojson,
    province_scope_for_location,
)
from app.discovery.types import DiscoveryCandidate, DiscoveryQuery

BERGAMO_REL = 44820
BERGAMO_AREA = 3600000000 + BERGAMO_REL
# Confine semplificato: la provincia di Bergamo sta a ovest di ~10.05 E, Brescia città è a 10.21 E.
BERGAMO_BOUNDARY = {
    "type": "Polygon",
    "coordinates": [[[9.40, 45.45], [10.05, 45.45], [10.05, 46.10], [9.40, 46.10], [9.40, 45.45]]],
}

FLORISTS = [
    # Bergamo
    {"type": "node", "id": 1, "lat": 45.6403859, "lon": 9.6847938,
     "tags": {"name": "Fiorin Fiorello", "shop": "florist", "addr:city": "Zanica"}},
    {"type": "node", "id": 2, "lat": 45.6965747, "lon": 9.6821677,
     "tags": {"name": "Il Fiorario del Borgo", "shop": "florist", "addr:city": "Bergamo"}},
    {"type": "node", "id": 3, "lat": 45.6958661, "lon": 9.6525536,
     "tags": {"name": "Potafiori", "shop": "florist"}},
    # Brescia: devono sparire
    {"type": "node", "id": 4, "lat": 45.5855635, "lon": 10.2278215,
     "tags": {"name": "Azienda Agricola Novaflora", "shop": "florist", "addr:city": "Brescia"}},
    {"type": "node", "id": 5, "lat": 45.6993814, "lon": 10.1904201,
     "tags": {"name": "Fiori di Pesco", "shop": "florist", "addr:city": "Gardone Val Trompia"}},
    {"type": "node", "id": 6, "lat": 45.5328839, "lon": 10.2279971,
     "tags": {"name": "Blu Lavanda", "shop": "florist"}},
]


class FakeResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = "{}"

    def json(self):
        return self._payload


class FakeHttp:
    """Sostituisce httpx.Client: instrada Nominatim (GET) e Overpass (POST) verso funzioni di test."""

    def __init__(self, nominatim, overpass) -> None:
        self.nominatim = nominatim
        self.overpass = overpass
        self.gets: list[dict] = []
        self.queries: list[str] = []

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, params=None):
        self.gets.append(dict(params or {}))
        return FakeResponse(self.nominatim(params or {}))

    def post(self, url, data=None):
        query = data["data"]
        self.queries.append(query)
        return self.overpass(query)


def _nominatim_bergamo(params: dict) -> list[dict]:
    return [
        # Il comune di Bergamo arriva per primo: non va scelto per una ricerca provinciale.
        {"osm_type": "relation", "osm_id": 44817, "class": "boundary", "type": "administrative",
         "place_rank": 16, "addresstype": "city", "boundingbox": ["45.67", "45.73", "9.62", "9.72"],
         "display_name": "Bergamo, Lombardia, Italia",
         "geojson": {"type": "Polygon", "coordinates": [[[9.62, 45.67], [9.72, 45.67], [9.72, 45.73], [9.62, 45.67]]]}},
        {"osm_type": "relation", "osm_id": BERGAMO_REL, "class": "boundary", "type": "administrative",
         "place_rank": 12, "addresstype": "county", "boundingbox": ["45.45", "46.10", "9.40", "10.40"],
         "display_name": "Provincia di Bergamo, Lombardia, Italia", "geojson": BERGAMO_BOUNDARY},
    ]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(osm_module.time, "sleep", lambda _seconds: None)


# --- località -------------------------------------------------------------------------


def test_province_code_becomes_full_province_location() -> None:
    assert compose_location(region="Lombardia", province="BG") == "Provincia di Bergamo, Lombardia"
    assert compose_location(province="bg") == "Provincia di Bergamo, Lombardia"
    assert compose_location(province="Provincia di Bergamo") == "Provincia di Bergamo, Lombardia"
    assert compose_location(province="BG", city="Zanica") == "Zanica, Bergamo, Lombardia"
    assert compose_location(location="BG, Lombardia") == "Provincia di Bergamo, Lombardia"
    assert compose_location(province="Bolzano/Bozen") == "Provincia di Bolzano, Trentino-Alto Adige"
    # Valle d'Aosta: provincia e regione coincidono.
    assert compose_location(province="AO") == "Valle d'Aosta"
    assert lookup_province("BS").name == "Brescia"


def test_unknown_province_is_rejected() -> None:
    with pytest.raises(ValueError, match="Provincia non riconosciuta"):
        compose_location(province="XX")


def test_post_discovery_keeps_province_name_not_code(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.discovery.execute_discovery", lambda run_id: None)
    by_code = client.post(
        "/discoveries",
        json={"industry": "fiorista", "region": "Lombardia", "province": "BG", "max_results": 20},
    )
    assert by_code.status_code == 202
    assert by_code.json()["location"] == "Provincia di Bergamo, Lombardia"

    free_text = client.post("/discoveries", json={"industry": "fiorista", "location": "BG, Lombardia"})
    assert free_text.json()["location"] == "Provincia di Bergamo, Lombardia"

    bad = client.post("/discoveries", json={"industry": "fiorista", "province": "XX"})
    assert bad.status_code == 422


def test_scope_only_for_province_locations() -> None:
    assert province_scope_for_location("Provincia di Bergamo, Lombardia").code == "BG"
    assert province_scope_for_location("BG").code == "BG"
    assert province_scope_for_location("Bergamo, Bergamo, Lombardia") is None
    assert province_scope_for_location("Lombardia") is None


# --- filtro ---------------------------------------------------------------------------


def test_filter_without_boundary_uses_address_and_comuni() -> None:
    scope = lookup_province("BG")
    candidates = [
        DiscoveryCandidate(name="A", city="Zanica"),
        DiscoveryCandidate(name="B", city="Brescia"),
        DiscoveryCandidate(name="C", region="BS"),
        DiscoveryCandidate(name="D", region="BG", city="Rezzato"),
        DiscoveryCandidate(name="E", city="Frazione Sconosciuta"),
    ]
    kept = filter_by_province(candidates, scope)
    assert [item.name for item in kept] == ["A", "D", "E"]
    assert all(item.extra["province"] == "Bergamo" for item in kept)
    assert all(item.region == "Lombardia" or item.region == "BG" for item in kept)


def test_point_in_polygon_handles_holes_and_multipolygons() -> None:
    square = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    hole = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
    polygon = {"type": "Polygon", "coordinates": [square, hole]}
    assert point_in_geojson(2, 2, polygon) is True
    assert point_in_geojson(5, 5, polygon) is False
    multi = {"type": "MultiPolygon", "coordinates": [[square], [[[20, 20], [30, 20], [30, 30], [20, 20]]]]}
    assert point_in_geojson(22, 25, multi) is True  # lat 22, lon 25: dentro il triangolo
    assert point_in_geojson(15, 15, multi) is False
    assert point_in_geojson(1, 1, {"type": "Point", "coordinates": [1, 1]}) is None


def test_fiorista_in_provincia_di_bergamo_excludes_brescia(monkeypatch) -> None:
    fake = FakeHttp(_nominatim_bergamo, lambda query: FakeResponse({"elements": FLORISTS}))
    monkeypatch.setattr(osm_module.httpx, "Client", fake)
    provider = OpenStreetMapProvider(Settings())

    found = provider.search_businesses(
        DiscoveryQuery(
            industry="fiorista",
            location="Provincia di Bergamo, Lombardia",
            max_results=50,
            include_without_website=True,
        )
    )

    names = {item.name for item in found}
    assert names == {"Fiorin Fiorello", "Il Fiorario del Borgo", "Potafiori"}
    assert not {item.city for item in found} & {"Brescia", "Gardone Val Trompia"}
    assert fake.gets[0]["q"] == "Provincia di Bergamo, Lombardia"
    assert fake.gets[0]["polygon_geojson"] == 1
    # Overpass cerca nel confine della provincia, non nel rettangolo che include Brescia.
    assert f"area({BERGAMO_AREA})" in fake.queries[0]
    assert "10.40" not in fake.queries[0]


def test_discovery_run_for_bergamo_province_end_to_end(client, db_session, sqlite_engine, monkeypatch) -> None:
    from app.discovery.service import execute_discovery

    monkeypatch.setattr("app.api.discovery.execute_discovery", lambda run_id: None)
    factory = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.db.get_session_factory", lambda: factory)
    monkeypatch.setattr(osm_module.httpx, "Client", FakeHttp(
        _nominatim_bergamo, lambda query: FakeResponse({"elements": FLORISTS})
    ))

    created = client.post(
        "/discoveries",
        json={"industry": "fiorista", "region": "Lombardia", "province": "BG", "max_results": 50, "extended": True},
    ).json()
    execute_discovery(UUID(created["id"]), Settings())

    run = client.get(f"/discoveries/{created['id']}").json()
    assert run["status"] == "completed"
    assert run["location"] == "Provincia di Bergamo, Lombardia"
    assert sorted(item["name"] for item in run["companies"]) == [
        "Fiorin Fiorello",
        "Il Fiorario del Borgo",
        "Potafiori",
    ]
    assert {item["province"] for item in run["companies"]} == {"Bergamo"}


# --- timeout Overpass: ricerca per comuni --------------------------------------------

COMUNI = {
    "elements": [
        {"type": "relation", "id": 101, "tags": {"name": "Zanica", "admin_level": "8"}},
        {"type": "relation", "id": 102, "tags": {"name": "Comun Nuovo", "admin_level": "8"}},
        {"type": "relation", "id": 103, "tags": {"name": "Bergamo", "admin_level": "8"}},
        # Confinante (provincia di Brescia): rel(area) lo include, non va interrogato.
        {"type": "relation", "id": 201, "tags": {"name": "Rezzato", "admin_level": "8"}},
    ]
}
COMUNE_RESULTS = {
    3600000101: [FLORISTS[0]],
    3600000103: [FLORISTS[1], FLORISTS[2]],
    3600000102: [],
}


def _split_overpass(fail_first_attempt_for: set[int], always_fail: set[int] = frozenset()):
    attempts: dict[str, int] = {}
    endpoints = len(osm_module.overpass_endpoints(Settings()))  # un tentativo = tutti i server

    def handler(query: str):
        if "admin_level" in query:
            return FakeResponse(COMUNI)
        if "area(id:" not in query:
            # Query sull'intera provincia: timeout lato server.
            return FakeResponse({"elements": [], "remark": "runtime error: Query timed out"})
        ids = {int(item) for item in query.split("area(id:")[1].split(")")[0].split(",")}
        attempts[query] = attempts.get(query, 0) + 1
        if ids & set(always_fail) or (ids & fail_first_attempt_for and attempts[query] <= endpoints):
            raise httpx.ReadTimeout("timeout")
        elements = [element for area_id in sorted(ids) for element in COMUNE_RESULTS.get(area_id, [])]
        return FakeResponse({"elements": elements})

    return handler


def test_province_timeout_splits_search_by_comuni_with_retry(monkeypatch) -> None:
    fake = FakeHttp(_nominatim_bergamo, _split_overpass(fail_first_attempt_for={3600000101}))
    monkeypatch.setattr(osm_module.httpx, "Client", fake)
    provider = OpenStreetMapProvider(Settings(overpass_comuni_group_size=2, overpass_retry_attempts=2))
    stages: list[tuple[str, int | None]] = []

    found = provider.search_businesses(
        DiscoveryQuery(industry="fiorista", location="Provincia di Bergamo, Lombardia", max_results=50,
                       include_without_website=True),
        on_stage=lambda label, percent=None: stages.append((label, percent)),
    )

    assert {item.name for item in found} == {"Fiorin Fiorello", "Il Fiorario del Borgo", "Potafiori"}
    assert provider.last_warning is None
    group_queries = [query for query in fake.queries if "area(id:" in query]
    assert all("3600000201" not in query for query in group_queries)  # Rezzato (BS) escluso
    assert any("3600000103,3600000102" in query for query in group_queries)  # gruppi da 2
    labels = [label for label, _ in stages]
    assert any("ricerca per comuni 0/3" in label for label in labels)
    assert any("nuovo tentativo 2/2" in label for label in labels)
    assert labels[-1].startswith("Overpass in timeout: ricerca per comuni 3/3")
    assert all(40 <= percent <= 54 for label, percent in stages if percent is not None)


def test_comuni_that_never_answer_make_the_run_partial(db_session, sqlite_engine, monkeypatch) -> None:
    from app.discovery.service import create_discovery_run, execute_discovery

    factory = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.db.get_session_factory", lambda: factory)
    monkeypatch.setattr(
        osm_module.httpx, "Client", FakeHttp(_nominatim_bergamo, _split_overpass(set(), always_fail={3600000101}))
    )
    run = create_discovery_run(
        db_session, industry="fiorista", location="Provincia di Bergamo, Lombardia", max_results=50, extended=True
    )
    execute_discovery(run.id, Settings(overpass_comuni_group_size=3, overpass_retry_attempts=2))

    db_session.expire_all()
    stored = db_session.get(type(run), run.id)
    assert stored.status == "partial"
    assert stored.total_found == 2
    assert "2/3 comuni completati" in stored.error_message
    assert "Zanica" in stored.error_message


def test_non_province_timeout_still_fails_without_splitting(monkeypatch) -> None:
    def nominatim(params):
        return [{"osm_type": "relation", "osm_id": 39152, "boundingbox": ["37", "38", "12", "15"]}]

    fake = FakeHttp(nominatim, lambda query: FakeResponse({"elements": [], "remark": "Query timed out"}))
    monkeypatch.setattr(osm_module.httpx, "Client", fake)
    provider = OpenStreetMapProvider(Settings())
    with pytest.raises(RuntimeError, match="tempo"):
        provider.search_businesses(DiscoveryQuery(industry="fiorista", location="Sicilia", max_results=20))
    assert not any("admin_level" in query for query in fake.queries)
