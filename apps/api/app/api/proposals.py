from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.entities import Proposal
from app.proposals.service import (
    ProposalServiceError,
    create_or_replace_greenfield_proposal,
    create_or_replace_proposal,
    load_latest_for_company,
    load_proposal_for_audit,
)
from app.schemas.proposal import ProblemItem, ProposalResponse

router = APIRouter(tags=["proposals"])


@router.post("/audits/{audit_id}/proposal", response_model=ProposalResponse)
def post_proposal(
    audit_id: UUID,
    use_ai: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ProposalResponse:
    try:
        proposal = create_or_replace_proposal(db, audit_id, use_ai=use_ai)
    except ProposalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _to_response(proposal)


@router.get("/audits/{audit_id}/proposal", response_model=ProposalResponse)
def get_audit_proposal(audit_id: UUID, db: Session = Depends(get_db)) -> ProposalResponse:
    proposal = load_proposal_for_audit(db, audit_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposta non trovata.")
    return _to_response(proposal)


@router.get("/companies/{company_id}/proposal", response_model=ProposalResponse)
def get_company_proposal(company_id: UUID, db: Session = Depends(get_db)) -> ProposalResponse:
    proposal = load_latest_for_company(db, company_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposta non trovata.")
    return _to_response(proposal)


@router.post("/companies/{company_id}/greenfield-proposal", response_model=ProposalResponse)
def post_greenfield_proposal(
    company_id: UUID,
    use_ai: bool | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ProposalResponse:
    try:
        proposal = create_or_replace_greenfield_proposal(db, company_id, use_ai=use_ai)
    except ProposalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _to_response(proposal)


def _to_response(proposal: Proposal) -> ProposalResponse:
    return ProposalResponse(
        id=proposal.id,
        audit_id=proposal.audit_id,
        company_id=proposal.company_id,
        kind=proposal.kind,
        source=proposal.source,
        prompt_version=proposal.prompt_version,
        summary=proposal.summary,
        priority_problems=[ProblemItem(**item) for item in proposal.priority_problems],
        recommended_service=proposal.recommended_service,
        strategy=proposal.strategy,
        email_subject=proposal.email_subject,
        email_body=proposal.email_body,
        brief=proposal.brief,
        range_min=proposal.range_min,
        range_max=proposal.range_max,
        currency=proposal.currency,
        range_note=proposal.range_note,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
    )
