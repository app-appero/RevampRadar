from app.ai.schema import AIAnalysisResult
from app.scanner.findings import FindingDraft
from app.scoring.business import compute_business_score
from app.scoring.constants import OPPORTUNITY_WEIGHTS, WEBSITE_WEIGHTS
from app.scoring.opportunity import compute_opportunity_score, recommended_service
from app.scoring.website import compute_website_score


def _finding(code: str, category: str, severity: str, title: str) -> FindingDraft:
    return FindingDraft(
        category=category,
        severity=severity,
        code=code,
        title=title,
        description="desc",
        evidence=None,
        recommendation="fix",
    )


def _scores(findings, http, html, seo, ai=None):
    website = compute_website_score(findings, http, html, seo, None, ai)
    business = compute_business_score(findings, http, html, seo)
    opportunity = compute_opportunity_score(website, business, findings, html, seo)
    return website, business, opportunity


def test_weights_sum_to_one() -> None:
    assert round(sum(WEBSITE_WEIGHTS.values()), 10) == 1.0
    assert round(sum(OPPORTUNITY_WEIGHTS.values()), 10) == 1.0


def test_healthy_site_has_high_website_score_and_null_ui() -> None:
    http = {"ok": True, "https": True, "response_time_ms": 180, "status_code": 200}
    html = {
        "viewport": "width=device-width",
        "cta_texts": ["Prenota ora"],
        "analytics": ["google_analytics"],
        "h1": ["Hotel sul mare"],
        "title": "Hotel sul mare",
        "favicon": "/favicon.ico",
        "structured_data_count": 1,
        "lang": "it",
        "technologies": ["wordpress"],
        "internal_links": [f"/p{i}" for i in range(10)],
    }
    seo = {"sitemap_found": True, "robots_found": True}
    website, _business, opportunity = _scores([], http, html, seo)
    assert website.overall_score >= 80
    assert website.ui_score is None
    assert opportunity.priority in {"LOW", "MEDIUM"}


def test_poor_but_active_site_is_a_better_opportunity_than_a_strong_site() -> None:
    active_html = {
        "analytics": ["google_tag_manager"],
        "technologies": ["wordpress"],
        "structured_data_count": 1,
        "internal_links": [f"/p{i}" for i in range(8)],
        "lang": "it",
        "favicon": "/favicon.ico",
    }
    active_http = {"ok": True, "https": True, "response_time_ms": 900, "status_code": 200}
    active_seo = {"sitemap_found": True, "robots_found": True}

    poor_findings = [
        _finding("HTML_MISSING_VIEWPORT", "mobile", "high", "Viewport mobile assente"),
        _finding("HTML_WEAK_CTA", "conversion", "medium", "CTA poco evidenti"),
        _finding("HTML_MISSING_TITLE", "html", "high", "Title assente"),
        _finding("HTML_MISSING_H1", "html", "high", "H1 assente"),
        _finding("SEO_MISSING_DESCRIPTION", "seo", "medium", "Meta description assente"),
    ]
    poor_html = {
        **active_html,
        "viewport": None,
        "cta_texts": [],
        "h1": [],
        "title": None,
    }
    strong_html = {
        **active_html,
        "viewport": "width=device-width",
        "cta_texts": ["Prenota"],
        "h1": ["Hotel"],
        "title": "Hotel",
    }

    poor_w, _, poor_o = _scores(poor_findings, active_http, poor_html, active_seo)
    strong_w, _, strong_o = _scores([], active_http, strong_html, active_seo)

    assert poor_w.overall_score < strong_w.overall_score
    assert poor_o.opportunity_score > strong_o.opportunity_score
    service = poor_o.recommended_service.lower()
    assert poor_o.priority in {"HIGH", "VERY_HIGH"}
    assert "https" in service or "mobile" in service or "conversioni" in service


def test_unreachable_site_is_not_a_high_priority_opportunity() -> None:
    findings = [_finding("HTTP_UNREACHABLE", "http", "critical", "Sito non raggiungibile")]
    http = {"ok": False, "https": False, "error": "timeout"}
    website, business, opportunity = _scores(findings, http, None, None)
    assert website.overall_score <= 20
    assert business.score <= 15
    assert opportunity.priority in {"LOW", "MEDIUM"}
    assert opportunity.recommended_service.startswith("Ripristino")


def test_https_issue_recommends_security_service() -> None:
    findings = [_finding("HTTP_NO_HTTPS", "http", "high", "HTTPS assente")]
    assert recommended_service(findings, 50) == "Messa in sicurezza HTTPS e sistemazione tecnica"


def test_ai_scores_are_blended_and_do_not_invent_ui_when_null() -> None:
    html = {"viewport": "width=device-width", "cta_texts": ["Contattaci"], "h1": ["Studio"], "lang": "it"}
    http = {"ok": True, "https": True, "response_time_ms": 300}
    ai = AIAnalysisResult(ui_score=None, ux_score=40, conversion_score=30, confidence=0.5)
    website = compute_website_score([], http, html, {}, None, ai)
    assert website.ui_score is None
    assert website.ux_score < 78
    assert website.conversion_score < 100


def test_explainability_fields_are_populated() -> None:
    findings = [
        _finding("HTML_WEAK_CTA", "conversion", "medium", "CTA poco evidenti"),
        _finding("HTML_MISSING_VIEWPORT", "mobile", "high", "Viewport mobile assente"),
    ]
    http = {"ok": True, "https": True}
    html = {"analytics": ["google_analytics"], "cta_texts": []}
    seo = {"sitemap_found": True}
    _, _, opportunity = _scores(findings, http, html, seo)
    assert opportunity.top_reasons
    assert opportunity.recommended_service
    assert "website_gap" in opportunity.components
    assert opportunity.confidence > 0
