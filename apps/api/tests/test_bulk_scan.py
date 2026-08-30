from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.jobs.bulk_scan import (
    create_bulk_scan,
    execute_bulk_scan,
    load_bulk_scan,
    ranked_items,
    retry_failed_items,
)
from app.models.entities import Audit, Company, DiscoveryResult, DiscoveryRun, OpportunityScore, Website


def _seed(session) -> DiscoveryRun:
    run = DiscoveryRun(
        industry="Hotel",
        location="Sicilia",
        max_results=10,
        provider="fake",
        status="completed",
        total_found=3,
    )
    session.add(run)
    session.flush()
    alpha = Company(
        name="Hotel Alpha",
        city="Palermo",
        source="fake",
        external_id="a1",
        status="discovered",
        website_url="https://alpha.test",
    )
    beta = Company(
        name="Hotel Beta",
        city="Catania",
        source="fake",
        external_id="b1",
        status="discovered",
        website_url="https://beta-fail.test",
    )
    gamma = Company(
        name="Hotel Gamma",
        city="Messina",
        source="fake",
        external_id="g1",
        status="discovered",
    )
    session.add_all([alpha, beta, gamma])
    session.flush()
    session.add(
        Website(
            company_id=alpha.id,
            url="https://alpha.test",
            normalized_url="https://alpha.test",
            domain="alpha.test",
        )
    )
    session.add(
        Website(
            company_id=beta.id,
            url="https://beta-fail.test",
            normalized_url="https://beta-fail.test",
            domain="beta-fail.test",
        )
    )
    session.add(DiscoveryResult(discovery_run_id=run.id, company_id=alpha.id))
    session.add(DiscoveryResult(discovery_run_id=run.id, company_id=beta.id))
    session.add(DiscoveryResult(discovery_run_id=run.id, company_id=gamma.id))
    session.commit()
    return run


def _fake_execute(audit_id, settings=None) -> None:
    from app.db import get_session_factory

    session = get_session_factory()()
    try:
        audit = session.get(Audit, audit_id)
        assert audit is not None
        website = session.get(Website, audit.website_id)
        if "fail" in audit.request_url:
            audit.status = "failed"
            audit.error_message = "simulated failure"
        else:
            audit.status = "completed"
            score = 88 if "alpha" in audit.request_url else 41
            session.add(
                OpportunityScore(
                    company_id=website.company_id if website else None,
                    audit_id=audit.id,
                    website_score=40,
                    business_score=50,
                    opportunity_score=score,
                    confidence=0.5,
                    priority="HIGH" if score > 70 else "MEDIUM",
                    explanation="test",
                    top_reasons=["motivo"],
                    positive_factors=["plus"],
                    negative_factors=["minus"],
                    recommended_service="Restyling sito",
                    components={},
                    formula_version="1.0.0",
                )
            )
        session.commit()
    finally:
        session.close()


def test_bulk_scan_skips_retries_and_ranks(db_session, sqlite_engine, monkeypatch) -> None:
    factory = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.db.get_session_factory", lambda: factory)
    monkeypatch.setattr("app.jobs.bulk_scan.execute_audit", _fake_execute)
    settings = Settings(bulk_scan_concurrency=1, bulk_scan_max_attempts=2)
    run = _seed(db_session)
    scan = create_bulk_scan(db_session, run.id, settings)
    db_session.expire_all()
    scan = load_bulk_scan(db_session, scan.id)
    assert scan is not None
    assert {item.status for item in scan.items} == {"pending", "skipped"}
    execute_bulk_scan(scan.id, settings)
    db_session.expire_all()

    loaded = load_bulk_scan(db_session, scan.id)
    assert loaded is not None
    by_name = {item.company.name: item for item in loaded.items}
    assert by_name["Hotel Gamma"].status == "skipped"
    assert by_name["Hotel Alpha"].status == "completed"
    assert by_name["Hotel Beta"].status == "failed"
    assert by_name["Hotel Beta"].attempts == 2
    assert loaded.status == "partial"

    ranked = ranked_items(loaded)
    assert ranked[0].company.name == "Hotel Alpha"
    assert ranked[0].audit.opportunity_score.opportunity_score == 88


def test_retry_failed_requeues(db_session, sqlite_engine, monkeypatch) -> None:
    factory = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.db.get_session_factory", lambda: factory)
    monkeypatch.setattr("app.jobs.bulk_scan.execute_audit", _fake_execute)
    settings = Settings(bulk_scan_concurrency=1, bulk_scan_max_attempts=1)
    run = _seed(db_session)
    scan = create_bulk_scan(db_session, run.id, settings)
    execute_bulk_scan(scan.id, settings)
    db_session.expire_all()
    retried = retry_failed_items(db_session, scan.id)
    assert retried.status == "queued"
    failed_or_pending = [item for item in retried.items if item.company.name == "Hotel Beta"]
    assert failed_or_pending[0].status == "pending"
    assert failed_or_pending[0].attempts == 0


def test_bulk_scan_api(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.api.bulk_scans.execute_bulk_scan", lambda scan_id: None)
    run = _seed(db_session)
    created = client.post(f"/discoveries/{run.id}/scans")
    assert created.status_code == 202
    payload = created.json()
    assert payload["progress"]["skipped"] == 1
    assert payload["progress"]["pending"] == 2
    fetched = client.get(f"/bulk-scans/{payload['id']}")
    assert fetched.status_code == 200
    discovery = client.get(f"/discoveries/{run.id}")
    assert discovery.json()["latest_scan_id"] == payload["id"]
