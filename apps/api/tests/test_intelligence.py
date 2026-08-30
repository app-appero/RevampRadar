from datetime import UTC, datetime, timedelta

from app.models.entities import Audit, AuditFinding, Company, OpportunityScore, Website, WebsiteScore
from app.scanner.html import scan_html
from app.services.intelligence import intelligence_for_audit, intelligence_for_company


def test_html_extracts_social_and_generator() -> None:
    html = """
    <html><head><meta name="generator" content="WordPress 4.9.8"></head>
    <body>
      <a href="https://www.facebook.com/hotelsole">FB</a>
      <a href="https://instagram.com/hotelsole">IG</a>
    </body></html>
    """
    result = scan_html(html, "https://hotelsole.test/")
    assert result.generator == "WordPress 4.9.8"
    networks = {item["network"] for item in result.social_links}
    assert networks == {"facebook", "instagram"}


def test_intelligence_history_and_osm_stars(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.api.audits.execute_audit", lambda audit_id: None)
    company = Company(
        name="Hotel Sole",
        city="Palermo",
        source="fake",
        external_id="h1",
        extra={"osm_tags": {"stars": "4", "tourism": "hotel"}},
        website_url="https://hotelsole.test",
    )
    db_session.add(company)
    db_session.flush()
    website = Website(
        company_id=company.id,
        url="https://hotelsole.test",
        normalized_url="https://hotelsole.test",
        domain="hotelsole.test",
    )
    db_session.add(website)
    db_session.flush()

    old = _completed_audit(
        db_session,
        website.id,
        completed_at=datetime.now(UTC) - timedelta(days=40),
        website_score=50,
        opportunity_score=60,
        finding_code="HTML_WEAK_CTA",
        html={"technologies": ["wordpress"], "analytics": [], "social_links": [], "generator": "WordPress 4.9"},
    )
    new = _completed_audit(
        db_session,
        website.id,
        completed_at=datetime.now(UTC),
        website_score=42,
        opportunity_score=71,
        finding_code="HTTP_NO_HTTPS",
        html={
            "technologies": ["wordpress"],
            "analytics": ["google_analytics"],
            "social_links": [{"network": "facebook", "url": "https://facebook.com/sole"}],
            "generator": "WordPress 4.9",
        },
    )
    db_session.commit()

    payload = intelligence_for_audit(db_session, new.id)
    assert payload is not None
    assert payload["signals"]["osm_stars"] == "4"
    assert payload["signals"]["analytics"] == ["google_analytics"]
    assert payload["signals"]["social"][0]["network"] == "facebook"
    assert any("WordPress" in note for note in payload["signals"]["aging"])
    assert payload["history"]["previous_audit_id"] == str(old.id)
    assert payload["history"]["website_score_delta"] == -8
    assert payload["history"]["opportunity_score_delta"] == 11
    assert "HTTP_NO_HTTPS" in payload["history"]["new_finding_codes"]
    assert "HTML_WEAK_CTA" in payload["history"]["resolved_finding_codes"]
    assert payload["monitoring"]["stale"] is False

    company_payload = intelligence_for_company(db_session, company.id)
    assert company_payload["audit_id"] == str(new.id)


def test_intelligence_api_requires_completed(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.audits.execute_audit", lambda audit_id: None)
    created = client.post("/audits", json={"url": "https://example.com"})
    audit_id = created.json()["id"]
    response = client.get(f"/audits/{audit_id}/intelligence")
    assert response.status_code == 404


def _completed_audit(session, website_id, *, completed_at, website_score, opportunity_score, finding_code, html) -> Audit:
    audit = Audit(
        website_id=website_id,
        status="completed",
        request_url="https://hotelsole.test",
        scanner_version="test",
        completed_at=completed_at,
        html_data=html,
    )
    session.add(audit)
    session.flush()
    session.add(
        AuditFinding(
            audit_id=audit.id,
            category="http",
            severity="high",
            code=finding_code,
            title=finding_code,
            description="test",
            recommendation="fix",
            source_type="scanner",
        )
    )
    session.add(
        WebsiteScore(
            audit_id=audit.id,
            technical_score=website_score,
            performance_score=website_score,
            ui_score=None,
            ux_score=website_score,
            mobile_score=website_score,
            conversion_score=website_score,
            seo_score=website_score,
            trust_score=website_score,
            overall_score=website_score,
            explanation="t",
            formula_version="1.0.0",
        )
    )
    session.add(
        OpportunityScore(
            audit_id=audit.id,
            website_score=website_score,
            business_score=50,
            opportunity_score=opportunity_score,
            confidence=0.5,
            priority="HIGH",
            explanation="t",
            top_reasons=[],
            positive_factors=[],
            negative_factors=[],
            recommended_service="test",
            formula_version="1.0.0",
        )
    )
    return audit
