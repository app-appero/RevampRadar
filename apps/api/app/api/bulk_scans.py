from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.jobs.bulk_scan import (
    BulkScanError,
    create_bulk_scan,
    execute_bulk_scan,
    load_bulk_scan,
    ranked_items,
    retry_failed_items,
)
from app.models.entities import BulkScan, BulkScanItem
from app.schemas.bulk_scan import (
    BulkScanItemResponse,
    BulkScanProgress,
    BulkScanResponse,
)

router = APIRouter(tags=["bulk-scans"])


@router.post("/discoveries/{run_id}/scans", status_code=202, response_model=BulkScanResponse)
def post_bulk_scan(
    run_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> BulkScanResponse:
    try:
        scan = create_bulk_scan(db, run_id)
    except BulkScanError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if scan.status == "queued":
        background_tasks.add_task(execute_bulk_scan, scan.id)
    loaded = load_bulk_scan(db, scan.id)
    assert loaded is not None
    return _to_response(loaded)


@router.get("/bulk-scans/{scan_id}", response_model=BulkScanResponse)
def get_bulk_scan(scan_id: UUID, db: Session = Depends(get_db)) -> BulkScanResponse:
    scan = load_bulk_scan(db, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scansione non trovata.")
    return _to_response(scan)


@router.post("/bulk-scans/{scan_id}/retry-failed", status_code=202, response_model=BulkScanResponse)
def post_retry_failed(
    scan_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> BulkScanResponse:
    try:
        scan = retry_failed_items(db, scan_id)
    except BulkScanError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    background_tasks.add_task(execute_bulk_scan, scan.id)
    loaded = load_bulk_scan(db, scan.id)
    assert loaded is not None
    return _to_response(loaded)


def _to_response(scan: BulkScan) -> BulkScanResponse:
    items = ranked_items(scan)
    return BulkScanResponse(
        id=scan.id,
        discovery_run_id=scan.discovery_run_id,
        status=scan.status,
        max_attempts=scan.max_attempts,
        concurrency=scan.concurrency,
        error_message=scan.error_message,
        started_at=scan.started_at,
        completed_at=scan.completed_at,
        progress=_progress(scan),
        items=[_item_response(item) for item in items],
    )


def _progress(scan: BulkScan) -> BulkScanProgress:
    items = scan.items
    counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0, "skipped": 0}
    for item in items:
        if item.status in counts:
            counts[item.status] += 1
    total = len(items)
    done = counts["completed"] + counts["failed"] + counts["skipped"]
    if scan.status == "queued" or total == 0:
        percent = 0
        label = "In coda"
    elif scan.status in {"completed", "partial"}:
        percent = 100
        label = "Completata" if scan.status == "completed" else "Completata con errori"
    elif scan.status == "failed":
        percent = 100
        label = "Fallita"
    else:
        percent = min(99, round(100 * done / total))
        if counts["running"]:
            label = f"Analisi siti · {done}/{total} · {counts['running']} in corso"
        else:
            label = f"Analisi siti · {done}/{total}"
    return BulkScanProgress(total=total, percent=percent, label=label, **counts)


def _item_response(item: BulkScanItem) -> BulkScanItemResponse:
    company = item.company
    website = company.websites[0] if company and company.websites else None
    score = item.audit.opportunity_score if item.audit else None
    return BulkScanItemResponse(
        id=item.id,
        company_id=item.company_id,
        company_name=company.name if company else "—",
        city=company.city if company else None,
        domain=website.domain if website else None,
        status=item.status,
        attempts=item.attempts,
        last_error=item.last_error,
        audit_id=item.audit_id,
        website_score=score.website_score if score else None,
        opportunity_score=score.opportunity_score if score else None,
        priority=score.priority if score else None,
        recommended_service=score.recommended_service if score else None,
    )
