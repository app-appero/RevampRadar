from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BulkScanProgress(BaseModel):
    total: int
    pending: int
    running: int
    completed: int
    failed: int
    skipped: int


class BulkScanItemResponse(BaseModel):
    id: UUID
    company_id: UUID
    company_name: str
    city: str | None
    domain: str | None
    status: str
    attempts: int
    last_error: str | None
    audit_id: UUID | None
    website_score: int | None = None
    opportunity_score: int | None = None
    priority: str | None = None
    recommended_service: str | None = None


class BulkScanResponse(BaseModel):
    id: UUID
    discovery_run_id: UUID
    status: str
    max_attempts: int
    concurrency: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    progress: BulkScanProgress
    items: list[BulkScanItemResponse]


class BulkScanSummary(BaseModel):
    id: UUID
    status: str
    progress: BulkScanProgress
