from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.jobs.bulk_enrich import (
    BulkEnrichError,
    EnrichJob,
    cancel_job,
    candidate_counts,
    get_job,
    run_job,
    start_job,
)

router = APIRouter(prefix="/enrichment", tags=["enrichment"])


class EnrichSelection(BaseModel):
    company_ids: list[UUID]


class EnrichCandidates(BaseModel):
    missing_city: int
    missing_website: int


class EnrichJobResponse(BaseModel):
    id: UUID
    kind: str
    status: str
    total: int
    processed: int
    updated: int
    not_found: int
    failed: int
    last_error: str | None


def _response(job: EnrichJob) -> EnrichJobResponse:
    return EnrichJobResponse(
        id=job.id,
        kind=job.kind,
        status=job.status,
        total=job.total,
        processed=job.processed,
        updated=job.updated,
        not_found=job.not_found,
        failed=job.failed,
        last_error=job.last_error,
    )


@router.get("/candidates", response_model=EnrichCandidates)
def get_candidates(db: Session = Depends(get_db)) -> EnrichCandidates:
    return EnrichCandidates(**candidate_counts(db))


@router.post("/{kind}", status_code=202, response_model=EnrichJobResponse)
def post_enrichment(
    kind: str,
    background_tasks: BackgroundTasks,
    payload: EnrichSelection | None = None,
    db: Session = Depends(get_db),
) -> EnrichJobResponse:
    try:
        job, created = start_job(db, kind, payload.company_ids if payload is not None else None)
    except BulkEnrichError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if created:
        background_tasks.add_task(run_job, job.id)
    return _response(job)


@router.get("/jobs/{job_id}", response_model=EnrichJobResponse)
def get_enrichment_job(job_id: UUID) -> EnrichJobResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job non trovato.")
    return _response(job)


@router.post("/selected/{kind}", status_code=202, response_model=EnrichJobResponse)
def post_selected_enrichment(
    kind: str, payload: EnrichSelection, background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> EnrichJobResponse:
    return post_enrichment(kind, background_tasks, payload, db)


@router.post("/jobs/{job_id}/cancel", response_model=EnrichJobResponse)
def cancel_enrichment(job_id: UUID) -> EnrichJobResponse:
    job = cancel_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job non trovato.")
    return _response(job)
