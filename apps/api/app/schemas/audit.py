from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateAuditRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class FindingResponse(BaseModel):
    id: UUID
    category: str
    severity: str
    code: str
    title: str
    description: str
    evidence: str | None
    recommendation: str
    source_type: str


class ScreenshotResponse(BaseModel):
    id: UUID
    device: str
    viewport_width: int
    viewport_height: int
    url: str


class AuditResponse(BaseModel):
    id: UUID
    status: str
    request_url: str
    normalized_url: str
    domain: str
    scanner_version: str
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    http: dict | None
    html: dict | None
    seo: dict | None
    performance: dict | None
    findings: list[FindingResponse]
    screenshots: list[ScreenshotResponse]
