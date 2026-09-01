from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.discovery.normalize import normalize_candidate
from app.discovery.provider import get_discovery_provider
from app.discovery.types import DiscoveryCandidate
from app.models.entities import Company, DiscoveryResult, DiscoveryRun, Website
from app.scanner.url import UrlValidationError, normalize_url
from app.schemas.discovery import MAX_RESULTS_EXTENDED, MAX_RESULTS_STANDARD


class DiscoveryServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def create_discovery_run(
    session: Session,
    *,
    industry: str,
    location: str,
    max_results: int,
    provider_name: str = "openstreetmap",
    extended: bool = False,
) -> DiscoveryRun:
    industry_value = industry.strip() or "tutti"
    location_value = location.strip() or "Italia"
    cap = MAX_RESULTS_EXTENDED if extended else MAX_RESULTS_STANDARD
    if max_results < 1 or max_results > cap:
        raise DiscoveryServiceError(
            f"max_results deve essere tra 1 e {cap}"
            + (" con ricerca estesa." if extended else " (usa ricerca estesa per arrivare a 200)."),
            status_code=422,
        )
    run = DiscoveryRun(
        industry=industry_value,
        location=location_value,
        max_results=max_results,
        extended=extended,
        provider=provider_name,
        status="queued",
        total_found=0,
        progress_percent=0,
        progress_label="In coda",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def execute_discovery(run_id: UUID, settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    from app.db import get_session_factory

    session = get_session_factory()()
    try:
        run = session.get(DiscoveryRun, run_id)
        if run is None:
            return
        run.status = "running"
        run.started_at = datetime.now(UTC)
        _set_progress(session, run, 8, "Avvio ricerca")
        _run_discovery(session, run, resolved)
        session.commit()
    except Exception as exc:
        session.rollback()
        run = session.get(DiscoveryRun, run_id)
        if run is not None:
            run.status = "failed"
            run.error_message = str(exc)
            run.completed_at = datetime.now(UTC)
            run.progress_label = run.progress_label or "Errore"
            session.commit()
        raise
    finally:
        session.close()


def load_discovery_run(session: Session, run_id: UUID) -> DiscoveryRun | None:
    return (
        session.query(DiscoveryRun)
        .options(
            selectinload(DiscoveryRun.results).selectinload(DiscoveryResult.company).selectinload(Company.websites)
        )
        .filter(DiscoveryRun.id == run_id)
        .one_or_none()
    )


def list_companies(session: Session) -> list[Company]:
    return (
        session.query(Company)
        .options(selectinload(Company.websites))
        .order_by(Company.created_at.desc())
        .all()
    )


def get_company(session: Session, company_id: UUID) -> Company | None:
    return (
        session.query(Company)
        .options(selectinload(Company.websites))
        .filter(Company.id == company_id)
        .one_or_none()
    )


def _set_progress(session: Session, run: DiscoveryRun, percent: int, label: str) -> None:
    run.progress_percent = max(0, min(100, percent))
    run.progress_label = label
    session.commit()


def _run_discovery(session: Session, run: DiscoveryRun, settings: Settings) -> None:
    from app.discovery.types import DiscoveryQuery

    provider = get_discovery_provider(settings)
    run.provider = provider.name
    query = DiscoveryQuery(
        industry=run.industry,
        location=run.location,
        max_results=run.max_results,
        include_without_website=bool(run.extended),
    )

    def on_stage(label: str) -> None:
        percent = 18 if "località" in label.lower() else 40
        _set_progress(session, run, percent, label)

    _set_progress(session, run, 12, "Ricerca OpenStreetMap")
    try:
        raw_candidates = provider.search_businesses(query, on_stage=on_stage)
    except TypeError:
        raw_candidates = provider.search_businesses(query)

    _set_progress(session, run, 55, "Normalizzazione risultati")
    persisted = 0
    seen_company_ids: set[UUID] = set()
    for raw in raw_candidates:
        candidate = normalize_candidate(raw)
        if candidate is None:
            continue
        company = _upsert_company(session, candidate)
        if company.id in seen_company_ids:
            continue
        already = (
            session.query(DiscoveryResult)
            .filter_by(discovery_run_id=run.id, company_id=company.id)
            .one_or_none()
        )
        if already is None:
            session.add(DiscoveryResult(discovery_run_id=run.id, company_id=company.id))
            persisted += 1
        seen_company_ids.add(company.id)
        cap = max(run.max_results, 1)
        percent = 55 + int(40 * min(persisted, cap) / cap)
        _set_progress(session, run, percent, f"Aziende trovate · {persisted}")
        if persisted >= run.max_results:
            break
    run.total_found = persisted
    run.status = "completed"
    run.progress_percent = 100
    if persisted == 0:
        from app.discovery.osm import empty_search_message

        run.error_message = empty_search_message(run.industry, run.location)
        run.progress_label = "Nessun risultato"
    else:
        run.progress_label = "Completata"
    run.completed_at = datetime.now(UTC)


def _upsert_company(session: Session, candidate: DiscoveryCandidate) -> Company:
    company = _find_duplicate(session, candidate)
    if company is None:
        company = Company(
            name=candidate.name,
            category=candidate.category,
            city=candidate.city,
            region=candidate.region,
            country=candidate.country,
            latitude=candidate.latitude,
            longitude=candidate.longitude,
            website_url=candidate.website_url,
            phone=candidate.phone,
            email=candidate.email,
            source=candidate.source,
            external_id=candidate.external_id,
            status="discovered",
            extra=candidate.extra,
        )
        session.add(company)
        session.flush()
        from app.services.crm_service import ensure_opportunity

        ensure_opportunity(session, company)
    else:
        _fill_missing(company, candidate)
    if candidate.website_url:
        _link_website(session, company, candidate.website_url)
    return company


def _find_duplicate(session: Session, candidate: DiscoveryCandidate) -> Company | None:
    if candidate.source and candidate.external_id:
        match = (
            session.query(Company)
            .filter_by(source=candidate.source, external_id=candidate.external_id)
            .one_or_none()
        )
        if match:
            return match
    if candidate.phone:
        match = session.query(Company).filter_by(phone=candidate.phone).one_or_none()
        if match:
            return match
    if candidate.website_url:
        try:
            normalized = normalize_url(candidate.website_url)
        except UrlValidationError:
            normalized = None
        if normalized:
            website = session.query(Website).filter_by(normalized_url=normalized.normalized).one_or_none()
            if website and website.company_id:
                return session.get(Company, website.company_id)
            website = session.query(Website).filter_by(domain=normalized.domain).one_or_none()
            if website and website.company_id:
                return session.get(Company, website.company_id)
    if candidate.name and candidate.city:
        return (
            session.query(Company)
            .filter(func.lower(Company.name) == candidate.name.lower())
            .filter(func.lower(Company.city) == candidate.city.lower())
            .one_or_none()
        )
    return None


def _fill_missing(company: Company, candidate: DiscoveryCandidate) -> None:
    if not company.category and candidate.category:
        company.category = candidate.category
    if not company.city and candidate.city:
        company.city = candidate.city
    if not company.region and candidate.region:
        company.region = candidate.region
    if not company.country and candidate.country:
        company.country = candidate.country
    if not company.website_url and candidate.website_url:
        company.website_url = candidate.website_url
    if not company.phone and candidate.phone:
        company.phone = candidate.phone
    if not company.email and candidate.email:
        company.email = candidate.email
    if not company.external_id and candidate.external_id:
        company.external_id = candidate.external_id
    if candidate.latitude is not None and candidate.longitude is not None:
        company.latitude = candidate.latitude
        company.longitude = candidate.longitude
    incoming = (candidate.extra or {}).get("osm_tags") if candidate.extra else None
    if isinstance(incoming, dict) and incoming:
        extra = dict(company.extra or {})
        current = extra.get("osm_tags") if isinstance(extra.get("osm_tags"), dict) else {}
        extra["osm_tags"] = {**current, **incoming}
        company.extra = extra


def _link_website(session: Session, company: Company, website_url: str) -> None:
    try:
        normalized = normalize_url(website_url)
    except UrlValidationError:
        return
    website = session.query(Website).filter_by(normalized_url=normalized.normalized).one_or_none()
    if website is None:
        website = session.query(Website).filter_by(domain=normalized.domain).one_or_none()
    if website is None:
        website = Website(
            company_id=company.id,
            url=normalized.original,
            normalized_url=normalized.normalized,
            domain=normalized.domain,
        )
        session.add(website)
        return
    if website.company_id is None:
        website.company_id = company.id
