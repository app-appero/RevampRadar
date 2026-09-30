from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ResearchStatus = Literal["never", "in_progress", "completed", "partial", "failed", "stale"]
SignalConfidence = Literal["verified", "estimated", "manual", "unverified"]


class BusinessSignalCreate(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    period: str = Field(default="", max_length=16)
    label: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=2000)
    unit: str | None = Field(default=None, max_length=32)
    source: str = Field(min_length=1, max_length=2000)
    source_url: str | None = Field(default=None, max_length=2048)
    observed_at: datetime | None = None
    confidence: SignalConfidence = "manual"


class RegistryEnrichmentRequest(BaseModel):
    vat: str | None = Field(default=None, min_length=8, max_length=16)


class BusinessSignalResponse(BaseModel):
    id: UUID
    key: str
    period: str
    label: str
    value: str
    unit: str | None
    source: str
    source_url: str | None
    observed_at: datetime | None
    confidence: str
    is_manual: bool
    created_at: datetime
    updated_at: datetime


class CompanyResearchResponse(BaseModel):
    company_id: UUID
    status: ResearchStatus
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    progress_percent: int
    progress_label: str | None
    website_findings: dict | None
    digital_presence: dict | None
    social_signals: dict | None
    external_sources: list | None
    brief: dict | None
    research_version: str
    updated_at: datetime
