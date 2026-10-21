from uuid import UUID

from app.models.entities import OpportunityScore, WebsiteScore


def test_create_audit_rejects_invalid_url(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.audits.execute_audit", lambda audit_id: None)
    response = client.post("/audits", json={"url": "ftp://example.com"})
    assert response.status_code == 422


def test_create_and_get_audit(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.audits.execute_audit", lambda audit_id: None)
    created = client.post("/audits", json={"url": "https://Example.com/hotel/"})
    assert created.status_code == 202
    payload = created.json()
    assert payload["status"] == "queued"
    assert payload["normalized_url"] == "https://example.com/hotel"
    assert payload["domain"] == "example.com"
    assert payload["progress_percent"] == 0
    assert payload["progress_label"] == "In coda"

    fetched = client.get(f"/audits/{payload['id']}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["id"] == payload["id"]
    assert body["website_score"] is None
    assert body["opportunity_score"] is None
    assert body["ai_analysis"] is None


def test_audit_response_includes_company_id_and_company_history(client, db_session, monkeypatch) -> None:
    from datetime import UTC, datetime

    from app.models.entities import Audit, Company, OpportunityScore, WebsiteScore

    monkeypatch.setattr("app.api.audits.execute_audit", lambda audit_id: None)
    company = Company(name="Hotel Sole", source="fake", status="discovered")
    db_session.add(company)
    db_session.commit()
    company_id = company.id
    audit_ids = []
    for index, created_at in enumerate((datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC))):
        response = client.post(
            "/audits",
            json={"url": "https://hotelsole.test", "company_id": str(company_id)},
        )
        assert response.status_code == 202
        audit_id = UUID(response.json()["id"])
        audit_ids.append(audit_id)
        audit = db_session.get(Audit, audit_id)
        assert audit is not None
        audit.created_at = created_at
        db_session.add(
            WebsiteScore(
                audit_id=audit_id,
                technical_score=50 + index,
                performance_score=60,
                ui_score=None,
                ux_score=65,
                mobile_score=55,
                conversion_score=45,
                seo_score=70,
                trust_score=75,
                overall_score=58 + index,
                explanation="Test score",
                formula_version="1.0.0",
            )
        )
        db_session.add(
            OpportunityScore(
                audit_id=audit_id,
                website_score=58 + index,
                business_score=68,
                opportunity_score=72 + index,
                confidence=0.7,
                priority="HIGH",
                explanation="Test opportunity",
                top_reasons=[],
                positive_factors=[],
                negative_factors=[],
                recommended_service="Redesign",
                formula_version="1.0.0",
            )
        )
    db_session.commit()

    latest = client.get(f"/audits/{audit_ids[0]}")
    history = client.get(f"/audits/companies/{company_id}")

    assert latest.json()["company_id"] == str(company_id)
    assert history.status_code == 200
    rows = history.json()
    assert [row["id"] for row in rows] == [str(audit_ids[0]), str(audit_ids[1])]
    assert rows[0]["website_score"] == 58
    assert rows[0]["technical_score"] == 50
    assert rows[0]["business_score"] == 68
    assert rows[0]["opportunity_score"] == 72


def test_get_audit_includes_persisted_scores(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.api.audits.execute_audit", lambda audit_id: None)
    created = client.post("/audits", json={"url": "https://example.com"})
    audit_id = created.json()["id"]

    db_session.add(
        WebsiteScore(
            audit_id=UUID(audit_id),
            technical_score=40,
            performance_score=50,
            ui_score=None,
            ux_score=45,
            mobile_score=30,
            conversion_score=35,
            seo_score=55,
            trust_score=60,
            overall_score=42,
            explanation="Website Score 42/100.",
            components={"scores": {"technical": 40}},
            formula_version="1.0.0",
        )
    )
    db_session.add(
        OpportunityScore(
            audit_id=UUID(audit_id),
            website_score=42,
            business_score=58,
            opportunity_score=67,
            confidence=0.61,
            priority="HIGH",
            explanation="Opportunity Score 67/100 (HIGH).",
            top_reasons=["Sito debole con segnali di attività"],
            positive_factors=["analytics presente"],
            negative_factors=["CTA assenti"],
            recommended_service="Redesign mobile e ottimizzazione conversioni",
            components={"website_gap": 58},
            formula_version="1.0.0",
        )
    )
    db_session.commit()

    fetched = client.get(f"/audits/{audit_id}")
    body = fetched.json()
    assert body["website_score"]["overall_score"] == 42
    assert body["website_score"]["ui_score"] is None
    assert body["opportunity_score"]["opportunity_score"] == 67
    assert body["opportunity_score"]["priority"] == "HIGH"
    assert body["opportunity_score"]["recommended_service"].startswith("Redesign")


def test_list_recent_audits(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.audits.execute_audit", lambda audit_id: None)
    first = client.post("/audits", json={"url": "https://alpha.example"})
    second = client.post("/audits", json={"url": "https://beta.example"})
    listed = client.get("/audits")
    assert listed.status_code == 200
    rows = listed.json()
    ids = {item["id"] for item in rows}
    assert first.json()["id"] in ids
    assert second.json()["id"] in ids


def test_missing_audit_returns_404(client) -> None:
    response = client.get("/audits/11111111-1111-1111-1111-111111111111")
    assert response.status_code == 404
