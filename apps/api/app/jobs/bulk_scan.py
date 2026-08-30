from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.jobs.runner import run_concurrent
from app.models.entities import (
    Audit,
    BulkScan,
    BulkScanItem,
    Company,
    DiscoveryResult,
    DiscoveryRun,
)
from app.services.audit_service import AuditServiceError, create_audit, execute_audit


class BulkScanError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def create_bulk_scan(session: Session, discovery_run_id: UUID, settings: Settings | None = None) -> BulkScan:
    resolved = settings or get_settings()
    run = (
        session.query(DiscoveryRun)
        .options(selectinload(DiscoveryRun.results).selectinload(DiscoveryResult.company).selectinload(Company.websites))
        .filter(DiscoveryRun.id == discovery_run_id)
        .one_or_none()
    )
    if run is None:
        raise BulkScanError("Discovery non trovata.", status_code=404)
    if run.status != "completed":
        raise BulkScanError("La discovery deve essere completata prima della scansione in batch.", status_code=409)

    active = (
        session.query(BulkScan)
        .filter(BulkScan.discovery_run_id == discovery_run_id)
        .filter(BulkScan.status.in_(("queued", "running")))
        .one_or_none()
    )
    if active is not None:
        return active

    scan = BulkScan(
        discovery_run_id=run.id,
        status="queued",
        max_attempts=resolved.bulk_scan_max_attempts,
        concurrency=resolved.bulk_scan_concurrency,
    )
    session.add(scan)
    session.flush()
    for result in run.results:
        company = result.company
        url = _company_url(company)
        session.add(
            BulkScanItem(
                bulk_scan_id=scan.id,
                company_id=company.id,
                status="pending" if url else "skipped",
                attempts=0,
                last_error=None if url else "Nessun sito da analizzare.",
            )
        )
    session.commit()
    session.refresh(scan)
    return scan


def retry_failed_items(session: Session, scan_id: UUID) -> BulkScan:
    scan = session.get(BulkScan, scan_id)
    if scan is None:
        raise BulkScanError("Scansione non trovata.", status_code=404)
    if scan.status in {"queued", "running"}:
        raise BulkScanError("La scansione è già in corso.", status_code=409)
    failed = [item for item in scan.items if item.status == "failed"]
    if not failed:
        raise BulkScanError("Nessun elemento fallito da ritentare.", status_code=409)
    for item in failed:
        item.status = "pending"
        item.attempts = 0
        item.last_error = None
        item.audit_id = None
    scan.status = "queued"
    scan.error_message = None
    scan.started_at = None
    scan.completed_at = None
    session.commit()
    session.refresh(scan)
    return scan


def execute_bulk_scan(scan_id: UUID, settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    from app.db import get_session_factory

    factory = get_session_factory()
    session = factory()
    try:
        scan = session.get(BulkScan, scan_id)
        if scan is None:
            return
        scan.status = "running"
        scan.started_at = datetime.now(UTC)
        session.commit()
        concurrency = scan.concurrency
        max_attempts = scan.max_attempts
    finally:
        session.close()

    while True:
        session = factory()
        try:
            pending = [
                item.id
                for item in session.query(BulkScanItem).filter_by(bulk_scan_id=scan_id, status="pending").all()
            ]
        finally:
            session.close()
        if not pending:
            break
        run_concurrent(
            lambda item_id: _process_item(item_id, max_attempts, resolved),
            pending,
            concurrency,
        )

    session = factory()
    try:
        _finalize(session, scan_id)
        session.commit()
    finally:
        session.close()


def load_bulk_scan(session: Session, scan_id: UUID) -> BulkScan | None:
    return (
        session.query(BulkScan)
        .options(
            selectinload(BulkScan.items).selectinload(BulkScanItem.company).selectinload(Company.websites),
            selectinload(BulkScan.items).selectinload(BulkScanItem.audit).selectinload(Audit.opportunity_score),
        )
        .filter(BulkScan.id == scan_id)
        .one_or_none()
    )


def latest_bulk_scan(session: Session, discovery_run_id: UUID) -> BulkScan | None:
    return (
        session.query(BulkScan)
        .filter(BulkScan.discovery_run_id == discovery_run_id)
        .order_by(BulkScan.created_at.desc())
        .first()
    )


def ranked_items(scan: BulkScan) -> list[BulkScanItem]:
    def sort_key(item: BulkScanItem) -> tuple[int, int, str]:
        score = item.audit.opportunity_score if item.audit else None
        value = score.opportunity_score if score is not None else -1
        status_rank = 0 if item.status == "completed" else 1
        return (status_rank, -value, item.company.name.lower() if item.company else "")

    return sorted(scan.items, key=sort_key)


def _process_item(item_id: UUID, max_attempts: int, settings: Settings) -> None:
    from app.db import get_session_factory

    session = get_session_factory()()
    try:
        item = session.get(BulkScanItem, item_id)
        if item is None or item.status != "pending":
            return
        company = session.get(Company, item.company_id)
        url = _company_url(company)
        if not url:
            item.status = "skipped"
            item.last_error = "Nessun sito da analizzare."
            session.commit()
            return
        item.status = "running"
        item.attempts += 1
        session.commit()
        audit = None
        try:
            audit = create_audit(session, url, company.id if company else None)
            execute_audit(audit.id, settings)
        except AuditServiceError as exc:
            _mark_attempt(session, item, max_attempts, str(exc), audit.id if audit else None)
            return
        except Exception as exc:
            _mark_attempt(session, item, max_attempts, str(exc), audit.id if audit else None)
            return
        session.expire_all()
        audit = session.get(Audit, audit.id)
        if audit is not None and audit.status == "completed":
            item.status = "completed"
            item.audit_id = audit.id
            item.last_error = None
        else:
            message = audit.error_message if audit else "Audit fallito."
            _mark_attempt(session, item, max_attempts, message or "Audit fallito.", audit.id if audit else None)
        session.commit()
    finally:
        session.close()


def _mark_attempt(
    session: Session,
    item: BulkScanItem,
    max_attempts: int,
    error: str,
    audit_id: UUID | None,
) -> None:
    item.last_error = error[:2000]
    item.audit_id = audit_id
    if item.attempts < max_attempts:
        item.status = "pending"
    else:
        item.status = "failed"
    session.commit()


def _finalize(session: Session, scan_id: UUID) -> None:
    scan = session.get(BulkScan, scan_id)
    if scan is None:
        return
    items = session.query(BulkScanItem).filter_by(bulk_scan_id=scan_id).all()
    failed = sum(1 for item in items if item.status == "failed")
    completed = sum(1 for item in items if item.status == "completed")
    if failed and completed:
        scan.status = "partial"
    elif failed and not completed:
        scan.status = "failed"
        scan.error_message = "Tutte le analisi con sito sono fallite."
    else:
        scan.status = "completed"
    scan.completed_at = datetime.now(UTC)


def _company_url(company: Company | None) -> str | None:
    if company is None:
        return None
    if company.website_url:
        return company.website_url
    if company.websites:
        return company.websites[0].normalized_url
    return None
