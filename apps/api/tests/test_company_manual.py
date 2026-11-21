import socket
import threading
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.jobs.bulk_enrich import _JOBS
from app.models import Base
from app.models.entities import (
    Activity,
    Audit,
    BulkScan,
    Company,
    DiscoveryRun,
    GrowthScore,
    Opportunity,
    OpportunityNote,
    Website,
)
from app.schemas.company_manual import ManualCompanyCreate
from app.services.company_manual import create_manual_company
from app.services.crm_service import add_note, add_tag, ensure_opportunity, update_opportunity


def _forbid_external(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args, **_kwargs):
        raise AssertionError("chiamata esterna non consentita")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr("app.services.audit_service.create_audit", fail)
    monkeypatch.setattr("app.services.audit_service.execute_audit", fail)
    monkeypatch.setattr("app.discovery.service.execute_discovery", fail)
    monkeypatch.setattr("app.discovery.service.enrich_company_from_places", fail)
    monkeypatch.setattr("app.discovery.service.resolve_company_location", fail)
    monkeypatch.setattr("app.ai.service.analyze_audit", fail)


def _assert_quiet(db_session) -> None:
    assert db_session.query(Audit).count() == 0
    assert db_session.query(BulkScan).count() == 0
    assert db_session.query(DiscoveryRun).count() == 0
    assert db_session.query(GrowthScore).count() == 0
    assert _JOBS == {}


def test_create_with_and_without_website(client, db_session, monkeypatch) -> None:
    _forbid_external(monkeypatch)
    created = client.post(
        "/companies",
        json={
            "name": "Bar Rossi",
            "website_url": "WWW.BarRossi.test/menu/",
            "email": "Ciao@BarRossi.test",
            "phone": "+39 091 123 456",
            "category": "bar",
            "city": "Palermo",
            "province": "Palermo",
            "region": "Sicilia",
            "source": "contatto",
            "status": "to_contact",
            "notes": ["Prima nota", "Prima nota"],
            "tags": ["Lotto"],
            "social_links": [{"label": "Instagram", "url": "@barrossi"}],
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["outcome"] == "created"
    assert body["status"] == "to_contact"
    assert body["company"]["website_url"] == "https://www.barrossi.test/menu"
    assert body["company"]["email"] == "ciao@barrossi.test"
    assert body["company"]["province"] == "Palermo"
    assert body["company"]["social_links"][0]["url"] == "https://instagram.com/barrossi"
    company = db_session.get(Company, UUID(body["company_id"]))
    opportunity = db_session.query(Opportunity).filter_by(company_id=company.id).one()
    assert str(opportunity.id) == body["opportunity_id"]
    assert opportunity.status == "to_contact"
    assert db_session.query(Website).filter_by(company_id=company.id).count() == 1
    assert company.places_checked_at is None
    assert [note.body for note in opportunity.notes] == ["Prima nota"]

    bare = client.post("/companies", json={"name": "Studio Neri"})
    assert bare.status_code == 201
    bare_body = bare.json()
    assert bare_body["company"]["website_url"] is None
    assert bare_body["company"]["email"] is None
    assert bare_body["status"] == "discovered"
    assert db_session.query(Website).filter_by(company_id=UUID(bare_body["company_id"])).count() == 0
    _assert_quiet(db_session)


def test_repeat_is_idempotent_and_conflicts_are_not_merged(client, db_session, monkeypatch) -> None:
    _forbid_external(monkeypatch)
    payload = {
        "name": "Bar Rossi",
        "city": "Palermo",
        "website_url": "https://barrossi.test",
        "email": "sala@barrossi.test",
        "phone": "+39 091 000111",
        "social_links": [{"label": "Instagram", "url": "https://instagram.com/barrossi"}],
    }
    first = client.post("/companies", json=payload)
    assert first.status_code == 201
    company_id = first.json()["company_id"]

    # Stesso dominio/email/Instagram: 409 con l'id esistente, nessuna seconda scheda.
    again = client.post("/companies", json=payload)
    assert again.status_code == 409
    assert again.json()["outcome"] == "duplicate"
    assert again.json()["company_id"] == company_id
    assert set(again.json()["candidates"][0]["reasons"]) == {
        "stesso dominio del sito", "email", "stesso profilo Instagram",
    }
    assert db_session.query(Company).filter_by(name="Bar Rossi").count() == 1
    # Con allow_duplicates vale la deduplica normale (ADR-022): la scheda esistente si riapre.
    reopened = client.post("/companies", json={**payload, "allow_duplicates": True})
    assert reopened.status_code == 200
    assert reopened.json()["outcome"] == "existing"
    assert reopened.json()["company_id"] == company_id

    same_name_other_city = client.post(
        "/companies",
        json={"name": "Bar Rossi", "city": "Roma", "website_url": "https://barrossi-roma.test"},
    )
    assert same_name_other_city.status_code == 201
    assert db_session.query(Company).filter_by(name="Bar Rossi").count() == 2

    shared_domain = client.post(
        "/companies",
        json={"name": "Bar Rossi", "city": "Catania", "website_url": "https://barrossi.test/catania"},
    )
    assert shared_domain.status_code == 409
    assert shared_domain.json()["outcome"] == "duplicate"
    assert shared_domain.json()["company_id"] == company_id
    # Sede diversa sullo stesso dominio: va chiesta esplicitamente.
    branch = client.post(
        "/companies",
        json={"name": "Bar Rossi", "city": "Catania", "website_url": "https://barrossi.test/catania",
              "allow_duplicates": True},
    )
    assert branch.status_code == 201

    shared_site = client.post(
        "/companies",
        json={"name": "Bar Rossi", "city": "Messina", "website_url": "https://barrossi.test", "allow_duplicates": True},
    )
    assert shared_site.status_code == 409
    assert shared_site.json()["outcome"] == "conflict"
    assert shared_site.json()["company_id"] is None
    assert any(item["company_id"] == company_id for item in shared_site.json()["candidates"])
    assert db_session.query(Company).filter_by(city="Messina").count() == 0

    shared_phone = client.post(
        "/companies",
        json={"name": "Altro Locale", "city": "Trapani", "phone": "+39 091 000111"},
    )
    assert shared_phone.status_code == 409
    shared_email = client.post(
        "/companies",
        json={"name": "Ufficio", "city": "Agrigento", "email": "sala@barrossi.test"},
    )
    assert shared_email.status_code == 409
    shared_social = client.post(
        "/companies",
        json={
            "name": "Pagina",
            "city": "Enna",
            "social_links": [{"label": "Instagram", "url": "https://instagram.com/barrossi"}],
        },
    )
    assert shared_social.status_code == 409

    only_name = client.post("/companies", json={"name": "Senza Altro"})
    only_name_again = client.post("/companies", json={"name": "Senza Altro"})
    assert only_name.status_code == 201 and only_name_again.status_code == 201
    assert only_name.json()["company_id"] != only_name_again.json()["company_id"]
    _assert_quiet(db_session)


def test_import_preview_is_read_only_and_apply_is_idempotent(client, db_session, monkeypatch) -> None:
    _forbid_external(monkeypatch)
    existing = client.post(
        "/companies",
        json={
            "name": "Hotel Sole",
            "city": "Palermo",
            "email": "old@hotelsole.test",
            "notes": ["Nota vera"],
            "status": "proposal",
        },
    ).json()
    before = db_session.query(Company).count()
    payload = {
        "create_missing": True,
        "rows": [
            {
                "ref": "riga-nuova",
                "name": "Nuova Bottega",
                "city": "Roma",
                "notes": ["Appena inserita"],
                "tags": ["lotto2"],
                "events": [
                    {
                        "external_ref": "lotto2-20261116-0800:email:riga-nuova",
                        "kind": "email_sent",
                        "channel": "email",
                        "sender": "io@example.com",
                        "recipient": "bottega@example.com",
                        "batch_id": "lotto2-20261116-0800",
                        "occurred_on": "2026-11-16",
                    }
                ],
            },
            {
                "ref": "riga-nota",
                "company_id": existing["company_id"],
                "name": "Hotel Sole",
                "city": "Palermo",
                "email": "",
                "notes": ["Nota vera", "Seconda"],
                "tags": ["lotto2", "lotto2"],
                "social_links": [{"label": "Instagram", "url": "https://instagram.com/hotelsole"}],
                "status": "contacted",
                "events": [
                    {
                        "external_ref": "lotto2-20261116-0800:dm:riga-nota",
                        "kind": "dm_sent",
                        "channel": "instagram",
                        "sender": "@io",
                        "recipient": "@hotelsole",
                        "batch_id": "lotto2-20261116-0800",
                        "occurred_on": "2026-11-16",
                    }
                ],
            },
            {
                "ref": "riga-ambigua",
                "name": "Altro Nome",
                "city": "Milano",
                "email": "old@hotelsole.test",
            },
            {"ref": "riga-rotta", "name": "X", "email": "non-una-email"},
            {"ref": "riga-id", "company_id": str(uuid4()), "name": "Fantasma", "city": "Lecce"},
        ],
    }
    preview = client.post("/companies/import/preview", json=payload)
    assert preview.status_code == 200
    assert preview.json()["dry_run"] is True
    by_ref = {row["ref"]: row for row in preview.json()["rows"]}
    assert by_ref["riga-nuova"]["outcome"] == "new"
    assert by_ref["riga-nuova"]["company_id"] is None
    assert by_ref["riga-nuova"]["events"][0]["outcome"] == "would_record"
    assert by_ref["riga-nota"]["outcome"] == "update"
    assert by_ref["riga-nota"]["company_id"] == existing["company_id"]
    assert "email" not in by_ref["riga-nota"]["changes"]
    assert by_ref["riga-ambigua"]["outcome"] == "ambiguous"
    assert by_ref["riga-rotta"]["outcome"] == "invalid"
    assert by_ref["riga-id"]["outcome"] == "id_not_found"
    db_session.expire_all()
    assert db_session.query(Company).count() == before
    sent = db_session.query(Activity).filter(Activity.type == "email_sent").count()
    assert sent == 0

    applied = client.post("/companies/import", json=payload)
    assert applied.status_code == 200
    applied_rows = {row["ref"]: row for row in applied.json()["rows"]}
    assert applied_rows["riga-nuova"]["outcome"] == "created"
    assert applied_rows["riga-nuova"]["company_id"]
    assert applied_rows["riga-nuova"]["opportunity_id"]
    assert applied_rows["riga-nuova"]["events"][0]["outcome"] == "recorded"
    assert applied_rows["riga-nota"]["outcome"] == "updated"
    assert applied_rows["riga-nota"]["company_id"] == existing["company_id"]
    assert applied_rows["riga-ambigua"]["outcome"] == "ambiguous"
    assert applied_rows["riga-ambigua"]["company_id"] is None
    assert applied_rows["riga-id"]["outcome"] == "id_not_found"
    assert applied_rows["riga-id"]["company_id"] is None

    created = db_session.get(Company, UUID(applied_rows["riga-nuova"]["company_id"]))
    assert created.website_url is None
    assert created.email is None
    event = db_session.query(Activity).filter_by(external_ref="lotto2-20261116-0800:email:riga-nuova").one()
    assert event.type == "email_sent"
    assert event.occurred_at is None
    assert event.occurred_on.isoformat() == "2026-11-16"
    assert event.batch_id == "lotto2-20261116-0800"
    assert event.channel == "email"
    new_opportunity = db_session.query(Opportunity).filter_by(company_id=created.id).one()
    assert new_opportunity.status == "contacted"

    kept = db_session.get(Company, UUID(existing["company_id"]))
    assert kept.email == "old@hotelsole.test"
    kept_opportunity = db_session.query(Opportunity).filter_by(company_id=kept.id).one()
    assert kept_opportunity.status == "proposal"
    notes = [note.body for note in db_session.query(OpportunityNote).filter_by(opportunity_id=kept_opportunity.id)]
    assert notes.count("Nota vera") == 1
    assert notes.count("Seconda") == 1
    assert any(note.startswith("Conflitto da verificare") for note in notes)
    dm = db_session.query(Activity).filter_by(external_ref="lotto2-20261116-0800:dm:riga-nota").one()
    assert dm.type == "dm_sent"
    assert dm.occurred_at is None

    repeated = client.post("/companies/import", json=payload)
    repeated_rows = {row["ref"]: row for row in repeated.json()["rows"]}
    assert repeated_rows["riga-nuova"]["outcome"] == "existing"
    assert repeated_rows["riga-nuova"]["company_id"] == applied_rows["riga-nuova"]["company_id"]
    assert repeated_rows["riga-nuova"]["events"][0]["outcome"] == "duplicate"
    assert db_session.query(Activity).filter_by(external_ref="lotto2-20261116-0800:email:riga-nuova").count() == 1
    assert notes_again(db_session, kept_opportunity.id).count("Nota vera") == 1
    kept_notes = notes_again(db_session, kept_opportunity.id)
    conflicts = [note for note in kept_notes if note.startswith("Conflitto da verificare")]
    assert len(conflicts) == 1
    assert "«proposal»" in conflicts[0]
    _assert_quiet(db_session)


def notes_again(db_session, opportunity_id) -> list[str]:
    db_session.expire_all()
    return [note.body for note in db_session.query(OpportunityNote).filter_by(opportunity_id=opportunity_id)]


def test_import_preserves_exclusion_and_does_not_invent_time(client, db_session) -> None:
    company = Company(name="Chiusa", city="Palermo", source="manual", status="discovered")
    db_session.add(company)
    db_session.flush()
    opportunity = ensure_opportunity(db_session, company)
    update_opportunity(db_session, opportunity.id, status="uncontactable")
    add_note(db_session, opportunity.id, "Non contattare")
    add_tag(db_session, opportunity.id, "nd")

    payload = {
        "create_missing": True,
        "rows": [
            {
                "ref": "esclusa",
                "company_id": str(company.id),
                "name": "Chiusa",
                "city": "Palermo",
                "notes": [""],
                "tags": ["nd"],
                "status": "contacted",
                "events": [
                    {
                        "external_ref": "lotto2-20261116-0800:concept:esclusa",
                        "kind": "concept_sent",
                        "channel": "instagram",
                        "batch_id": "lotto2-20261116-0800",
                        "occurred_at": "2026-11-16T08:00:00+01:00",
                    },
                    {
                        "external_ref": "lotto2-20261116-0800:dm:esclusa",
                        "kind": "dm_sent",
                        "channel": "instagram",
                        "batch_id": "lotto2-20261116-0800",
                        "occurred_on": "2026-11-16",
                    },
                ],
            }
        ],
    }
    body = client.post("/companies/import", json=payload).json()["rows"][0]
    assert body["outcome"] == "updated"
    db_session.expire_all()
    assert db_session.get(Opportunity, opportunity.id).status == "uncontactable"
    kinds = {item.type for item in db_session.query(Activity).filter(Activity.type != "status_change")}
    assert kinds == {"concept_sent", "dm_sent"}
    concept = db_session.query(Activity).filter_by(type="concept_sent").one()
    assert concept.occurred_at is not None
    assert concept.occurred_on is None
    dm = db_session.query(Activity).filter_by(type="dm_sent").one()
    assert dm.occurred_at is None and dm.occurred_on.isoformat() == "2026-11-16"
    assert db_session.query(OpportunityNote).filter_by(body="Non contattare").count() == 1


def test_old_import_does_not_create_companies(client, db_session) -> None:
    response = client.post(
        "/opportunities/import",
        json={
            "format": "revampradar.pipeline",
            "version": 1,
            "companies": [{"name": "Mai vista", "city": "Palermo", "email": "nuova@example.com"}],
        },
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 0
    assert response.json()["errors"][0]["error"] == "Azienda non trovata."
    assert db_session.query(Company).count() == 0


def test_missing_id_can_match_another_verified_signal(client, db_session) -> None:
    created = client.post(
        "/companies", json={"name": "Bottega Vera", "city": "Palermo", "website_url": "https://bottega.test"}
    ).json()
    found = client.post(
        "/companies/import",
        json={
            "create_missing": True,
            "rows": [
                {
                    "ref": "id-sbagliato",
                    "company_id": str(uuid4()),
                    "name": "Bottega Vera",
                    "city": "Palermo",
                    "website_url": "https://bottega.test",
                }
            ],
        },
    ).json()["rows"][0]
    assert found["outcome"] == "existing"
    assert found["company_id"] == created["company_id"]
    assert db_session.query(Company).count() == 1


def test_create_missing_false_skips_new_rows(client, db_session) -> None:
    body = client.post(
        "/companies/import",
        json={"create_missing": False, "rows": [{"ref": "no", "name": "Non creare", "city": "Pisa"}]},
    ).json()["rows"][0]
    assert body["outcome"] == "skipped"
    assert body["company_id"] is None
    assert db_session.query(Company).count() == 0


def test_date_only_timestamp_is_rejected(client) -> None:
    response = client.post(
        "/companies",
        json={
            "name": "Con Evento",
            "events": [
                {
                    "external_ref": "evt-1",
                    "kind": "email_sent",
                    "channel": "email",
                    "occurred_at": "2026-11-16",
                }
            ],
        },
    )
    assert response.status_code == 422


def test_concurrent_creates_do_not_duplicate(tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'manual.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    barrier = threading.Barrier(2)
    results: list[tuple[str, str]] = []
    errors: list[BaseException] = []

    def worker() -> None:
        session = factory()
        try:
            barrier.wait(timeout=5)
            outcome, company, _candidates, _warnings, _error = create_manual_company(
                session,
                ManualCompanyCreate(name="Bar Rossi", city="Palermo", website_url="https://barrossi.test"),
            )
            # Chi arriva secondo trova il dominio già presente: 409 con l'id dell'altra.
            assert company is not None
            results.append((outcome, str(company.id)))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len({item[1] for item in results}) == 1
    assert sorted(item[0] for item in results) == ["created", "duplicate"]
    session = factory()
    try:
        assert session.query(Company).count() == 1
        assert session.query(Audit).count() == 0
    finally:
        session.close()
