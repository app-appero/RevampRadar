from uuid import UUID

from app.models.entities import Audit, AuditFinding, Company, OpportunityScore, WebsiteScore
from app.proposals.builder import build_greenfield_proposal_draft, build_proposal_draft, estimate_range
from app.proposals.service import create_or_replace_proposal
from app.proposals.templates import render_email_template


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


def test_use_ai_false_never_calls_polish_even_if_a_key_is_configured(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.api.audits.execute_audit", lambda audit_id: None)

    def _boom(*args, **kwargs):
        raise AssertionError("polish_proposal non deve essere chiamato con use_ai=false")

    monkeypatch.setattr("app.proposals.service.polish_proposal", _boom)
    client.put("/settings/ai", json={"provider": "claude", "anthropic_api_key": "sk-ant-test"})

    created = client.post("/audits", json={"url": "https://hotelsole.test"})
    audit_id = created.json()["id"]
    audit = db_session.get(Audit, UUID(audit_id))
    audit.status = "completed"
    db_session.commit()

    response = client.post(f"/audits/{audit_id}/proposal", params={"use_ai": "false"})
    assert response.status_code == 200
    assert response.json()["source"] == "deterministic"


def test_use_ai_true_falls_back_to_deterministic_without_a_key(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.api.audits.execute_audit", lambda audit_id: None)
    created = client.post("/audits", json={"url": "https://hotelsole.test"})
    audit_id = created.json()["id"]
    audit = db_session.get(Audit, UUID(audit_id))
    audit.status = "completed"
    db_session.commit()

    response = client.post(f"/audits/{audit_id}/proposal", params={"use_ai": "true"})
    assert response.status_code == 200
    assert response.json()["source"] == "deterministic"


def test_polish_proposal_falls_back_when_ai_proposes_a_time_slot(monkeypatch) -> None:
    from app.proposals.ai import polish_proposal
    from app.proposals.sender import DEFAULT_SENDER

    class FakeProvider:
        name = "fake"

        def complete_json(self, system, user, temperature=0.3):
            import json as _json

            return _json.dumps(
                {
                    "summary": "Riassunto AI",
                    "strategy": "Strategia AI",
                    "email_subject": "Oggetto AI",
                    "email_body": "Ciao, vi va se ci vediamo 10 minuti al telefono?",
                    "brief": "Brief AI",
                }
            )

    monkeypatch.setattr("app.proposals.ai.get_ai_provider", lambda settings: FakeProvider())
    draft = build_proposal_draft(
        domain="hotelsole.test",
        url="https://hotelsole.test",
        company_name=None,
        city=None,
        findings=[],
        website_score=None,
        opportunity_score=None,
    )
    from app.config import Settings

    polished = polish_proposal(Settings(), draft, {}, DEFAULT_SENDER)
    assert polished is not None
    assert polished.email_body == draft.email_body
    assert "10 minuti" not in polished.email_body


def test_polish_proposal_falls_back_when_ai_cites_an_internal_score(monkeypatch) -> None:
    from app.proposals.ai import polish_proposal
    from app.proposals.sender import DEFAULT_SENDER

    class FakeProvider:
        name = "fake"

        def complete_json(self, system, user, temperature=0.3):
            import json as _json

            return _json.dumps(
                {
                    "summary": "Riassunto AI",
                    "strategy": "Strategia AI",
                    "email_subject": "Oggetto AI",
                    "email_body": "Ciao, il vostro Opportunity Score è 72/100, molto interessante.",
                    "brief": "Brief AI",
                }
            )

    monkeypatch.setattr("app.proposals.ai.get_ai_provider", lambda settings: FakeProvider())
    draft = build_proposal_draft(
        domain="hotelsole.test",
        url="https://hotelsole.test",
        company_name=None,
        city=None,
        findings=[],
        website_score=None,
        opportunity_score=None,
    )
    from app.config import Settings

    polished = polish_proposal(Settings(), draft, {}, DEFAULT_SENDER)
    assert polished is not None
    assert polished.email_body == draft.email_body
    assert "opportunity score" not in polished.email_body.lower()


def test_polish_proposal_falls_back_when_ai_claims_lost_business(monkeypatch) -> None:
    from app.proposals.ai import polish_proposal
    from app.proposals.sender import DEFAULT_SENDER

    class FakeProvider:
        name = "fake"

        def complete_json(self, system, user, temperature=0.3):
            import json as _json

            return _json.dumps(
                {
                    "summary": "Riassunto AI",
                    "strategy": "Strategia AI",
                    "email_subject": "Oggetto AI",
                    "email_body": "Il vostro sito vi sta facendo perdere clienti ogni giorno.",
                    "brief": "Brief AI",
                }
            )

    monkeypatch.setattr("app.proposals.ai.get_ai_provider", lambda settings: FakeProvider())
    draft = build_proposal_draft(
        domain="hotelsole.test",
        url="https://hotelsole.test",
        company_name=None,
        city=None,
        findings=[],
        website_score=None,
        opportunity_score=None,
    )
    from app.config import Settings

    polished = polish_proposal(Settings(), draft, {}, DEFAULT_SENDER)
    assert polished is not None
    assert polished.email_body == draft.email_body
    assert "perdere clienti" not in polished.email_body.lower()


def test_email_body_mentions_one_verified_observation_when_relevant() -> None:
    class ViewportFinding:
        code = "HTML_MISSING_VIEWPORT"
        severity = "high"
        title = "Viewport mobile assente"
        recommendation = "Aggiungi il meta viewport."

    draft = build_proposal_draft(
        domain="hotelsole.test",
        url="https://hotelsole.test",
        company_name="Hotel Sole",
        city="Rimini",
        findings=[ViewportFinding()],
        website_score=None,
        opportunity_score=None,
    )
    assert "smartphone" in draft.email_body
    # Un solo elemento citato, non un elenco di problemi tecnici.
    assert draft.email_body.count("Ho notato in particolare") == 1


def test_email_body_has_no_dangling_placeholder_when_no_relevant_finding() -> None:
    draft = build_proposal_draft(
        domain="hotelsole.test",
        url="https://hotelsole.test",
        company_name="Hotel Sole",
        city="Rimini",
        findings=[],
        website_score=None,
        opportunity_score=None,
    )
    assert "{{osservazione}}" not in draft.email_body
    assert "Ho notato in particolare" not in draft.email_body


def test_greenfield_email_subject_does_not_assert_unverified_absence() -> None:
    class Score:
        score = 60
        priority = "HIGH"
        top_reasons = ["Nessun competitor comparabile trovato nella stessa zona."]
        positive_factors: list[str] = []
        recommended_service = "Creazione sito vetrina con scheda attività e contatti"

    draft = build_greenfield_proposal_draft(
        company_name="Bottega del Gusto",
        category="Alimentari",
        city="Lecce",
        growth_score=Score(),
    )
    assert "non ha un sito" not in draft.email_subject.lower()
    assert "vi manca" not in draft.email_subject.lower()


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
    assert "vostra attività" in body["email_body"]
    assert "sito web" in body["email_body"]
    assert "Trattoria da Mario" in body["summary"]

    fetched = client.get(f"/companies/{company.id}/proposal")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]

    growth = client.get(f"/companies/{company.id}/growth-score")
    assert growth.status_code == 200
    assert growth.json()["score"] >= 0


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
            "other_links": [{"label": "GitHub", "url": "https://github.com/saraverdi"}],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Sara Verdi"
    assert updated.json()["other_links"][0]["label"] == "GitHub"
    fetched = client.get("/settings/profile")
    assert fetched.json()["intro"].startswith("Realizzo siti")
    assert fetched.json()["freelancer_links"][0]["label"] == "Malt"
    assert fetched.json()["other_links"][0]["url"] == "https://github.com/saraverdi"


def test_signature_includes_other_links_under_their_own_heading() -> None:
    from app.proposals.sender import SenderLink, SenderProfileView, format_signature

    sender = SenderProfileView(
        display_name="Sara Verdi",
        intro="Realizzo siti.",
        website_url="https://saraverdi.test",
        freelancer_links=(),
        social_links=(SenderLink(label="LinkedIn", url="https://linkedin.test/saraverdi"),),
        other_links=(SenderLink(label="GitHub", url="https://github.com/saraverdi"),),
    )
    signature = format_signature(sender)
    assert "Altro:" in signature
    assert "https://github.com/saraverdi" in signature
    # GitHub non finisce più sotto "Social".
    social_block_start = signature.index("Social:")
    other_block_start = signature.index("Altro:")
    assert "github.com" not in signature[social_block_start:other_block_start]


def test_render_email_template_replaces_known_tokens_and_leaves_rest_untouched() -> None:
    rendered = render_email_template(
        "Ciao {{nome_attivita}}, saluti da {{nome_mittente}}. {{non_esiste}}",
        {"nome_attivita": "Bar Blu", "nome_mittente": "Luca"},
    )
    assert rendered == "Ciao Bar Blu, saluti da Luca. {{non_esiste}}"


def test_email_templates_default_then_update(client) -> None:
    first = client.get("/settings/email-templates")
    assert first.status_code == 200
    body = first.json()
    assert body["refactor_body"] is None
    assert body["greenfield_body"] is None
    assert "{{nome_mittente}}" in body["refactor_default"]
    assert "nome_mittente" in body["refactor_tokens"]
    assert "dominio" not in body["greenfield_tokens"]

    updated = client.put(
        "/settings/email-templates",
        json={
            "refactor_body": "Ciao {{nome_attivita}}, ho visto il vostro sito. {{firma}}",
            "greenfield_body": None,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["refactor_body"].startswith("Ciao {{nome_attivita}}")
    assert updated.json()["greenfield_body"] is None

    fetched = client.get("/settings/email-templates")
    assert fetched.json()["refactor_body"] == "Ciao {{nome_attivita}}, ho visto il vostro sito. {{firma}}"


def test_custom_refactor_template_is_used_when_generating_a_proposal(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.api.audits.execute_audit", lambda audit_id: None)
    monkeypatch.setattr("app.proposals.service.polish_proposal", lambda *args, **kwargs: None)
    client.put(
        "/settings/email-templates",
        json={"refactor_body": "Salve {{nome_attivita}}! Un saluto, {{firma}}", "greenfield_body": None},
    )
    created = client.post("/audits", json={"url": "https://hotelsole.test"})
    audit_id = UUID(created.json()["id"])
    audit = db_session.get(Audit, audit_id)
    assert audit is not None
    audit.status = "completed"
    db_session.commit()

    generated = client.post(f"/audits/{audit_id}/proposal")
    assert generated.status_code == 200
    assert generated.json()["email_body"].startswith("Salve hotelsole.test!")

