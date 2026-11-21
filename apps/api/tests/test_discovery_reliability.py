"""Discovery affidabile: tentativi su timeout/sovraccarico, limite richieste Overpass, ricerche bloccate."""

from __future__ import annotations

import threading
import time as real_time
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy.orm import sessionmaker

import app.discovery.osm as osm_module
from app.config import Settings
from app.discovery.osm import OpenStreetMapProvider, overpass_endpoints
from app.discovery.service import create_discovery_run, execute_discovery, fail_stale_runs
from app.models.entities import DiscoveryRun

ENDPOINTS = len(overpass_endpoints(Settings()))
BAKERIES = [
    {"type": "node", "id": 501, "lat": 45.522, "lon": 9.592,
     "tags": {"name": "Panificio Treviglio", "shop": "bakery", "addr:city": "Treviglio", "phone": "0363 1"}},
    {"type": "node", "id": 502, "lat": 45.519, "lon": 9.588,
     "tags": {"name": "Forno del Borgo", "shop": "bakery", "addr:city": "Treviglio", "website": "https://forno.it"}},
]


class Response:
    def __init__(self, payload, status_code: int = 200, text: str = "{}") -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


class Overpass:
    """Nominatim risponde; Overpass fallisce per i primi `failures` tentativi completi, poi risponde."""

    def __init__(self, failures: int, failure: str) -> None:
        self.failures = failures
        self.failure = failure
        self.posts = 0

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, params=None):
        return Response([{"osm_type": "relation", "osm_id": 44000, "boundingbox": ["45.49", "45.55", "9.55", "9.63"],
                          "display_name": "Treviglio, Bergamo, Lombardia, Italia"}])

    def post(self, url, data=None):
        self.posts += 1
        if self.posts <= self.failures * ENDPOINTS:  # un tentativo = tutti i server provati
            if self.failure == "timeout":
                return Response({"elements": [], "remark": "runtime error: Query timed out in \"query\""})
            if self.failure == "busy":
                return Response({}, status_code=429, text="rate_limited")
            raise httpx.ReadTimeout("timeout")
        return Response({"elements": BAKERIES})


@pytest.fixture
def no_sleep(monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr(osm_module.time, "sleep", lambda seconds: waits.append(seconds))
    return waits


@pytest.fixture
def factory(sqlite_engine, monkeypatch):
    made = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.db.get_session_factory", lambda: made)
    return made


@pytest.mark.parametrize("failure", ["timeout", "busy", "http-timeout"])
def test_city_search_completes_after_two_failed_attempts(db_session, factory, monkeypatch, no_sleep, failure):
    """Accettazione: Overpass simulato va in timeout 2 volte, poi risponde → completed."""
    overpass = Overpass(failures=2, failure=failure)
    monkeypatch.setattr(osm_module.httpx, "Client", overpass)
    run = create_discovery_run(db_session, industry="panificio", location="Treviglio, Bergamo, Lombardia",
                               max_results=20, extended=True)

    execute_discovery(run.id, Settings())

    db_session.expire_all()
    stored = db_session.get(DiscoveryRun, run.id)
    assert stored.status == "completed", stored.error_message
    assert stored.total_found == 2
    assert overpass.posts == 2 * ENDPOINTS + 1  # 2 giri falliti su tutti i server, poi il primo risponde
    assert no_sleep == [5.0, 10.0]  # attesa crescente fra i 3 tentativi


def test_city_search_fails_with_readable_reason_after_three_attempts(db_session, factory, monkeypatch, no_sleep):
    monkeypatch.setattr(osm_module.httpx, "Client", Overpass(failures=99, failure="busy"))
    run = create_discovery_run(db_session, industry="falegname", location="Oderzo, Treviso, Veneto", max_results=20)

    with pytest.raises(RuntimeError):
        execute_discovery(run.id, Settings())

    db_session.expire_all()
    stored = db_session.get(DiscoveryRun, run.id)
    assert stored.status == "failed"
    assert "sovraccarico" in stored.error_message
    assert stored.progress_label.startswith("Fallita")
    assert len(no_sleep) == 2


def test_overpass_requests_are_limited_across_concurrent_discoveries(monkeypatch) -> None:
    active = 0
    peak = 0
    lock = threading.Lock()

    class Slow:
        def __call__(self, *args, **kwargs):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, data=None):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            real_time.sleep(0.05)
            with lock:
                active -= 1
            return Response({"elements": BAKERIES})

    monkeypatch.setattr(osm_module.httpx, "Client", Slow())
    provider = OpenStreetMapProvider(Settings(overpass_max_concurrency=2))
    threads = [threading.Thread(target=provider._post_overpass, args=("[out:json];", 20)) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert peak == 2


# --- ricerche bloccate -------------------------------------------------------------------


def _run(db, status: str, **fields) -> DiscoveryRun:
    run = DiscoveryRun(industry="panificio", location="Treviglio, Bergamo, Lombardia", max_results=20,
                       provider="openstreetmap", status=status, total_found=0, progress_percent=40,
                       progress_label="Query Overpass", **fields)
    db.add(run)
    db.commit()
    return run


def test_stuck_running_run_becomes_failed_with_reason(client, db_session, monkeypatch) -> None:
    """Accettazione: una ricerca bloccata in "running" diventa "failed" con motivo leggibile."""
    monkeypatch.setattr("app.api.discovery.execute_discovery", lambda run_id: None)
    hours_ago = datetime.now(UTC) - timedelta(hours=3)
    stuck = _run(db_session, "running", started_at=hours_ago, heartbeat_at=hours_ago)

    body = client.get(f"/discoveries/{stuck.id}").json()

    assert body["status"] == "failed"
    assert "nessun avanzamento da oltre 20 minuti" in body["error_message"]
    assert "Query Overpass" in body["error_message"]
    assert "Riprova ricerca" in body["error_message"]
    assert body["progress_label"] == "Fallita · interrotta"
    assert body["completed_at"] is not None
    # Dopo il passaggio a failed si può rilanciare.
    assert client.post(f"/discoveries/{stuck.id}/retry").status_code == 202


def test_live_long_run_and_recent_queue_are_left_alone(db_session) -> None:
    now = datetime.now(UTC)
    # Avviata da un'ora ma con avanzamento 2 minuti fa (es. ricerca per comuni): resta viva.
    alive = _run(db_session, "running", started_at=now - timedelta(hours=1), heartbeat_at=now - timedelta(minutes=2))
    queued_old = _run(db_session, "queued", created_at=now - timedelta(hours=2))
    queued_new = _run(db_session, "queued", created_at=now - timedelta(minutes=1))

    assert fail_stale_runs(db_session) == 1
    db_session.expire_all()
    assert db_session.get(DiscoveryRun, alive.id).status == "running"
    assert db_session.get(DiscoveryRun, queued_old.id).status == "failed"
    assert db_session.get(DiscoveryRun, queued_new.id).status == "queued"


def test_list_endpoint_also_closes_stuck_runs(client, db_session) -> None:
    stuck = _run(db_session, "running", started_at=datetime.now(UTC) - timedelta(hours=5))
    rows = {row["id"]: row for row in client.get("/discoveries").json()}
    assert rows[str(stuck.id)]["status"] == "failed"


def test_progress_updates_heartbeat(db_session, factory, monkeypatch, no_sleep) -> None:
    monkeypatch.setattr(osm_module.httpx, "Client", Overpass(failures=0, failure="timeout"))
    run = create_discovery_run(db_session, industry="panificio", location="Treviglio, Bergamo, Lombardia",
                               max_results=20)
    execute_discovery(UUID(str(run.id)), Settings())
    db_session.expire_all()
    assert db_session.get(DiscoveryRun, run.id).heartbeat_at is not None
