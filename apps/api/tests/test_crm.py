from datetime import UTC, datetime, timedelta

from app.discovery.service import _run_discovery, create_discovery_run
from app.discovery.types import DiscoveryCandidate
from app.models.entities import Company, Opportunity, OpportunityScore
from app.schemas.crm import CRM_STATUSES
from app.services.crm_service import (
    add_activity,
    add_note,
    add_tag,
    complete_activity,
    dashboard,
    ensure_opportunity,
    list_agenda,
    list_agenda_history,
    list_opportunities,
    mark_analyzed_if_discovered,
    reopen_activity,
    delete_scheduled_activity,
    remove_tag,
    update_opportunity,
)


def _company(session, name="Hotel Sole", city="Palermo", category="hotel") -> Company:
    company = Company(
        name=name,
        city=city,
        category=category,
        source="fake",
        external_id=name.lower().replace(" ", "-"),
        status="discovered",
        website_url=f"https://{name.lower().replace(' ', '')}.test",
    )
    session.add(company)
    session.flush()
    ensure_opportunity(session, company)
    session.commit()
    return company


def test_pipeline_statuses_match_docs() -> None:
    assert CRM_STATUSES == (
        "discovered",
        "analyzed",
        "qualified",
        "shortlisted",
        "to_contact",
        "contacted",
        "replied",
        "meeting",
        "proposal",
        "won",
        "lost",
    )


def test_discovery_creates_opportunity(db_session, monkeypatch) -> None:
    class Fake:
        name = "fake"

        def search_businesses(self, query):
            return [
                DiscoveryCandidate(
                    name="Hotel Sole",
                    city="Palermo",
                    category="hotel",
                    website_url="https://hotelsole.it",
                    source="fake",
                    external_id="1",
                )
            ]

    monkeypatch.setattr("app.discovery.service.get_discovery_provider", lambda settings: Fake())
    from app.config import Settings

    run = create_discovery_run(db_session, industry="Hotel", location="Sicilia", max_results=10)
    _run_discovery(db_session, run, Settings())
    db_session.commit()
    company = db_session.query(Company).one()
    opportunity = db_session.query(Opportunity).filter_by(company_id=company.id).one()
    assert opportunity.status == "discovered"
    assert opportunity.is_favorite is False


def test_status_note_tag_favorite_and_activity(db_session) -> None:
    company = _company(db_session)
    opportunity = db_session.query(Opportunity).filter_by(company_id=company.id).one()

    updated = update_opportunity(db_session, opportunity.id, status="qualified", is_favorite=True)
    assert updated.status == "qualified"
    assert updated.is_favorite is True
    assert any(item.type == "status_change" for item in updated.activities)

    with_note = add_note(db_session, opportunity.id, "  Vale una chiamata.  ")
    assert with_note.notes[0].body == "Vale una chiamata."

    with_tag = add_tag(db_session, opportunity.id, " Shortlist ")
    assert [link.tag.name for link in with_tag.tag_links] == ["shortlist"]

    with_activity = add_activity(
        db_session,
        opportunity.id,
        activity_type="call",
        note="Lasciato messaggio",
        occurred_at=datetime.now(UTC),
    )
    assert any(item.type == "call" for item in with_activity.activities)

    removed = remove_tag(db_session, opportunity.id, with_tag.tag_links[0].tag_id)
    assert removed.tag_links == []


def test_list_filters_and_dashboard(db_session) -> None:
    from app.models.entities import Audit, Website

    alpha = _company(db_session, name="Hotel Alpha", city="Palermo")
    beta = _company(db_session, name="Hotel Beta", city="Catania")
    _company(db_session, name="Ristorante Gamma", city="Palermo", category="restaurant")

    alpha_opp = db_session.query(Opportunity).filter_by(company_id=alpha.id).one()
    update_opportunity(db_session, alpha_opp.id, status="shortlisted", is_favorite=True)
    mark_analyzed_if_discovered(db_session, beta.id)
    db_session.commit()

    website = Website(
        company_id=alpha.id,
        url="https://alpha.test",
        normalized_url="https://alpha.test",
        domain="alpha.test",
    )
    db_session.add(website)
    db_session.flush()
    audit = Audit(
        website_id=website.id,
        status="completed",
        request_url="https://alpha.test",
        scanner_version="test",
    )
    db_session.add(audit)
    db_session.flush()
    db_session.add(
        OpportunityScore(
            company_id=alpha.id,
            audit_id=audit.id,
            website_score=40,
            business_score=70,
            opportunity_score=82,
            confidence=0.7,
            priority="VERY_HIGH",
            explanation="forte",
            top_reasons=["sito debole"],
            positive_factors=["hotel"],
            negative_factors=[],
            recommended_service="redesign",
            formula_version="1.0.0",
        )
    )
    db_session.commit()

    add_tag(db_session, alpha_opp.id, "hot")

    assert [item.company.name for item in list_opportunities(db_session, city="Palermo")] == [
        "Hotel Alpha",
        "Ristorante Gamma",
    ]
    assert [item.company.name for item in list_opportunities(db_session, shortlist=True)] == ["Hotel Alpha"]
    assert [item.company.name for item in list_opportunities(db_session, min_score=80)] == ["Hotel Alpha"]
    assert [item.company.name for item in list_opportunities(db_session, priority="VERY_HIGH")] == ["Hotel Alpha"]
    assert [item.company.name for item in list_opportunities(db_session, tag="hot")] == ["Hotel Alpha"]
    assert [item.company.name for item in list_opportunities(db_session, query="beta")] == ["Hotel Beta"]
    assert list_opportunities(db_session, status="analyzed")[0].company.name == "Hotel Beta"

    stats = dashboard(db_session)
    assert stats["total"] == 3
    assert stats["favorites"] == 1
    assert stats["shortlisted"] == 1
    assert stats["high_priority"] == 1
    assert stats["counts"]["shortlisted"] == 1
    assert stats["counts"]["analyzed"] == 1
    assert stats["counts"]["discovered"] == 1


def test_segment_filter_and_growth_ranking(db_session) -> None:
    from app.models.entities import GrowthScore

    with_site = _company(db_session, name="Hotel Con Sito", city="Palermo")
    no_site = Company(
        name="Trattoria Senza Sito",
        city="Palermo",
        category="ristorante",
        source="fake",
        external_id="no-site",
        status="discovered",
        website_url=None,
    )
    db_session.add(no_site)
    db_session.flush()
    ensure_opportunity(db_session, no_site)
    db_session.add(
        GrowthScore(
            company_id=no_site.id,
            score=88,
            priority="VERY_HIGH",
            confidence=0.6,
            explanation="Growth Potential 88/100 (VERY_HIGH).",
            top_reasons=["gap competitivo"],
            positive_factors=[],
            negative_factors=[],
            recommended_service="Creazione sito vetrina con prenotazione online",
            peer_sample_size=5,
            formula_version="1.0.0",
        )
    )
    db_session.commit()

    refactor_only = list_opportunities(db_session, segment="refactor")
    assert [item.company.name for item in refactor_only] == ["Hotel Con Sito"]

    greenfield_only = list_opportunities(db_session, segment="greenfield")
    assert [item.company.name for item in greenfield_only] == ["Trattoria Senza Sito"]

    all_ranked = list_opportunities(db_session, min_score=80)
    assert [item.company.name for item in all_ranked] == ["Trattoria Senza Sito"]

    everyone = list_opportunities(db_session)
    assert [item.company.name for item in everyone] == ["Trattoria Senza Sito", with_site.name]

    stats = dashboard(db_session)
    assert stats["high_priority"] == 1


def test_contactable_filter_hides_companies_with_no_reach(db_session) -> None:
    _company(db_session, name="Hotel Con Sito", city="Palermo")
    unreachable = Company(
        name="Nessun Contatto",
        city="Palermo",
        source="fake",
        external_id="unreachable",
        status="discovered",
    )
    db_session.add(unreachable)
    db_session.flush()
    ensure_opportunity(db_session, unreachable)
    db_session.commit()

    everyone = list_opportunities(db_session)
    assert {item.company.name for item in everyone} == {"Hotel Con Sito", "Nessun Contatto"}

    only_reachable = list_opportunities(db_session, contactable=True)
    assert [item.company.name for item in only_reachable] == ["Hotel Con Sito"]


def test_crm_api_roundtrip(client, db_session) -> None:
    company = _company(db_session)
    listed = client.get("/opportunities")
    assert listed.status_code == 200
    assert listed.json()[0]["company_name"] == "Hotel Sole"
    opportunity_id = listed.json()[0]["id"]

    patched = client.patch(
        f"/opportunities/{opportunity_id}",
        json={"status": "to_contact", "is_favorite": True},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "to_contact"
    assert patched.json()["is_favorite"] is True

    noted = client.post(f"/opportunities/{opportunity_id}/notes", json={"body": "Chiamare lunedì"})
    assert noted.status_code == 200
    assert noted.json()["notes"][0]["body"] == "Chiamare lunedì"

    tagged = client.post(f"/opportunities/{opportunity_id}/tags", json={"name": "Priorità"})
    assert tagged.json()["tags"][0]["name"] == "priorità"

    activity = client.post(
        f"/opportunities/{opportunity_id}/activities",
        json={"type": "email", "note": "Inviata presentazione"},
    )
    assert any(item["type"] == "email" for item in activity.json()["activities"])

    dash = client.get("/opportunities/dashboard")
    assert dash.status_code == 200
    assert dash.json()["favorites"] == 1
    assert dash.json()["counts"]["to_contact"] == 1

    by_company = client.get(f"/companies/{company.id}/opportunity")
    assert by_company.status_code == 200
    assert by_company.json()["id"] == opportunity_id

    bad = client.patch(f"/opportunities/{opportunity_id}", json={"status": "unknown"})
    assert bad.status_code == 422


def test_scheduled_activity_agenda_and_complete(db_session) -> None:
    company = _company(db_session)
    opportunity = db_session.query(Opportunity).filter_by(company_id=company.id).one()
    due = datetime.now(UTC) + timedelta(days=2)
    overdue = datetime.now(UTC) - timedelta(days=1)

    scheduled = add_activity(
        db_session,
        opportunity.id,
        activity_type="call",
        note="Richiamare",
        occurred_at=None,
        due_at=due,
    )
    pending = [item for item in scheduled.activities if item.due_at and not item.completed_at]
    assert len(pending) == 1
    assert pending[0].occurred_at is None

    add_activity(
        db_session,
        opportunity.id,
        activity_type="meeting",
        note="Scaduto",
        occurred_at=None,
        due_at=overdue,
    )

    items = list_agenda(
        db_session,
        from_dt=datetime.now(UTC),
        to_dt=due + timedelta(days=1),
        include_overdue=True,
    )
    assert len(items) == 2

    completed = complete_activity(db_session, pending[0].id)
    assert completed.completed_at is not None
    assert completed.occurred_at is not None

    history = list_agenda_history(db_session)
    assert len(history) == 1
    assert history[0].note == "Richiamare"

    restored = reopen_activity(db_session, completed.id)
    assert restored.completed_at is None
    assert restored.occurred_at is None
    assert list_agenda_history(db_session) == []

    remaining = list_agenda(db_session)
    assert len(remaining) == 2
    assert any(item.note == "Richiamare" for item in remaining)
    assert any(item.note == "Scaduto" for item in remaining)


def test_agenda_api(client, db_session) -> None:
    company = _company(db_session, name="Bar Blu")
    opportunity = db_session.query(Opportunity).filter_by(company_id=company.id).one()
    due = (datetime.now(UTC) + timedelta(hours=3)).isoformat().replace("+00:00", "Z")

    created = client.post(
        f"/opportunities/{opportunity.id}/activities",
        json={"type": "call", "note": "Follow-up", "due_at": due},
    )
    assert created.status_code == 200
    activity = next(item for item in created.json()["activities"] if item["due_at"])
    assert activity["occurred_at"] is None

    agenda = client.get("/agenda")
    assert agenda.status_code == 200
    assert any(item["company_name"] == "Bar Blu" for item in agenda.json())

    done = client.post(f"/activities/{activity['id']}/complete")
    assert done.status_code == 200
    assert done.json()["completed_at"] is not None

    history = client.get("/agenda/history")
    assert history.status_code == 200
    assert any(item["company_name"] == "Bar Blu" for item in history.json())

    reopened = client.post(f"/activities/{activity['id']}/reopen")
    assert reopened.status_code == 200
    assert reopened.json()["completed_at"] is None
    assert reopened.json()["occurred_at"] is None

    agenda_again = client.get("/agenda")
    assert any(item["company_name"] == "Bar Blu" for item in agenda_again.json())
    assert not any(item["company_name"] == "Bar Blu" for item in client.get("/agenda/history").json())

    deleted = client.delete(f"/activities/{activity['id']}")
    assert deleted.status_code == 204
    assert not any(item["company_name"] == "Bar Blu" for item in client.get("/agenda").json())
