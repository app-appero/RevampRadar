from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.discovery.italy_geo import compose_location, italy_geo
from app.discovery.osm import format_industry_tags, listed_sectors, preview_industry, social_contact_link
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
    DiscoveryCatalog,
    DiscoveryRunResponse,
    DiscoveryRunSummary,
    ItalyProvince,
    ItalyRegion,
    OsmIndustryPreview,
)


router = APIRouter(tags=["discovery"])


def _request_location(payload: CreateDiscoveryRequest) -> str:
    if payload.city.strip() or payload.province.strip() or payload.region.strip():
        return compose_location(
            region=payload.region,
            province=payload.province,
            city=payload.city,
        )
    return payload.location.strip()


@router.get("/discovery/osm-preview", response_model=OsmIndustryPreview)
def get_osm_preview(industry: str = Query("", max_length=128)) -> OsmIndustryPreview:
    payload = preview_industry(industry)
    return OsmIndustryPreview(**payload)


@router.get("/discovery/catalog", response_model=DiscoveryCatalog)
def get_discovery_catalog() -> DiscoveryCatalog:
    geo = italy_geo()
    regions = [
        ItalyRegion(
            name=region["name"],
            provinces=[
                ItalyProvince(name=province["name"], cities=province["cities"])
                for province in region.get("provinces") or []
            ],
        )
        for region in geo.get("regions") or []
    ]
    return DiscoveryCatalog(sectors=listed_sectors(), regions=regions)


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
            location=_request_location(payload),
            max_results=payload.max_results,
            extended=payload.extended,
        )
    except DiscoveryServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    background_tasks.add_task(execute_discovery, run.id)
    loaded = load_discovery_run(db, run.id)
    assert loaded is not None
    return _run_response(db, loaded)


@router.get("/discoveries", response_model=list[DiscoveryRunSummary])
def list_discoveries(
    limit: int = Query(8, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[DiscoveryRunSummary]:
    rows = db.query(DiscoveryRun).order_by(DiscoveryRun.created_at.desc()).limit(limit).all()
    return [
        DiscoveryRunSummary(
            id=item.id,
            industry=item.industry,
            location=item.location,
            status=item.status,
            total_found=item.total_found,
            created_at=item.created_at,
            completed_at=item.completed_at,
            progress_percent=item.progress_percent,
            progress_label=item.progress_label,
        )
        for item in rows
    ]


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
        extended=run.extended,
        provider=run.provider,
        status=run.status,
        total_found=run.total_found,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
        progress_percent=run.progress_percent,
        progress_label=run.progress_label,
        osm_tags=format_industry_tags(run.industry),
        companies=companies,
        latest_scan_id=latest.id if latest else None,
    )


def _website(company: Company):
    return company.websites[0] if company.websites else None


def _company_summary(company: Company) -> CompanySummary:
    website = _website(company)
    tags = _company_osm_tags(company)
    social = social_contact_link(tags)
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
        osm_tags=tags,
        osm_start_date=tags.get("start_date") if tags else None,
        osm_opening_hours=tags.get("opening_hours") if tags else None,
        social_label=social[0] if social else None,
        social_url=social[1] if social else None,
    )


def _company_osm_tags(company: Company) -> dict[str, str] | None:
    extra = company.extra or {}
    tags = extra.get("osm_tags")
    if not isinstance(tags, dict) or not tags:
        return None
    return {str(key): str(value) for key, value in tags.items()}


def _company_detail(company: Company) -> CompanyDetail:
    summary = _company_summary(company)
    website = _website(company)
    return CompanyDetail(
        **summary.model_dump(),
        external_id=company.external_id,
        created_at=company.created_at,
        website_id=website.id if website else None,
    )
