from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.models.entities import Audit, Company, Website
from app.services.app_store import enrich_app_links

STALE_AFTER_DAYS = 30


def intelligence_for_audit(session: Session, audit_id: UUID) -> dict | None:
    audit = (
        session.query(Audit)
        .options(
            selectinload(Audit.findings),
            selectinload(Audit.website).selectinload(Website.company),
            selectinload(Audit.website_score),
            selectinload(Audit.opportunity_score),
        )
        .filter(Audit.id == audit_id)
        .one_or_none()
    )
    if audit is None or audit.status != "completed":
        return None
    return _build(session, audit)


def intelligence_for_company(session: Session, company_id: UUID) -> dict | None:
    company = (
        session.query(Company)
        .options(selectinload(Company.websites))
        .filter(Company.id == company_id)
        .one_or_none()
    )
    if company is None:
        return None
    website = next((item for item in company.websites), None)
    if website is None:
        return {
            "company_id": str(company.id),
            "audit_id": None,
            "signals": _company_signals(company),
            "history": None,
            "monitoring": {"last_completed_at": None, "days_since": None, "stale": False},
        }
    audit = (
        session.query(Audit)
        .options(
            selectinload(Audit.findings),
            selectinload(Audit.website).selectinload(Website.company),
            selectinload(Audit.website_score),
            selectinload(Audit.opportunity_score),
        )
        .filter(Audit.website_id == website.id, Audit.status == "completed")
        .order_by(Audit.completed_at.desc())
        .first()
    )
    if audit is None:
        return {
            "company_id": str(company.id),
            "audit_id": None,
            "signals": _company_signals(company),
            "history": None,
            "monitoring": {"last_completed_at": None, "days_since": None, "stale": True},
        }
    return _build(session, audit)


def _build(session: Session, audit: Audit) -> dict:
    website = audit.website
    company = website.company if website else None
    html = audit.html_data or {}
    previous = _previous_audit(session, audit)
    days_since = _days_since(audit.completed_at)
    return {
        "company_id": str(company.id) if company else None,
        "audit_id": str(audit.id),
        "signals": {
            **_page_signals(html),
            **_company_signals(company),
        },
        "history": _history(audit, previous),
        "monitoring": {
            "last_completed_at": audit.completed_at.isoformat() if audit.completed_at else None,
            "days_since": days_since,
            "stale": days_since is not None and days_since >= STALE_AFTER_DAYS,
        },
    }


def _page_signals(html: dict) -> dict:
    technologies = list(html.get("technologies") or [])
    analytics = list(html.get("analytics") or [])
    social = list(html.get("social_links") or [])
    app_links = enrich_app_links(list(html.get("app_links") or []))
    generator = html.get("generator")
    aging = _aging_notes(technologies, generator)
    saas = list(html.get("saas_signals") or [])
    return {
        "technologies": technologies,
        "analytics": analytics,
        "social": social,
        "app_links": app_links,
        "generator": generator,
        "aging": aging,
        "saas": saas,
    }


def _company_signals(company: Company | None) -> dict:
    extra = (company.extra or {}) if company else {}
    osm = extra.get("osm_tags") if isinstance(extra.get("osm_tags"), dict) else {}
    stars = osm.get("stars") if osm else None
    return {
        "osm_stars": str(stars) if stars is not None else None,
        "osm_tags": {str(key): str(value) for key, value in osm.items()} if osm else {},
        "osm_start_date": str(osm["start_date"]) if osm.get("start_date") else None,
        "osm_opening_hours": str(osm["opening_hours"]) if osm.get("opening_hours") else None,
        "has_phone": bool(company.phone) if company else False,
        "has_email": bool(company.email) if company else False,
        "has_website": bool(company.website_url) if company else False,
    }


def _aging_notes(technologies: list[str], generator: str | None) -> list[str]:
    notes: list[str] = []
    text = (generator or "").lower()
    if "wordpress" in technologies:
        if _looks_old_wordpress(text):
            notes.append(f"WordPress con generator datato: {generator}.")
        elif generator:
            notes.append(f"CMS dichiarato: {generator}.")
        else:
            notes.append("WordPress rilevato; versione non dichiarata nel generator.")
    elif generator:
        notes.append(f"Generator: {generator}.")
    return notes


def _looks_old_wordpress(generator: str) -> bool:
    if "wordpress" not in generator:
        return False
    for token in generator.replace(",", " ").split():
        if token[:1].isdigit() and token[0] in {"3", "4"}:
            return True
        if token.startswith("5.") and token[2:3].isdigit() and int(token[2]) <= 4:
            return True
    return False


def _previous_audit(session: Session, audit: Audit) -> Audit | None:
    if audit.website_id is None:
        return None
    return (
        session.query(Audit)
        .options(selectinload(Audit.findings), selectinload(Audit.website_score), selectinload(Audit.opportunity_score))
        .filter(
            Audit.website_id == audit.website_id,
            Audit.status == "completed",
            Audit.id != audit.id,
        )
        .order_by(Audit.completed_at.desc())
        .first()
    )


def _history(current: Audit, previous: Audit | None) -> dict | None:
    if previous is None:
        return None
    current_codes = {item.code for item in current.findings}
    previous_codes = {item.code for item in previous.findings}
    current_site = current.website_score.overall_score if current.website_score else None
    previous_site = previous.website_score.overall_score if previous.website_score else None
    current_opp = current.opportunity_score.opportunity_score if current.opportunity_score else None
    previous_opp = previous.opportunity_score.opportunity_score if previous.opportunity_score else None
    return {
        "previous_audit_id": str(previous.id),
        "previous_completed_at": previous.completed_at.isoformat() if previous.completed_at else None,
        "website_score_delta": _delta(current_site, previous_site),
        "opportunity_score_delta": _delta(current_opp, previous_opp),
        "new_finding_codes": sorted(current_codes - previous_codes),
        "resolved_finding_codes": sorted(previous_codes - current_codes),
    }


def _delta(current: int | None, previous: int | None) -> int | None:
    if current is None or previous is None:
        return None
    return current - previous


def _days_since(completed_at: datetime | None) -> int | None:
    if completed_at is None:
        return None
    when = completed_at if completed_at.tzinfo else completed_at.replace(tzinfo=UTC)
    return max(0, (datetime.now(UTC) - when).days)
