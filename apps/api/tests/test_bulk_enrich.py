from uuid import UUID

from sqlalchemy.orm import sessionmaker

import app.db as db_module
import app.jobs.bulk_enrich as job_module
from app.discovery.service import DiscoveryServiceError
from app.models.entities import Company


def _company(name: str, **kw) -> Company:
    return Company(name=name, source="fake", external_id=name, status="discovered", **kw)


def test_candidates_count_only_companies_that_can_be_completed(client, db_session) -> None:
    db_session.add_all(
        [
            _company("senza citta", latitude=1.0, longitude=2.0),
            _company("senza coordinate"),
            _company("completa", city="Roma", website_url="https://a.it", latitude=1.0, longitude=2.0),
        ]
    )
    db_session.commit()
    body = client.get("/enrichment/candidates").json()
    assert body == {"missing_city": 1, "missing_website": 2}


def test_run_job_counts_updated_not_found_and_failed(client, db_session, sqlite_engine, monkeypatch) -> None:
    db_session.add_all([_company(f"c{i}", latitude=1.0, longitude=2.0) for i in range(3)])
    db_session.commit()
    monkeypatch.setattr(db_module, "get_session_factory", lambda: sessionmaker(bind=sqlite_engine))
    monkeypatch.setattr(job_module.time, "sleep", lambda _s: None)

    outcomes = iter([None, DiscoveryServiceError("no", 404), DiscoveryServiceError("boom", 502)])

    def fake_resolve(session, company, settings):
        outcome = next(outcomes)
        if outcome:
            raise outcome
        return company

    monkeypatch.setattr(job_module, "resolve_company_location", fake_resolve)
    job, created = job_module.start_job(db_session, "city")
    assert created and job.total == 3
    job_module.run_job(job.id)
    assert (job.status, job.processed, job.updated, job.not_found, job.failed) == ("completed", 3, 1, 1, 1)


def test_run_job_stops_when_key_is_missing(client, db_session, sqlite_engine, monkeypatch) -> None:
    db_session.add_all([_company(f"p{i}") for i in range(4)])
    db_session.commit()
    monkeypatch.setattr(db_module, "get_session_factory", lambda: sessionmaker(bind=sqlite_engine))
    monkeypatch.setattr(job_module.time, "sleep", lambda _s: None)
    job, _ = job_module.start_job(db_session, "places")
    job_module.run_job(job.id)  # nessuna chiave salvata -> 422 al primo tentativo
    assert job.status == "failed" and job.processed == 1
    assert "Google Places" in (job.last_error or "")


def test_only_one_running_job_per_kind(client, db_session) -> None:
    db_session.add(_company("solo", latitude=1.0, longitude=2.0))
    db_session.commit()
    first, created = job_module.start_job(db_session, "city")
    second, created_again = job_module.start_job(db_session, "city")
    assert created and not created_again and first.id == second.id
    first.status = "completed"


def test_selection_never_includes_other_companies(client, db_session) -> None:
    selected = _company("selected")
    outside = _company("outside")
    with_site = _company("with-site", website_url="https://example.com")
    db_session.add_all([selected, outside, with_site])
    db_session.commit()
    job, _ = job_module.start_job(db_session, "places", [selected.id, with_site.id])
    assert job.company_ids == [selected.id]
    job.status = "completed"


def test_empty_selection_does_not_start_global_job(client, db_session) -> None:
    db_session.add(_company("outside"))
    db_session.commit()
    response = client.post("/enrichment/places", json={"company_ids": []})
    assert response.status_code == 409


def test_selected_endpoint_enriches_only_requested_companies(client, db_session, monkeypatch) -> None:
    selected = _company("selected")
    outside = _company("outside")
    db_session.add_all([selected, outside])
    db_session.commit()

    def complete_job(job_id):
        job_module.get_job(job_id).status = "completed"

    monkeypatch.setattr("app.api.bulk_enrich.run_job", complete_job)
    response = client.post(
        "/enrichment/selected/places",
        json={"company_ids": [str(selected.id)]},
    )

    assert response.status_code == 202
    assert response.json()["total"] == 1
    assert job_module.get_job(UUID(response.json()["id"])).company_ids == [selected.id]


def test_running_different_selection_is_rejected(client, db_session) -> None:
    import pytest
    first = _company("first")
    second = _company("second")
    db_session.add_all([first, second])
    db_session.commit()
    job, _ = job_module.start_job(db_session, "places", [first.id])
    try:
        with pytest.raises(job_module.BulkEnrichError, match="già in corso"):
            job_module.start_job(db_session, "places", [second.id])
    finally:
        job.status = "completed"


def test_analysis_only_runs_selected_websites(client, db_session, sqlite_engine, monkeypatch) -> None:
    selected = _company("selected-site", website_url="https://example.com")
    outside = _company("outside-site", website_url="https://example.org")
    missing = _company("missing-site")
    db_session.add_all([selected, outside, missing])
    db_session.commit()
    monkeypatch.setattr(db_module, "get_session_factory", lambda: sessionmaker(bind=sqlite_engine))
    calls = []
    monkeypatch.setattr(job_module, "execute_audit", lambda audit_id, settings: calls.append(audit_id))
    job, _ = job_module.start_job(db_session, "analysis", [selected.id, missing.id])
    assert job.company_ids == [selected.id]
    job_module.run_job(job.id)
    assert len(calls) == 1
    assert job.status == "completed" and job.updated == 1


def test_analysis_requires_selection(client) -> None:
    assert client.post("/enrichment/analysis").status_code == 422


def test_cancelled_job_does_not_start_next_company(client, db_session, sqlite_engine, monkeypatch) -> None:
    first = _company("first", latitude=1.0, longitude=2.0)
    second = _company("second", latitude=1.0, longitude=2.0)
    db_session.add_all([first, second])
    db_session.commit()
    monkeypatch.setattr(db_module, "get_session_factory", lambda: sessionmaker(bind=sqlite_engine))
    monkeypatch.setattr(job_module.time, "sleep", lambda _s: None)
    calls = []
    job, _ = job_module.start_job(db_session, "city", [first.id, second.id])
    expected_first = job.company_ids[0]

    def cancel_after_first(session, company, settings):
        calls.append(company.id)
        job_module.cancel_job(job.id)
        return company

    monkeypatch.setattr(job_module, "resolve_company_location", cancel_after_first)
    job_module.run_job(job.id)

    assert calls == [expected_first]
    assert job.status == "cancelled"
    assert job.processed == 1
