from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.discovery.service import (
    DiscoveryServiceError,
    create_discovery_run,
    execute_discovery,
    get_company,
    list_companies,
    load_discovery_run,
)
from app.jobs.bulk_scan import latest_bulk_scan
from app.models.entities import Company, DiscoveryRun
from app.schemas.discovery import (
    CompanyDetail,
    CompanySummary,
    CreateDiscoveryRequest,
    DiscoveryRunResponse,
)

router = APIRouter(tags=["discovery"])


@router.post("/discoveries", status_code=202, response_model=DiscoveryRunResponse)
def post_discovery(
    payload: CreateDiscoveryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> DiscoveryRunResponse:
    try:
        run = create_discovery_run(
            db,
            industry=payload.industry,
            location=payload.location,
            max_results=payload.max_results,
        )
    except DiscoveryServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    background_tasks.add_task(execute_discovery, run.id)
    loaded = load_discovery_run(db, run.id)
    assert loaded is not None
    return _run_response(db, loaded)


@router.get("/discoveries/{run_id}", response_model=DiscoveryRunResponse)
def get_discovery(run_id: UUID, db: Session = Depends(get_db)) -> DiscoveryRunResponse:
    run = load_discovery_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Discovery non trovata.")
    return _run_response(db, run)


@router.get("/companies", response_model=list[CompanySummary])
def get_companies(db: Session = Depends(get_db)) -> list[CompanySummary]:
    return [_company_summary(item) for item in list_companies(db)]


@router.get("/companies/{company_id}", response_model=CompanyDetail)
def get_company_detail(company_id: UUID, db: Session = Depends(get_db)) -> CompanyDetail:
    company = get_company(db, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Azienda non trovata.")
    return _company_detail(company)


def _run_response(db: Session, run: DiscoveryRun) -> DiscoveryRunResponse:
    companies = [_company_summary(item.company) for item in run.results if item.company is not None]
    latest = latest_bulk_scan(db, run.id)
    return DiscoveryRunResponse(
        id=run.id,
        industry=run.industry,
        location=run.location,
        max_results=run.max_results,
        provider=run.provider,
        status=run.status,
        total_found=run.total_found,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
        companies=companies,
        latest_scan_id=latest.id if latest else None,
    )


def _website(company: Company):
    return company.websites[0] if company.websites else None


def _company_summary(company: Company) -> CompanySummary:
    website = _website(company)
    return CompanySummary(
        id=company.id,
        name=company.name,
        category=company.category,
        city=company.city,
        region=company.region,
        country=company.country,
        website_url=company.website_url or (website.normalized_url if website else None),
        phone=company.phone,
        email=company.email,
        source=company.source,
        status=company.status,
        domain=website.domain if website else None,
    )


def _company_detail(company: Company) -> CompanyDetail:
    summary = _company_summary(company)
    website = _website(company)
    return CompanyDetail(
        **summary.model_dump(),
        external_id=company.external_id,
        created_at=company.created_at,
        website_id=website.id if website else None,
    )
