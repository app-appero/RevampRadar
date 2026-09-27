"""Orchestrazione di 'Approfondisci prospect': avvio on-demand, mai automatico."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.parse import parse_json_object
from app.ai.provider import get_ai_provider
from app.config import Settings, get_settings
from app.deep_research import RESEARCH_VERSION
from app.deep_research.brief import build_company_brief
from app.deep_research.crawler import ResearchPage, fetch_pages, select_priority_pages
from app.deep_research.digital_presence import build_digital_presence
from app.deep_research.prompt_v1 import SYSTEM_PROMPT
from app.models.entities import Audit, AuditFinding, BusinessSignal, Company, CompanyResearch, Website
from app.services.ai_settings import effective_settings

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


class DeepResearchError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def get_research(session: Session, company_id: UUID) -> CompanyResearch | None:
    return session.query(CompanyResearch).filter_by(company_id=company_id).one_or_none()


def get_or_create_research(session: Session, company_id: UUID) -> CompanyResearch:
    research = get_research(session, company_id)
    if research is None:
        research = CompanyResearch(company_id=company_id, status="never", research_version=RESEARCH_VERSION)
        session.add(research)
        session.commit()
        session.refresh(research)
    return research


def refresh_stale_status(session: Session, research: CompanyResearch, company: Company) -> CompanyResearch:
    """Se un audit più recente è arrivato dopo l'ultima ricerca completata, segna 'da aggiornare'."""
    if research.status not in {"completed", "partial"} or research.completed_at is None:
        return research
    website = (
        session.query(Website).filter_by(company_id=company.id).order_by(Website.created_at.desc()).first()
    )
    if website is None:
        return research
    latest_audit = (
        session.query(Audit)
        .filter_by(website_id=website.id, status="completed")
        .order_by(Audit.completed_at.desc())
        .first()
    )
    if latest_audit is not None and latest_audit.completed_at and latest_audit.completed_at > research.completed_at:
        research.status = "stale"
        session.commit()
        session.refresh(research)
    return research


def start_research(session: Session, company_id: UUID) -> CompanyResearch:
    company = session.get(Company, company_id)
    if company is None:
        raise DeepResearchError("Azienda non trovata.", status_code=404)
    research = get_or_create_research(session, company_id)
    if research.status == "in_progress":
        raise DeepResearchError("Ricerca già in corso per questa azienda.", status_code=409)
    research.status = "in_progress"
    research.started_at = datetime.now(UTC)
    research.completed_at = None
    research.error_message = None
    research.progress_percent = 5
    research.progress_label = "Avvio ricerca"
    session.commit()
    session.refresh(research)
    return research


def execute_research(company_id: UUID, settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    from app.db import get_session_factory

    session = get_session_factory()()
    try:
        research = get_research(session, company_id)
        company = session.get(Company, company_id)
        if research is None or company is None:
            return
        _run_research(session, research, company, effective_settings(session, resolved))
        session.commit()
    except Exception as exc:  # noqa: BLE001 - task in background, non deve propagare
        session.rollback()
        research = get_research(session, company_id)
        if research is not None:
            research.status = "failed"
            research.error_message = str(exc)
            research.completed_at = datetime.now(UTC)
            research.progress_percent = 100
            research.progress_label = "Fallita"
            session.commit()
        logger.exception("Deep research fallita per company %s", company_id)
    finally:
        session.close()


def _set_progress(session: Session, research: CompanyResearch, percent: int, label: str) -> None:
    research.progress_percent = max(0, min(100, percent))
    research.progress_label = label
    session.commit()


def _run_research(session: Session, research: CompanyResearch, company: Company, settings: Settings) -> None:
    _set_progress(session, research, 15, "Analisi sito aziendale")

    website = (
        session.query(Website).filter_by(company_id=company.id).order_by(Website.created_at.desc()).first()
    )
    latest_audit = None
    internal_links: list[str] = []
    if website is not None:
        latest_audit = (
            session.query(Audit)
            .filter_by(website_id=website.id, status="completed")
            .order_by(Audit.completed_at.desc())
            .first()
        )
        if latest_audit is not None and latest_audit.html_data:
            internal_links = latest_audit.html_data.get("internal_links") or []

    partial = website is None or latest_audit is None
    pages: list[ResearchPage] = []
    if internal_links:
        priority = select_priority_pages(internal_links)
        pages = fetch_pages(priority, settings)
        if not pages:
            partial = True

    _set_progress(session, research, 40, "Presenza digitale")
    html_data = latest_audit.html_data if latest_audit else None
    digital_presence = build_digital_presence(company, html_data)
    research.website_findings = {
        "pages": [
            {"kind": page.kind, "url": page.url, "title": page.title, "text_excerpt": page.text_excerpt}
            for page in pages
        ]
    }
    research.digital_presence = digital_presence
    research.social_signals = {
        "note": (
            "Nessuno scraping dei profili social: si riportano solo esistenza, URL e fonte, "
            "già derivati da OSM e dal sito. Nessuna inferenza su performance o engagement."
        )
    }
    research.external_sources = []

    _set_progress(session, research, 60, "Segnali aziendali")
    business_signals = session.query(BusinessSignal).filter_by(company_id=company.id).all()

    audit_findings: list[dict] = []
    if latest_audit is not None:
        findings = session.query(AuditFinding).filter_by(audit_id=latest_audit.id).all()
        findings.sort(key=lambda item: _SEVERITY_RANK.get(item.severity, 9))
        audit_findings = [{"title": item.title, "severity": item.severity} for item in findings[:5]]

    _set_progress(session, research, 75, "Sintesi (AI opzionale)")
    ai_text = _maybe_ai_synthesis(settings, company, pages, digital_presence, audit_findings)

    brief = build_company_brief(
        company=company,
        pages=pages,
        digital_presence=digital_presence,
        business_signals=business_signals,
        audit_findings=audit_findings,
        ai_text=ai_text,
    )
    research.brief = brief
    research.research_version = RESEARCH_VERSION

    research.status = "partial" if partial else "completed"
    research.progress_percent = 100
    research.progress_label = "Completata (parziale)" if partial else "Completata"
    research.completed_at = datetime.now(UTC)


def _maybe_ai_synthesis(
    settings: Settings,
    company: Company,
    pages: list[ResearchPage],
    digital_presence: dict,
    audit_findings: list[dict],
) -> dict | None:
    if not pages:
        return None
    provider = get_ai_provider(settings)
    if provider is None:
        return None
    facts = {
        "company_name": company.name,
        "category": company.category,
        "city": company.city,
        "pages": [{"kind": p.kind, "title": p.title, "text": p.text_excerpt} for p in pages],
        "digital_presence": digital_presence,
        "website_problems": [item["title"] for item in audit_findings],
        "known_fields_only": True,
    }
    try:
        content = provider.complete_json(SYSTEM_PROMPT, json.dumps(facts, ensure_ascii=False), temperature=0.2)
        parsed = parse_json_object(content)
    except Exception as exc:
        logger.warning("Deep research AI synthesis fallita: %s", exc)
        return None
    what_it_does = parsed.get("what_it_does")
    homepage_direction = parsed.get("homepage_direction")
    if not isinstance(what_it_does, str) and not isinstance(homepage_direction, str):
        return None
    return {
        "what_it_does": what_it_does if isinstance(what_it_does, str) else None,
        "homepage_direction": homepage_direction if isinstance(homepage_direction, str) else None,
    }
