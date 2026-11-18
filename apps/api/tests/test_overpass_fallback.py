"""Overpass irraggiungibile: ripiego sui server di riserva, nuovi tentativi, retry della discovery."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy.orm import sessionmaker

import app.discovery.osm as osm_module
from app.config import Settings
from app.discovery.osm import OpenStreetMapProvider, OverpassUnavailableError, overpass_endpoints
from app.discovery.service import create_discovery_run, execute_discovery
from app.discovery.types import DiscoveryCandidate, DiscoveryQuery
from app.models.entities import Company, DiscoveryResult, DiscoveryRun

MAIN = "overpass-api.de"
KUMI = "overpass.kumi.systems"
COFFEE = "overpass.private.coffee"
TREVISO_REL = 39123
TREVISO_BOUNDARY = {
    "type": "Polygon",
    "coordinates": [[[11.85, 45.55], [12.65, 45.55], [12.65, 46.05], [11.85, 46.05], [11.85, 45.55]]],
}
FLORISTS_TV = [
    {"type": "node", "id": 11, "lat": 45.6669, "lon": 12.2430,
     "tags": {"name": "Fiori di Treviso", "shop": "florist", "addr:city": "Treviso", "website": "https://fioritv.it"}},
    {"type": "node", "id": 12, "lat": 45.8875, "lon": 12.2970,
     "tags": {"name": "Conegliano in Fiore", "shop": "florist", "addr:city": "Conegliano", "phone": "0438 1"}},
]
UNREACHABLE = httpx.ConnectError("[Errno 101] Network is unreachable")


class Response:
    def __init__(self, payload, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = "{}"

    def json(self):
        return self._payload


class FakeNetwork:
    """httpx.Client finto: Nominatim risponde, ogni server Overpass segue la sua regola."""

    def __init__(self, overpass_rules: dict[str, object]) -> None:
        self.rules = overpass_rules
        self.posts: list[str] = []

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, params=None):
        return Response([
            {"osm_type": "relation", "osm_id": TREVISO_REL, "class": "boundary", "type": "administrative",
             "place_rank": 12, "addresstype": "county", "boundingbox": ["45.55", "46.05", "11.85", "12.65"],
             "display_name": "Provincia di Treviso, Veneto, Italia", "geojson": TREVISO_BOUNDARY},
        ])

    def post(self, url, data=None):
        host = httpx.URL(url).host
        self.posts.append(host)
        rule = self.rules.get(host, UNREACHABLE)
        if isinstance(rule, BaseException):
            raise rule
        return rule(data["data"]) if callable(rule) else rule


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(osm_module.time, "sleep", lambda _seconds: None)


def _treviso_query() -> DiscoveryQuery:
    return DiscoveryQuery(
        industry="fiorista", location="Provincia di Treviso, Veneto", max_results=50, include_without_website=True
    )


def test_backup_servers_are_configured_after_the_main_one() -> None:
    hosts = [httpx.URL(url).host for url in overpass_endpoints(Settings())]
    assert hosts[0] == MAIN
    assert hosts.index(KUMI) < hosts.index(COFFEE) < hosts.index("lz4.overpass-api.de")


def test_fiorista_treviso_completes_from_backup_when_main_is_unreachable(monkeypatch) -> None:
    network = FakeNetwork({MAIN: UNREACHABLE, KUMI: Response({"elements": FLORISTS_TV})})
    monkeypatch.setattr(osm_module.httpx, "Client", network)
    provider = OpenStreetMapProvider(Settings())

    found = provider.search_businesses(_treviso_query())

    assert {item.name for item in found} == {"Fiori di Treviso", "Conegliano in Fiore"}
    assert network.posts == [MAIN, KUMI]
    assert provider.last_warning is None


def test_discovery_run_completes_from_backup(client, db_session, sqlite_engine, monkeypatch) -> None:
    """Accettazione: con l'endpoint principale irraggiungibile la ricerca si completa dalla riserva."""
    monkeypatch.setattr("app.api.discovery.execute_discovery", lambda run_id: None)
    factory = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.db.get_session_factory", lambda: factory)
    network = FakeNetwork({MAIN: UNREACHABLE, KUMI: UNREACHABLE, COFFEE: Response({"elements": FLORISTS_TV})})
    monkeypatch.setattr(osm_module.httpx, "Client", network)

    created = client.post(
        "/discoveries",
        json={"industry": "fiorista", "region": "Veneto", "province": "TV", "max_results": 50, "extended": True},
    ).json()
    execute_discovery(UUID(created["id"]), Settings())

    run = client.get(f"/discoveries/{created['id']}").json()
    assert run["status"] == "completed"
    assert run["error_message"] is None
    assert run["total_found"] == 2
    assert network.posts == [MAIN, KUMI, COFFEE]


def test_all_servers_unreachable_fails_with_clear_message_after_retries(db_session, sqlite_engine, monkeypatch):
    factory = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.db.get_session_factory", lambda: factory)
    network = FakeNetwork({})
    monkeypatch.setattr(osm_module.httpx, "Client", network)
    run = create_discovery_run(db_session, industry="fiorista", location="Provincia di Treviso, Veneto",
                               max_results=20)

    with pytest.raises(OverpassUnavailableError):
        execute_discovery(run.id, Settings(overpass_retry_attempts=2))

    db_session.expire_all()
    stored = db_session.get(DiscoveryRun, run.id)
    assert stored.status == "failed"
    assert stored.error_message.startswith("Overpass non raggiungibile")
    assert all(host in stored.error_message for host in (MAIN, KUMI, COFFEE))
    assert "Riprova ricerca" in stored.error_message
    assert stored.progress_label.startswith("Fallita")
    servers = len(overpass_endpoints(Settings()))
    assert len(network.posts) == 2 * servers  # 2 tentativi, ognuno su tutti i server


def _comuni_split_rules(group_calls: list[str]):
    comuni = Response({"elements": [
        {"type": "relation", "id": 301, "tags": {"name": "Treviso"}},
        {"type": "relation", "id": 302, "tags": {"name": "Conegliano"}},
        {"type": "relation", "id": 303, "tags": {"name": "Castelfranco Veneto"}},
    ]})

    def kumi(query: str):
        if "admin_level" in query:
            return comuni
        if "area(id:" not in query:
            return Response({"elements": [], "remark": "runtime error: Query timed out"})
        group_calls.append(query)
        ids = query.split("area(id:")[1].split(")")[0]
        if "3600000302" in ids:
            return Response({"elements": [FLORISTS_TV[1]]})
        if "3600000301" in ids:
            return Response({"elements": [FLORISTS_TV[0]]})
        return Response({"elements": []})

    return kumi


def test_comuni_split_sticks_to_the_server_that_answers(monkeypatch) -> None:
    group_calls: list[str] = []
    network = FakeNetwork({MAIN: UNREACHABLE, KUMI: _comuni_split_rules(group_calls)})
    monkeypatch.setattr(osm_module.httpx, "Client", network)
    provider = OpenStreetMapProvider(Settings(overpass_comuni_group_size=1))

    found = provider.search_businesses(_treviso_query())

    assert {item.name for item in found} == {"Fiori di Treviso", "Conegliano in Fiore"}
    assert len(group_calls) == 3
    # Query provinciale: tutti e 4 i server (kumi va in timeout, gli altri irraggiungibili).
    # Poi elenco comuni e i 3 gruppi solo su kumi: i server giù non vengono più riprovati,
    # nemmeno per confermare il gruppo senza risultati (Castelfranco).
    assert network.posts == [MAIN, KUMI, COFFEE, "lz4.overpass-api.de", KUMI, KUMI, KUMI, KUMI]


def test_network_lost_during_comuni_split_keeps_results_as_partial(monkeypatch) -> None:
    group_calls: list[str] = []
    kumi_ok = _comuni_split_rules([])

    def kumi(query: str):
        if "area(id:" not in query:
            return kumi_ok(query)
        # Il primo gruppo risponde, poi la rete cade anche verso kumi.
        if group_calls:
            raise UNREACHABLE
        group_calls.append(query)
        return Response({"elements": [FLORISTS_TV[0]]})

    network = FakeNetwork({KUMI: kumi})
    monkeypatch.setattr(osm_module.httpx, "Client", network)
    provider = OpenStreetMapProvider(Settings(overpass_comuni_group_size=1))

    found = provider.search_businesses(_treviso_query())

    assert [item.name for item in found] == ["Fiori di Treviso"]
    assert "1/3 comuni completati" in provider.last_warning
    assert "interrotta" in provider.last_warning
    assert "da cercare" in provider.last_warning


def test_nominatim_network_error_is_readable(monkeypatch) -> None:
    class Down(FakeNetwork):
        def get(self, url, params=None):
            raise UNREACHABLE

    monkeypatch.setattr(osm_module.httpx, "Client", Down({}))
    with pytest.raises(RuntimeError, match="Nominatim non raggiungibile"):
        OpenStreetMapProvider(Settings()).search_businesses(_treviso_query())


# --- POST /discoveries/{id}/retry --------------------------------------------------------


def _run(db, status: str, **fields) -> DiscoveryRun:
    run = DiscoveryRun(industry="fiorista", location="Provincia di Treviso, Veneto", max_results=20,
                       provider="openstreetmap", status=status, total_found=0, progress_percent=100,
                       error_message="[Errno 101] Network is unreachable", progress_label="Query Overpass", **fields)
    db.add(run)
    db.commit()
    return run


def test_retry_requeues_failed_run(client, db_session, monkeypatch) -> None:
    started: list = []
    monkeypatch.setattr("app.api.discovery.execute_discovery", lambda run_id: started.append(run_id))
    run = _run(db_session, "failed")

    response = client.post(f"/discoveries/{run.id}/retry")

    assert response.status_code == 202
    body = response.json()
    assert body["id"] == str(run.id)
    assert body["status"] == "queued"
    assert body["error_message"] is None
    assert body["progress_label"] == "In coda · nuovo tentativo"
    assert started == [run.id]


def test_retry_rules(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.api.discovery.execute_discovery", lambda run_id: None)
    completed = _run(db_session, "completed")
    running = _run(db_session, "running", started_at=datetime.now(UTC) - timedelta(minutes=2))
    stuck = _run(db_session, "running", started_at=datetime.now(UTC) - timedelta(hours=2))
    partial = _run(db_session, "partial")

    assert client.post(f"/discoveries/{completed.id}/retry").status_code == 409
    assert client.post(f"/discoveries/{running.id}/retry").status_code == 409
    assert client.post(f"/discoveries/{stuck.id}/retry").status_code == 202
    assert client.post(f"/discoveries/{partial.id}/retry").status_code == 202
    assert client.post("/discoveries/11111111-1111-1111-1111-111111111111/retry").status_code == 404


def test_retry_keeps_previous_results_and_counts_total(db_session, sqlite_engine, monkeypatch) -> None:
    factory = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.db.get_session_factory", lambda: factory)
    run = _run(db_session, "partial")
    known = Company(name="Fiori di Treviso", source="openstreetmap", external_id="node/11", status="discovered")
    db_session.add(known)
    db_session.flush()
    db_session.add(DiscoveryResult(discovery_run_id=run.id, company_id=known.id))
    db_session.commit()

    class Provider:
        name = "openstreetmap"
        last_warning = None

        def search_businesses(self, query, on_stage=None):
            return [
                DiscoveryCandidate(name="Fiori di Treviso", source="openstreetmap", external_id="node/11"),
                DiscoveryCandidate(name="Conegliano in Fiore", source="openstreetmap", external_id="node/12",
                                   phone="0438 1"),
            ]

    monkeypatch.setattr("app.discovery.service.get_discovery_provider", lambda settings: Provider())
    from app.discovery.service import reset_discovery_for_retry

    reset_discovery_for_retry(db_session, run.id)
    execute_discovery(run.id, Settings())

    db_session.expire_all()
    stored = db_session.get(DiscoveryRun, run.id)
    assert stored.status == "completed"
    assert stored.total_found == 2
    assert db_session.query(DiscoveryResult).filter_by(discovery_run_id=run.id).count() == 2
