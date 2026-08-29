from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.service import ai_findings, analyze_audit
from app.config import Settings, get_settings
from app.models.entities import (
    Audit,
    AuditFinding,
    OpportunityScore,
    Screenshot,
    Website,
    WebsiteScore,
)
from app.scanner import SCANNER_VERSION
from app.scanner.browser import capture_screenshots
from app.scanner.findings import FindingDraft, build_findings
from app.scanner.html import scan_html
from app.scanner.http import scan_http
from app.scanner.pagespeed import fetch_pagespeed
from app.scanner.seo import scan_seo
from app.scanner.url import NormalizedUrl, UrlValidationError, normalize_url
from app.scoring import FORMULA_VERSION, compute_business_score, compute_opportunity_score, compute_website_score


class AuditServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def create_audit(session: Session, raw_url: str) -> Audit:
    try:
        normalized = normalize_url(raw_url)
    except UrlValidationError as exc:
        raise AuditServiceError(str(exc), status_code=422) from exc

    website = _get_or_create_website(session, normalized)
    audit = Audit(
        website_id=website.id,
        status="queued",
        request_url=normalized.original,
        scanner_version=SCANNER_VERSION,
    )
    session.add(audit)
    session.commit()
    session.refresh(audit)
    session.refresh(website)
    return audit


def execute_audit(audit_id: UUID, settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    from app.db import get_session_factory

    session = get_session_factory()()
    try:
        audit = session.get(Audit, audit_id)
        if audit is None:
            return
        audit.status = "running"
        audit.started_at = datetime.now(UTC)
        session.commit()

        website = session.get(Website, audit.website_id)
        assert website is not None
        _run_scan(session, audit, website, resolved)
        session.commit()
    except Exception as exc:
        session.rollback()
        audit = session.get(Audit, audit_id)
        if audit is not None:
            audit.status = "failed"
            audit.error_message = str(exc)
            audit.completed_at = datetime.now(UTC)
            session.commit()
        raise
    finally:
        session.close()


def _run_scan(session: Session, audit: Audit, website: Website, settings: Settings) -> None:
    http_result = scan_http(website.normalized_url, settings)
    audit.http_data = http_result.to_dict()

    html_result = None
    seo_result = None
    if http_result.html:
        html_result = scan_html(http_result.html, http_result.final_url or website.normalized_url)
        audit.html_data = html_result.to_dict()
        seo_result = scan_seo(
            http_result.final_url or website.normalized_url,
            http_result.html,
            settings,
        )
        audit.seo_data = seo_result.to_dict()

    findings = build_findings(http_result, html_result, seo_result)
    target_url = http_result.final_url or website.normalized_url
    screenshot_devices: list[str] = []

    if http_result.ok:
        screenshot_dir = Path(settings.screenshot_dir) / str(audit.id)
        browser_result = capture_screenshots(target_url, screenshot_dir, settings)
        performance = {"browser": browser_result.get("performance")}
        if not browser_result.get("ok"):
            findings.append(
                FindingDraft(
                    category="browser",
                    severity="medium",
                    code="BROWSER_CAPTURE_FAILED",
                    title="Screenshot non disponibile",
                    description="Playwright non è riuscito a catturare la pagina.",
                    evidence=browser_result.get("error"),
                    recommendation="Riprova l'analisi. Se il sito blocca i bot, valuta un secondo passaggio.",
                    source_type="browser",
                )
            )
        for shot in browser_result.get("screenshots") or []:
            screenshot_devices.append(shot["device"])
            session.add(
                Screenshot(
                    audit_id=audit.id,
                    device=shot["device"],
                    viewport_width=shot["viewport_width"],
                    viewport_height=shot["viewport_height"],
                    file_path=shot["file_path"],
                )
            )
        pagespeed = fetch_pagespeed(target_url, settings)
        if pagespeed:
            performance["pagespeed"] = pagespeed
        audit.performance_data = performance

    ai_result, ai_meta = analyze_audit(
        settings=settings,
        url=target_url,
        http=audit.http_data,
        html=audit.html_data,
        seo=audit.seo_data,
        findings=findings,
        screenshot_devices=screenshot_devices,
    )
    audit.ai_data = ai_meta
    if ai_result is not None:
        findings.extend(ai_findings(ai_result))

    for draft in findings:
        session.add(
            AuditFinding(
                audit_id=audit.id,
                category=draft.category,
                severity=draft.severity,
                code=draft.code,
                title=draft.title,
                description=draft.description,
                evidence=draft.evidence,
                recommendation=draft.recommendation,
                source_type=draft.source_type,
            )
        )

    _persist_scores(session, audit, findings, ai_result)

    if not http_result.ok:
        audit.status = "failed"
        audit.error_message = http_result.error
    else:
        audit.status = "completed"
    audit.completed_at = datetime.now(UTC)


def _get_or_create_website(session: Session, normalized: NormalizedUrl) -> Website:
    website = session.query(Website).filter_by(normalized_url=normalized.normalized).one_or_none()
    if website is None:
        website = Website(
            url=normalized.original,
            normalized_url=normalized.normalized,
            domain=normalized.domain,
        )
        session.add(website)
        session.flush()
    return website


def _persist_scores(
    session: Session,
    audit: Audit,
    findings: list[FindingDraft],
    ai_result,
) -> None:
    website_draft = compute_website_score(
        findings,
        audit.http_data,
        audit.html_data,
        audit.seo_data,
        audit.performance_data,
        ai_result,
    )
    business_draft = compute_business_score(
        findings,
        audit.http_data,
        audit.html_data,
        audit.seo_data,
    )
    opportunity_draft = compute_opportunity_score(
        website_draft,
        business_draft,
        findings,
        audit.html_data,
        audit.seo_data,
    )
    session.add(
        WebsiteScore(
            audit_id=audit.id,
            technical_score=website_draft.technical_score,
            performance_score=website_draft.performance_score,
            ui_score=website_draft.ui_score,
            ux_score=website_draft.ux_score,
            mobile_score=website_draft.mobile_score,
            conversion_score=website_draft.conversion_score,
            seo_score=website_draft.seo_score,
            trust_score=website_draft.trust_score,
            overall_score=website_draft.overall_score,
            explanation=website_draft.explanation,
            components=website_draft.components,
            formula_version=FORMULA_VERSION,
        )
    )
    session.add(
        OpportunityScore(
            company_id=None,
            audit_id=audit.id,
            website_score=opportunity_draft.website_score,
            business_score=opportunity_draft.business_score,
            opportunity_score=opportunity_draft.opportunity_score,
            confidence=opportunity_draft.confidence,
            priority=opportunity_draft.priority,
            explanation=opportunity_draft.explanation,
            top_reasons=opportunity_draft.top_reasons,
            positive_factors=opportunity_draft.positive_factors,
            negative_factors=opportunity_draft.negative_factors,
            recommended_service=opportunity_draft.recommended_service,
            components=opportunity_draft.components,
            formula_version=FORMULA_VERSION,
        )
    )
