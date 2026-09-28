from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deep_research.service import (
    DeepResearchError,
    execute_research,
    get_or_create_research,
    refresh_stale_status,
    start_research,
)
from app.models.entities import BusinessSignal, Company, CompanyResearch
from app.schemas.deep_research import (
    BusinessSignalCreate,
    BusinessSignalResponse,
    CompanyResearchResponse,
)
from app.services.business_signals import (
    BusinessSignalError,
    delete_business_signal,
    list_business_signals,
    upsert_business_signal,
)

router = APIRouter(tags=["deep-research"])


@router.post("/companies/{company_id}/research", status_code=202, response_model=CompanyResearchResponse)
def post_start_research(
    company_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CompanyResearchResponse:
    try:
        research = start_research(db, company_id)
    except DeepResearchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    background_tasks.add_task(execute_research, company_id)
    return _research_response(research)


@router.get("/companies/{company_id}/research", response_model=CompanyResearchResponse)
def get_company_research(company_id: UUID, db: Session = Depends(get_db)) -> CompanyResearchResponse:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Azienda non trovata.")
    research = get_or_create_research(db, company_id)
    research = refresh_stale_status(db, research, company)
    return _research_response(research)


@router.get("/companies/{company_id}/business-signals", response_model=list[BusinessSignalResponse])
def get_business_signals(company_id: UUID, db: Session = Depends(get_db)) -> list[BusinessSignalResponse]:
    return [_signal_response(item) for item in list_business_signals(db, company_id)]


@router.put("/companies/{company_id}/business-signals", response_model=BusinessSignalResponse)
def put_business_signal(
    company_id: UUID,
    payload: BusinessSignalCreate,
    db: Session = Depends(get_db),
) -> BusinessSignalResponse:
    try:
        signal = upsert_business_signal(db, company_id, payload)
    except BusinessSignalError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _signal_response(signal)


@router.delete("/companies/{company_id}/business-signals/{signal_id}", status_code=204)
def delete_business_signal_endpoint(
    company_id: UUID,
    signal_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_business_signal(db, company_id, signal_id)
    except BusinessSignalError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _research_response(research: CompanyResearch) -> CompanyResearchResponse:
    return CompanyResearchResponse(
        company_id=research.company_id,
        status=research.status,
        started_at=research.started_at,
        completed_at=research.completed_at,
        error_message=research.error_message,
        progress_percent=research.progress_percent,
        progress_label=research.progress_label,
        website_findings=research.website_findings,
        digital_presence=research.digital_presence,
        social_signals=research.social_signals,
        external_sources=research.external_sources,
        brief=research.brief,
        research_version=research.research_version,
        updated_at=research.updated_at,
    )


def _signal_response(signal: BusinessSignal) -> BusinessSignalResponse:
    return BusinessSignalResponse(
        id=signal.id,
        key=signal.key,
        period=signal.period,
        label=signal.label,
        value=signal.value,
        unit=signal.unit,
        source=signal.source,
        source_url=signal.source_url,
        observed_at=signal.observed_at,
        confidence=signal.confidence,
        is_manual=signal.is_manual,
        created_at=signal.created_at,
        updated_at=signal.updated_at,
    )
