"""Contratto API CRM: alias `search`, campo `body` delle note, stato di contatto per email."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.models.entities import Activity, Company, Opportunity, OpportunityNote, OpportunityTag, Tag

SENT_TAG = "lotto2-20261116-inviato"


def _opportunity(db, name: str, *, status: str = "discovered", email: str | None = None, tags=()) -> Opportunity:
    company = Company(name=name, source="openstreetmap", status="discovered", email=email)
    db.add(company)
    db.flush()
    opportunity = Opportunity(company_id=company.id, status=status, is_favorite=False)
    db.add(opportunity)
    db.flush()
    for name_ in tags:
        tag = db.query(Tag).filter_by(name=name_).one_or_none()
        if tag is None:
            tag = Tag(name=name_)
            db.add(tag)
            db.flush()
        db.add(OpportunityTag(opportunity_id=opportunity.id, tag_id=tag.id))
    db.flush()
    return opportunity


def _seed_lotto2(db) -> None:
    """Le tre aziende del lotto 2 con le forme reali dei dati sul server di sviluppo."""
    imported_at = datetime(2026, 11, 16, 9, 42, 2, tzinfo=UTC)

    # Monte Civetta: nessuna email in anagrafica, l'indirizzo è solo nella nota dell'invio.
    civetta = _opportunity(
        db, "Albergo Monte Civetta", status="contacted", tags=(SENT_TAG, "no-reinvio-automatico", "canale-ig")
    )
    db.add(OpportunityNote(
        opportunity_id=civetta.id,
        body=(
            "[lotto2-20261116-0800 | invio riconciliato] Email inviata il 16/11/2026 da "
            "info@globetrotta.it a montecivetta@alice.it. Non reinviare automaticamente."
        ),
    ))
    db.add(Activity(opportunity_id=civetta.id, type="status_change",
                    note="discovered → contacted (import JSON)", occurred_at=imported_at))

    # Sant'Anna: email in anagrafica, stato contacted dal cambio stato dell'import.
    santanna = _opportunity(
        db, "Agriturismo Sant`Anna", status="contacted", email="info@aziendasantanna.it", tags=(SENT_TAG,)
    )
    db.add(Activity(opportunity_id=santanna.id, type="status_change",
                    note="discovered → contacted (import JSON)", occurred_at=imported_at))

    # Ottica Moderna: invio storico registrato come attività email_sent con sola data.
    ottica = _opportunity(
        db, "Ottica Moderna Belluno", status="contacted", email="otticamoderna9900@libero.it", tags=(SENT_TAG,)
    )
    db.add(Activity(
        opportunity_id=ottica.id, type="email_sent", occurred_on=date(2026, 11, 16), channel="email",
        sender="info@globetrotta.it", recipient="otticamoderna9900@libero.it",
        batch_id="lotto2-20261116-0800", external_ref="lotto2-20261116-0800:ottica-moderna-belluno:email:first",
        note="Email inviata (storico registrato, nessun messaggio spedito da RevampRadar).",
    ))

    # Controlli: mai contattata; solo tag di invio; tag che NON indica un invio.
    _opportunity(db, "Bar Gelateria Santa Lucia", email="santalucia@example.it")
    _opportunity(db, "Fiori Solo Tag", status="to_contact", email="fiori@example.it", tags=(SENT_TAG,))
    _opportunity(db, "Bozza Ferma", status="to_contact", email="bozza@example.it",
                 tags=("invio-aruba-da-completare", "bozza-non-inviata"))
    db.commit()


# --- contact-status ---------------------------------------------------------------------


def test_lotto2_emails_are_already_contacted(client, db_session) -> None:
    _seed_lotto2(db_session)
    response = client.post(
        "/opportunities/contact-status",
        json={"emails": ["MonteCivetta@Alice.it", "mailto:info@aziendasantanna.it",
                         "Ottica Moderna <otticamoderna9900@libero.it>"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["checked"] == 3
    assert body["already_contacted"] == 3
    by_email = {item["normalized_email"]: item for item in body["results"]}

    civetta = by_email["montecivetta@alice.it"]
    assert civetta["already_contacted"] is True
    assert civetta["status"] == "contacted"
    assert civetta["contacted_on"] == "2026-11-16"
    assert civetta["matches"][0]["company_name"] == "Albergo Monte Civetta"
    assert civetta["matches"][0]["matched_on"] == ["note"]
    assert f"tag:{SENT_TAG}" in civetta["matches"][0]["evidence"]

    santanna = by_email["info@aziendasantanna.it"]
    assert santanna["already_contacted"] is True
    assert santanna["status"] == "contacted"
    assert santanna["contacted_on"] == "2026-11-16"
    assert santanna["contacted_at"].startswith("2026-11-16T09:42:02")
    assert santanna["matches"][0]["company_name"] == "Agriturismo Sant`Anna"

    ottica = by_email["otticamoderna9900@libero.it"]
    assert ottica["already_contacted"] is True
    assert ottica["status"] == "contacted"
    assert ottica["contacted_on"] == "2026-11-16"
    assert "activity:email_sent" in ottica["matches"][0]["evidence"]
    assert set(ottica["matches"][0]["matched_on"]) == {"company_email", "activity_recipient"}


def test_contact_status_tags_controls_and_unknown(client, db_session) -> None:
    _seed_lotto2(db_session)
    body = client.post(
        "/opportunities/contact-status",
        json={"emails": ["santalucia@example.it", "fiori@example.it", "bozza@example.it",
                         "nessuno@example.it", "non-una-email"]},
    ).json()
    items = {item["email"]: item for item in body["results"]}

    never = items["santalucia@example.it"]
    assert never["already_contacted"] is False
    assert never["status"] == "discovered"
    assert never["contacted_on"] is None

    tag_only = items["fiori@example.it"]
    assert tag_only["already_contacted"] is True
    assert tag_only["status"] == "to_contact"
    assert tag_only["contacted_on"] == "2026-11-16"  # dalla data nel tag

    draft = items["bozza@example.it"]
    assert draft["already_contacted"] is False  # "invio-…-da-completare" e "non-inviata" non sono invii

    assert items["nessuno@example.it"]["matches"] == []
    assert items["non-una-email"]["valid"] is False
    assert body["already_contacted"] == 1


def test_contact_status_accepts_custom_sent_tags(client, db_session) -> None:
    _opportunity(db_session, "Studio Rossi", status="qualified", email="rossi@example.it", tags=("lotto3-spedito",))
    db_session.commit()
    plain = client.post("/opportunities/contact-status", json={"emails": ["rossi@example.it"]}).json()
    assert plain["results"][0]["already_contacted"] is False
    custom = client.post(
        "/opportunities/contact-status",
        json={"emails": ["rossi@example.it"], "contacted_tags": ["Lotto3-Spedito"]},
    ).json()
    assert custom["results"][0]["already_contacted"] is True


def test_contact_status_does_not_match_longer_addresses(client, db_session) -> None:
    _opportunity(db_session, "Altro", status="contacted", email="xinfo@aziendasantanna.it.com")
    db_session.commit()
    body = client.post("/opportunities/contact-status", json={"emails": ["info@aziendasantanna.it"]}).json()
    assert body["results"][0]["matches"] == []


# --- GET /opportunities?search= ---------------------------------------------------------


def test_search_is_an_alias_of_q(client, db_session) -> None:
    _opportunity(db_session, "Ottica Moderna Belluno")
    _opportunity(db_session, "Hotel Sole")
    db_session.commit()

    by_q = client.get("/opportunities", params={"q": "ottica"}).json()
    by_search = client.get("/opportunities", params={"search": "ottica"}).json()
    assert [item["company_name"] for item in by_search] == ["Ottica Moderna Belluno"]
    assert by_search == by_q
    # Entrambi presenti: vale q.
    both = client.get("/opportunities", params={"q": "hotel", "search": "ottica"}).json()
    assert [item["company_name"] for item in both] == ["Hotel Sole"]

    exported = client.get("/opportunities/export", params={"search": "ottica"}).json()
    assert len(exported["companies"]) == 1
    categories = client.get("/opportunities/categories", params={"search": "nessuna-corrispondenza"}).json()
    assert categories == []


def test_openapi_documents_search_and_note_body(client) -> None:
    schema = client.get("/openapi.json").json()
    params = {item["name"]: item for item in schema["paths"]["/opportunities"]["get"]["parameters"]}
    assert "alias" in params["search"]["description"].lower()
    note = schema["components"]["schemas"]["CreateNoteRequest"]
    assert note["required"] == ["body"]
    assert note["examples"] == [{"body": "Richiamare lunedì dopo le 10."}]
    assert "body" in schema["paths"]["/opportunities/{opportunity_id}/notes"]["post"]["description"]


# --- POST /opportunities/{id}/notes ---------------------------------------------------


def test_note_with_content_field_gets_a_clear_422(client, db_session) -> None:
    opportunity = _opportunity(db_session, "Hotel Sole")
    db_session.commit()

    wrong = client.post(f"/opportunities/{opportunity.id}/notes", json={"content": "Richiamare"})
    assert wrong.status_code == 422
    message = wrong.json()["detail"][0]["msg"]
    assert "«content»" in message and "«body»" in message

    ok = client.post(f"/opportunities/{opportunity.id}/notes", json={"body": "Richiamare"})
    assert ok.status_code == 200
    assert ok.json()["notes"][0]["body"] == "Richiamare"
