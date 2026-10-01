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
