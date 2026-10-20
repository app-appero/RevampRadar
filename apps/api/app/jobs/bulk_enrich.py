from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.discovery.service import (
    DiscoveryServiceError,
    enrich_company_from_places,
    resolve_company_location,
)
from app.models.entities import Company, Website
from app.services.audit_service import create_audit, execute_audit

KINDS = ("city", "places", "analysis")
# Nominatim ammette ~1 richiesta/secondo; Google Places non ha bisogno di pause lunghe.
_DELAY_SECONDS = {"city": 1.1, "places": 0.1, "analysis": 0}
_MAX_CONSECUTIVE_ERRORS = 3


class BulkEnrichError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class EnrichJob:
    id: UUID
    kind: str
    total: int
    status: str = "running"
    processed: int = 0
    updated: int = 0
    not_found: int = 0
    failed: int = 0
    last_error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    company_ids: list[UUID] = field(default_factory=list)


# Stato in memoria: l'app è personale e l'API gira in un solo processo. Se il backend
# viene riavviato a metà, il job si perde ma i dati già salvati restano.
_JOBS: dict[UUID, EnrichJob] = {}
_LOCK = threading.Lock()


def _missing_website_filter(query):
    return (
        query.outerjoin(Website, Website.company_id == Company.id)
        .filter(or_(Company.website_url.is_(None), Company.website_url == ""))
        .filter(Website.id.is_(None))
    )


def city_candidates(session: Session) -> list[UUID]:
    query = (
        session.query(Company.id)
        .filter(or_(Company.city.is_(None), Company.city == ""))
        .filter(Company.latitude.is_not(None), Company.longitude.is_not(None))
    )
    return [row[0] for row in query.all()]


def places_candidates(session: Session) -> list[UUID]:
    query = _missing_website_filter(session.query(Company.id)).filter(Company.places_checked_at.is_(None))
    return [row[0] for row in query.distinct().all()]


def candidate_counts(session: Session) -> dict[str, int]:
    return {"missing_city": len(city_candidates(session)), "missing_website": len(places_candidates(session))}


def start_job(
    session: Session, kind: str, company_ids: list[UUID] | None = None,
) -> tuple[EnrichJob, bool]:
    """Un job per tipo; una selezione esplicita non può diventare globale."""
    if kind not in KINDS:
        raise BulkEnrichError("Tipo di recupero non valido.", status_code=422)
    if kind == "analysis" and company_ids is None:
        raise BulkEnrichError("Seleziona le aziende da analizzare.", status_code=422)
    if kind == "analysis":
        ids = [company.id for company in session.query(Company).filter(Company.id.in_(company_ids)).all()
               if company.website_url or company.websites]
    else:
        ids = city_candidates(session) if kind == "city" else places_candidates(session)
    if company_ids is not None:
        selected = set(company_ids)
        ids = [company_id for company_id in ids if company_id in selected]
    if not ids:
        raise BulkEnrichError("Nessuna azienda idonea nella selezione.", status_code=409)
    with _LOCK:
        for job in _JOBS.values():
            if job.kind == kind and job.status in {"running", "cancelling"}:
                if set(job.company_ids) == set(ids):
                    return job, False
                raise BulkEnrichError("Un'altra operazione dello stesso tipo è già in corso.", status_code=409)
        job = EnrichJob(id=uuid4(), kind=kind, total=len(ids), company_ids=ids)
        _JOBS[job.id] = job
    return job, True


def get_job(job_id: UUID) -> EnrichJob | None:
    with _LOCK:
        return _JOBS.get(job_id)


def cancel_job(job_id: UUID) -> EnrichJob | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is not None and job.status == "running":
            job.status = "cancelling"
        return job


def run_job(job_id: UUID, settings: Settings | None = None) -> None:
    from app.db import get_session_factory

    resolved = settings or get_settings()
    job = get_job(job_id)
    if job is None:
        return
    factory = get_session_factory()
    consecutive_errors = 0
    try:
        for company_id in job.company_ids:
            with _LOCK:
                if job.status == "cancelling":
                    job.status = "cancelled"
                    return
            session = factory()
            try:
                company = session.get(Company, company_id)
                if company is not None:
                    try:
                        if job.kind == "analysis":
                            url = company.website_url or company.websites[0].normalized_url
                            audit = create_audit(session, url, company.id)
                            execute_audit(audit.id, resolved)
                        elif job.kind == "city":
                            resolve_company_location(session, company, resolved)
                        else:
                            enrich_company_from_places(session, company, resolved)
                        job.updated += 1
                        consecutive_errors = 0
                    except DiscoveryServiceError as exc:
                        session.rollback()
                        if exc.status_code == 404:
                            job.not_found += 1
                            consecutive_errors = 0
                        else:
                            job.failed += 1
                            job.last_error = str(exc)
                            consecutive_errors += 1
                            # Chiave mancante o servizio che rifiuta ogni richiesta: inutile insistere.
                            if exc.status_code == 422 or consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                                job.processed += 1
                                job.status = "failed"
                                return
            except Exception as exc:  # noqa: BLE001 - registra errori e continua con le altre aziende
                session.rollback()
                job.failed += 1
                job.last_error = str(exc)
            finally:
                session.close()
            job.processed += 1
            time.sleep(_DELAY_SECONDS[job.kind])
        with _LOCK:
            job.status = "cancelled" if job.status == "cancelling" else "completed"
    except Exception as exc:  # noqa: BLE001 - il job non deve mai lasciare stato "running"
        job.status = "failed"
        job.last_error = str(exc)
    finally:
        job.finished_at = datetime.now(UTC)
