from sqlalchemy import func, select

from app.models.entities import (
    Audit,
    Company,
    DiscoveryResult,
    DiscoveryRun,
    Opportunity,
    OpportunityNote,
    Proposal,
    Website,
)
from app.services.crm_service import ensure_opportunity


def _proposal(**kw) -> Proposal:
    return Proposal(
        kind="refactor", source="deterministic", prompt_version="v1", summary="s", priority_problems=[],
        recommended_service="r", strategy="s", email_subject="o", email_body="b", brief="b",
        range_min=1, range_max=2, currency="EUR", range_note="n", **kw,
    )


def _company_with_everything(db, name: str, status: str = "completed") -> Company:
    company = Company(name=name, source="fake", external_id=name, status="discovered")
    db.add(company)
    db.flush()
    website = Website(company_id=company.id, url=f"https://{name}.it", normalized_url=f"https://{name}.it/", domain=f"{name}.it")
    db.add(website)
    db.flush()
    audit = Audit(website_id=website.id, status=status, request_url=website.url, scanner_version="t", progress_percent=100)
    db.add(audit)
    db.flush()
    db.add(_proposal(audit_id=audit.id, company_id=company.id))
    opportunity = ensure_opportunity(db, company)
    db.add(OpportunityNote(opportunity_id=opportunity.id, body="nota"))
    db.commit()
    return company


def _count(db, model) -> int:
    return db.execute(select(func.count()).select_from(model)).scalar_one()


def test_delete_company_removes_everything_linked(client, db_session) -> None:
    keep = _company_with_everything(db_session, "tieni")
    gone = _company_with_everything(db_session, "via")
    keep_id = keep.id
    assert client.delete(f"/companies/{gone.id}").status_code == 204
    assert client.get(f"/companies/{gone.id}").status_code == 404
    for model in (Company, Website, Audit, Proposal, Opportunity, OpportunityNote):
        assert _count(db_session, model) == 1, model
    assert db_session.get(Company, keep_id) is not None


def test_delete_audit_keeps_company_and_drops_orphan_website(client, db_session) -> None:
    company = _company_with_everything(db_session, "acme")
    audit = db_session.execute(select(Audit)).scalar_one()
    assert client.delete(f"/audits/{audit.id}").status_code == 204
    assert _count(db_session, Audit) == 0 and _count(db_session, Proposal) == 0
    assert db_session.get(Company, company.id) is not None
    assert _count(db_session, Website) == 1  # collegato all'azienda: resta


def test_running_audit_cannot_be_deleted(client, db_session) -> None:
    _company_with_everything(db_session, "busy", status="running")
    audit = db_session.execute(select(Audit)).scalar_one()
    assert client.delete(f"/audits/{audit.id}").status_code == 409
    assert _count(db_session, Audit) == 1


def test_delete_discovery_removes_exclusive_companies_only(client, db_session) -> None:
    solo = _company_with_everything(db_session, "solo")
    shared = _company_with_everything(db_session, "condivisa")
    solo_id, shared_id = solo.id, shared.id
    run1 = DiscoveryRun(industry="bar", location="Roma", status="completed", max_results=10, provider="openstreetmap")
    run2 = DiscoveryRun(industry="bar", location="Roma", status="completed", max_results=10, provider="openstreetmap")
    db_session.add_all([run1, run2])
    db_session.flush()
    db_session.add_all(
        [
            DiscoveryResult(discovery_run_id=run1.id, company_id=solo.id),
            DiscoveryResult(discovery_run_id=run1.id, company_id=shared.id),
            DiscoveryResult(discovery_run_id=run2.id, company_id=shared.id),
        ]
    )
    db_session.commit()
    assert client.delete(f"/discoveries/{run1.id}").status_code == 204
    assert db_session.get(Company, solo_id) is None
    assert db_session.get(Company, shared_id) is not None
    assert _count(db_session, DiscoveryRun) == 1


def test_delete_all_requires_confirm_then_wipes_pipeline(client, db_session) -> None:
    _company_with_everything(db_session, "a")
    _company_with_everything(db_session, "b")
    assert client.delete("/companies").status_code == 400
    assert _count(db_session, Company) == 2
    body = client.delete("/companies?confirm=true").json()
    assert body["deleted"] == 2
    for model in (Company, Website, Audit, Proposal, Opportunity, OpportunityNote):
        assert _count(db_session, model) == 0, model


def test_delete_all_audits_and_discoveries(client, db_session) -> None:
    _company_with_everything(db_session, "x")
    assert client.delete("/audits?confirm=true").json()["deleted"] == 1
    assert _count(db_session, Audit) == 0 and _count(db_session, Company) == 1
    assert client.delete("/discoveries?confirm=true").json()["deleted"] == 0
