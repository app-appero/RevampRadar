from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.entities import Audit
from app.schemas.audit import (
    AuditResponse,
    CreateAuditRequest,
    FindingResponse,
    ScreenshotResponse,
)
from app.services.audit_service import AuditServiceError, create_audit, execute_audit

router = APIRouter(prefix="/audits", tags=["audits"])


@router.post("", status_code=202, response_model=AuditResponse)
def post_audit(
    payload: CreateAuditRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> AuditResponse:
    try:
        audit = create_audit(db, payload.url)
    except AuditServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    background_tasks.add_task(execute_audit, audit.id)
    audit = _load_audit(db, audit.id)
    assert audit is not None
    return _to_response(audit)


@router.get("/{audit_id}", response_model=AuditResponse)
def get_audit(audit_id: UUID, db: Session = Depends(get_db)) -> AuditResponse:
    audit = _load_audit(db, audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Audit non trovato.")
    return _to_response(audit)


@router.get("/{audit_id}/screenshots/{device}")
def get_screenshot(audit_id: UUID, device: str, db: Session = Depends(get_db)) -> FileResponse:
    audit = _load_audit(db, audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Audit non trovato.")
    screenshot = next((item for item in audit.screenshots if item.device == device), None)
    if screenshot is None or not Path(screenshot.file_path).exists():
        raise HTTPException(status_code=404, detail="Screenshot non disponibile.")
    return FileResponse(screenshot.file_path, media_type="image/png")


def _load_audit(db: Session, audit_id: UUID) -> Audit | None:
    return (
        db.query(Audit)
        .options(selectinload(Audit.findings), selectinload(Audit.screenshots), selectinload(Audit.website))
        .filter(Audit.id == audit_id)
        .one_or_none()
    )


def _to_response(audit: Audit) -> AuditResponse:
    return AuditResponse(
        id=audit.id,
        status=audit.status,
        request_url=audit.request_url,
        normalized_url=audit.website.normalized_url,
        domain=audit.website.domain,
        scanner_version=audit.scanner_version,
        started_at=audit.started_at,
        completed_at=audit.completed_at,
        error_message=audit.error_message,
        http=audit.http_data,
        html=audit.html_data,
        seo=audit.seo_data,
        performance=audit.performance_data,
        findings=[
            FindingResponse(
                id=item.id,
                category=item.category,
                severity=item.severity,
                code=item.code,
                title=item.title,
                description=item.description,
                evidence=item.evidence,
                recommendation=item.recommendation,
                source_type=item.source_type,
            )
            for item in sorted(audit.findings, key=_severity_rank)
        ],
        screenshots=[
            ScreenshotResponse(
                id=item.id,
                device=item.device,
                viewport_width=item.viewport_width,
                viewport_height=item.viewport_height,
                url=f"/audits/{audit.id}/screenshots/{item.device}",
            )
            for item in audit.screenshots
        ],
    )


def _severity_rank(finding) -> tuple[int, str]:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    return (order.get(finding.severity, 9), finding.code)
