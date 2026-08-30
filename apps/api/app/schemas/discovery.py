from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateDiscoveryRequest(BaseModel):
    industry: str = Field(min_length=2, max_length=128)
    location: str = Field(min_length=2, max_length=255)
    max_results: int = Field(default=20, ge=1, le=50)


class CompanySummary(BaseModel):
    id: UUID
    name: str
    category: str | None
    city: str | None
    region: str | None
    country: str | None
    website_url: str | None
    phone: str | None
    email: str | None
    source: str
    status: str
    domain: str | None = None


class CompanyDetail(CompanySummary):
    external_id: str | None
    created_at: datetime
    website_id: UUID | None = None


class DiscoveryRunSummary(BaseModel):
    id: UUID
    industry: str
    location: str
    status: str
    total_found: int
    created_at: datetime
    completed_at: datetime | None = None


class DiscoveryRunResponse(BaseModel):
    id: UUID
    industry: str
    location: str
    max_results: int
    provider: str
    status: str
    total_found: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    companies: list[CompanySummary]
    latest_scan_id: UUID | None = None
