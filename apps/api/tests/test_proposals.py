from uuid import UUID

from app.models.entities import Audit, AuditFinding, Company, OpportunityScore, WebsiteScore
from app.proposals.builder import _greenfield_pitch, build_proposal_draft, estimate_range
from app.proposals.service import create_or_replace_proposal


def test_range_follows_service_and_does_not_invent_company() -> None:
    class Finding:
        code = "HTTP_NO_HTTPS"
        severity = "high"
        title = "Il sito non usa HTTPS"
        recommendation = "Attivare HTTPS."

    class Score:
        overall_score = 38
        opportunity_score = 72
        priority = "HIGH"
        recommended_service = "Messa in sicurezza HTTPS e sistemazione tecnica"

    draft = build_proposal_draft(
        domain="hotelsole.test",
        url="https://hotelsole.test",
        company_name=None,
        city=None,
        findings=[Finding()],
        website_score=Score(),
        opportunity_score=Score(),
    )
    assert draft.currency == "EUR"
    assert draft.range_min == 1500
    assert draft.range_max >= draft.range_min
    assert "hotelsole.test" in draft.summary
    assert "dipendenti" not in draft.email_body.lower()
    assert "fatturato" not in draft.email_body.lower()
    assert "iva" not in draft.email_body.lower()
    assert "1500" not in draft.email_body
    assert "4000" not in draft.email_body
    assert "Luca Bianchi" in draft.email_body
    assert "lucabianchi.dev" in draft.email_body
    assert "Upwork" in draft.email_body
    assert "mi chiamo" in draft.email_body.lower()
    assert f"EUR {draft.range_min}" in draft.brief
    assert draft.priority_problems[0]["code"] == "HTTP_NO_HTTPS"
    assert "HTTPS" in draft.recommended_service


def test_estimate_range_rebuild_vs_maintenance() -> None:
    rebuild = estimate_range("Ripristino hosting o ricostruzione del sito", 20, "VERY_HIGH")
    small = estimate_range("Interventi puntuali di manutenzione e miglioramento continuo", 80, "LOW")
    assert rebuild[0] > small[1]


def test_proposal_requires_completed_audit(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.audits.execute_audit", lambda audit_id: None)
    created = client.post("/audits", json={"url": "https://example.com"})
    audit_id = created.json()["id"]
    response = client.post(f"/audits/{audit_id}/proposal")
    assert response.status_code == 409


def test_generate_and_replace_proposal(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.api.audits.execute_audit", lambda audit_id: None)
    monkeypatch.setattr("app.proposals.service.polish_proposal", lambda *args, **kwargs: None)
    created = client.post("/audits", json={"url": "https://hotelsole.test"})
    audit_id = UUID(created.json()["id"])
    audit = db_session.get(Audit, audit_id)
    assert audit is not None
    audit.status = "completed"
    db_session.add(
        AuditFinding(
            audit_id=audit.id,
            category="http",
            severity="high",
            code="HTTP_NO_HTTPS",
            title="Il sito non usa HTTPS",
            description="La risposta non è in HTTPS.",
            evidence="http://hotelsole.test",
            recommendation="Attivare un certificato TLS.",
            source_type="scanner",
        )
    )
    db_session.add(
        WebsiteScore(
            audit_id=audit.id,
            technical_score=30,
            performance_score=40,
            ui_score=None,
            ux_score=40,
            mobile_score=35,
            conversion_score=30,
            seo_score=40,
            trust_score=45,
            overall_score=36,
            explanation="Website Score 36/100.",
            formula_version="1.0.0",
        )
    )
    db_session.add(
        OpportunityScore(
            audit_id=audit.id,
            website_score=36,
            business_score=50,
            opportunity_score=71,
            confidence=0.6,
            priority="HIGH",
            explanation="Opportunity Score 71/100 (HIGH).",
            top_reasons=["Sito debole"],
            positive_factors=[],
            negative_factors=["HTTPS assente"],
            recommended_service="Messa in sicurezza HTTPS e sistemazione tecnica",
            formula_version="1.0.0",
        )
    )
    db_session.commit()

    generated = client.post(f"/audits/{audit_id}/proposal")
    assert generated.status_code == 200
    body = generated.json()
    assert body["source"] == "deterministic"
    assert body["recommended_service"].startswith("Messa in sicurezza")
    assert body["range_min"] == 1500
    assert "hotelsole.test" in body["email_body"]
    assert "1500" not in body["email_body"]
    assert "Luca Bianchi" in body["email_body"]
    assert body["priority_problems"][0]["code"] == "HTTP_NO_HTTPS"
    first_id = body["id"]

    fetched = client.get(f"/audits/{audit_id}/proposal")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == first_id

    again = client.post(f"/audits/{audit_id}/proposal")
    assert again.status_code == 200
    assert again.json()["id"] == first_id

    missing = client.get("/audits/11111111-1111-1111-1111-111111111111/proposal")
    assert missing.status_code == 404


def test_service_builds_without_httpx(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.proposals.service.polish_proposal", lambda *args, **kwargs: None)
    from app.models.entities import Website
    from app.scanner.url import normalize_url

    normalized = normalize_url("https://luna.test")
    website = Website(
        url=normalized.original,
        normalized_url=normalized.normalized,
        domain=normalized.domain,
    )
    db_session.add(website)
    db_session.flush()
    audit = Audit(
        website_id=website.id,
        status="completed",
        request_url=normalized.original,
        scanner_version="test",
    )
    db_session.add(audit)
    db_session.commit()
    proposal = create_or_replace_proposal(db_session, audit.id)
    assert proposal.source == "deterministic"
    assert "luna.test" in proposal.summary


def test_greenfield_proposal_for_company_without_website(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.proposals.service.polish_proposal", lambda *args, **kwargs: None)
    company = Company(
        name="Trattoria da Mario",
        category="Ristorante",
        city="Palermo",
        region="Sicilia",
        country="Italia",
        website_url=None,
        phone="0911234567",
        source="osm",
        status="discovered",
    )
    db_session.add(company)
    db_session.commit()

    generated = client.post(f"/companies/{company.id}/greenfield-proposal")
    assert generated.status_code == 200
    body = generated.json()
    assert body["kind"] == "greenfield"
    assert body["audit_id"] is None
    assert "Trattoria da Mario" in body["email_body"]
    assert "prenotare direttamente online" in body["email_body"]
    assert "Trattoria da Mario" in body["summary"]

    fetched = client.get(f"/companies/{company.id}/proposal")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]

    growth = client.get(f"/companies/{company.id}/growth-score")
    assert growth.status_code == 200
    assert growth.json()["score"] >= 0


def test_greenfield_pitch_does_not_leak_restaurant_wording_to_other_categories() -> None:
    booking = _greenfield_pitch("Creazione sito vetrina con prenotazione online")
    catalog = _greenfield_pitch("Creazione sito vetrina con catalogo prodotti")
    generic = _greenfield_pitch("Creazione sito vetrina con scheda attività e contatti")
    for pitch in (booking, catalog, generic):
        assert "piatti" not in pitch
        assert "menù" not in pitch
    assert "prenotare direttamente online" in booking
    assert "prodotti" in catalog


def test_greenfield_proposal_rejected_when_company_has_website(client, db_session) -> None:
    company = Company(
        name="Hotel Sole",
        category="Hotel",
        website_url="https://hotelsole.test",
        source="osm",
        status="discovered",
    )
    db_session.add(company)
    db_session.commit()

    response = client.post(f"/companies/{company.id}/greenfield-proposal")
    assert response.status_code == 409


def test_sender_profile_defaults_and_update(client) -> None:
    first = client.get("/settings/profile")
    assert first.status_code == 200
    body = first.json()
    assert body["display_name"] == "Luca Bianchi"
    assert body["website_url"].startswith("https://")
    assert any(item["label"] == "Upwork" for item in body["freelancer_links"])

    updated = client.put(
        "/settings/profile",
        json={
            "display_name": "Sara Verdi",
            "intro": "Realizzo siti per hotel e B&B.",
            "website_url": "https://saraverdi.test",
            "freelancer_links": [{"label": "Malt", "url": "https://www.malt.fr/profile/sara"}],
            "social_links": [{"label": "LinkedIn", "url": "https://www.linkedin.com/in/saraverdi"}],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Sara Verdi"
    fetched = client.get("/settings/profile")
    assert fetched.json()["intro"].startswith("Realizzo siti")
    assert fetched.json()["freelancer_links"][0]["label"] == "Malt"

