from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.models.entities import Audit, Company, Proposal, Website
from app.proposals.ai import polish_proposal
from app.proposals.builder import ProposalDraft, build_greenfield_proposal_draft, build_proposal_draft
from app.proposals.prompt_v1 import PROMPT_VERSION
from app.services.growth_service import compute_and_store_growth_score, get_growth_score
from app.services.sender_profile import get_or_create_sender_profile, profile_view


class ProposalServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def load_proposal_for_audit(session: Session, audit_id: UUID) -> Proposal | None:
    return session.query(Proposal).filter_by(audit_id=audit_id).one_or_none()


def load_latest_for_company(session: Session, company_id: UUID) -> Proposal | None:
    return (
        session.query(Proposal)
        .filter_by(company_id=company_id)
        .order_by(Proposal.created_at.desc())
        .first()
    )


def create_or_replace_proposal(
    session: Session,
    audit_id: UUID,
    settings: Settings | None = None,
) -> Proposal:
    resolved = settings or get_settings()
    audit = (
        session.query(Audit)
        .options(
            selectinload(Audit.findings),
            selectinload(Audit.website).selectinload(Website.company),
            selectinload(Audit.website_score),
            selectinload(Audit.opportunity_score),
            selectinload(Audit.proposal),
        )
        .filter(Audit.id == audit_id)
        .one_or_none()
    )
    if audit is None:
        raise ProposalServiceError("Audit non trovato.", status_code=404)
    if audit.status != "completed":
        raise ProposalServiceError("La proposta richiede un audit completato.", status_code=409)

    website = audit.website
    company: Company | None = website.company if website else None
    sender = profile_view(get_or_create_sender_profile(session))
    draft = build_proposal_draft(
        domain=website.domain if website else audit.request_url,
        url=website.normalized_url if website else audit.request_url,
        company_name=company.name if company else None,
        city=company.city if company else None,
        findings=audit.findings,
        website_score=audit.website_score,
        opportunity_score=audit.opportunity_score,
        sender=sender,
    )
    source = "deterministic"
    polished = polish_proposal(resolved, draft, _facts(audit, company, draft, sender), sender)
    if polished is not None:
        draft = polished
        source = "ai"

    existing = audit.proposal
    if existing is not None:
        _apply(existing, draft, source, company.id if company else None, kind="refactor")
        session.commit()
        session.refresh(existing)
        return existing

    proposal = Proposal(
        audit_id=audit.id,
        company_id=company.id if company else None,
        kind="refactor",
        source=source,
        prompt_version=PROMPT_VERSION,
        summary=draft.summary,
        priority_problems=draft.priority_problems,
        recommended_service=draft.recommended_service,
        strategy=draft.strategy,
        email_subject=draft.email_subject,
        email_body=draft.email_body,
        brief=draft.brief,
        range_min=draft.range_min,
        range_max=draft.range_max,
        currency=draft.currency,
        range_note=draft.range_note,
    )
    session.add(proposal)
    session.commit()
    session.refresh(proposal)
    return proposal


def create_or_replace_greenfield_proposal(
    session: Session,
    company_id: UUID,
    settings: Settings | None = None,
) -> Proposal:
    resolved = settings or get_settings()
    company = (
        session.query(Company)
        .options(selectinload(Company.websites))
        .filter(Company.id == company_id)
        .one_or_none()
    )
    if company is None:
        raise ProposalServiceError("Azienda non trovata.", status_code=404)
    if company.website_url or company.websites:
        raise ProposalServiceError(
            "Questa azienda ha già un sito: usa la proposta di refactor legata all'audit.",
            status_code=409,
        )

    score = get_growth_score(session, company.id) or compute_and_store_growth_score(session, company)
    sender = profile_view(get_or_create_sender_profile(session))
    draft = build_greenfield_proposal_draft(
        company_name=company.name,
        category=company.category,
        city=company.city,
        growth_score=score,
        sender=sender,
    )
    source = "deterministic"
    polished = polish_proposal(resolved, draft, _greenfield_facts(company, score, draft, sender), sender)
    if polished is not None:
        draft = polished
        source = "ai"

    existing = (
        session.query(Proposal)
        .filter_by(company_id=company.id, kind="greenfield")
        .order_by(Proposal.created_at.desc())
        .first()
    )
    if existing is not None:
        _apply(existing, draft, source, company.id, kind="greenfield")
        session.commit()
        session.refresh(existing)
        return existing

    proposal = Proposal(
        audit_id=None,
        company_id=company.id,
        kind="greenfield",
        source=source,
        prompt_version=PROMPT_VERSION,
        summary=draft.summary,
        priority_problems=draft.priority_problems,
        recommended_service=draft.recommended_service,
        strategy=draft.strategy,
        email_subject=draft.email_subject,
        email_body=draft.email_body,
        brief=draft.brief,
        range_min=draft.range_min,
        range_max=draft.range_max,
        currency=draft.currency,
        range_note=draft.range_note,
    )
    session.add(proposal)
    session.commit()
    session.refresh(proposal)
    return proposal


def _apply(
    proposal: Proposal,
    draft: ProposalDraft,
    source: str,
    company_id: UUID | None,
    *,
    kind: str,
) -> None:
    proposal.company_id = company_id
    proposal.kind = kind
    proposal.source = source
    proposal.prompt_version = PROMPT_VERSION
    proposal.summary = draft.summary
    proposal.priority_problems = draft.priority_problems
    proposal.recommended_service = draft.recommended_service
    proposal.strategy = draft.strategy
    proposal.email_subject = draft.email_subject
    proposal.email_body = draft.email_body
    proposal.brief = draft.brief
    proposal.range_min = draft.range_min
    proposal.range_max = draft.range_max
    proposal.currency = draft.currency
    proposal.range_note = draft.range_note


def _facts(audit: Audit, company: Company | None, draft: ProposalDraft, sender) -> dict:
    return {
        "domain": audit.website.domain if audit.website else None,
        "url": audit.website.normalized_url if audit.website else audit.request_url,
        "company_name": company.name if company else None,
        "city": company.city if company else None,
        "website_score": audit.website_score.overall_score if audit.website_score else None,
        "opportunity_score": audit.opportunity_score.opportunity_score if audit.opportunity_score else None,
        "priority": audit.opportunity_score.priority if audit.opportunity_score else None,
        "recommended_service": draft.recommended_service,
        "priority_problems": draft.priority_problems,
        "range_min": draft.range_min,
        "range_max": draft.range_max,
        "range_is_internal_only": True,
        "sender_profile": {
            "display_name": sender.display_name,
            "intro": sender.intro,
            "website_url": sender.website_url,
            "freelancer_links": [{"label": item.label, "url": item.url} for item in sender.freelancer_links],
            "social_links": [{"label": item.label, "url": item.url} for item in sender.social_links],
        },
        "known_fields_only": True,
    }


def _greenfield_facts(company: Company, score, draft: ProposalDraft, sender) -> dict:
    return {
        "company_name": company.name,
        "category": company.category,
        "city": company.city,
        "has_website": False,
        "growth_score": score.score,
        "priority": score.priority,
        "recommended_service": draft.recommended_service,
        "priority_problems": draft.priority_problems,
        "range_min": draft.range_min,
        "range_max": draft.range_max,
        "range_is_internal_only": True,
        "sender_profile": {
            "display_name": sender.display_name,
            "intro": sender.intro,
            "website_url": sender.website_url,
            "freelancer_links": [{"label": item.label, "url": item.url} for item in sender.freelancer_links],
            "social_links": [{"label": item.label, "url": item.url} for item in sender.social_links],
        },
        "known_fields_only": True,
    }
