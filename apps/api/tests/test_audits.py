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

    fetched = client.get(f"/audits/{payload['id']}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["id"] == payload["id"]
    assert body["website_score"] is None
    assert body["opportunity_score"] is None
    assert body["ai_analysis"] is None


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


def test_missing_audit_returns_404(client) -> None:
    response = client.get("/audits/11111111-1111-1111-1111-111111111111")
    assert response.status_code == 404
