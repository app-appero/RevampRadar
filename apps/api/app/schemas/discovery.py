from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


MAX_RESULTS_STANDARD = 50
MAX_RESULTS_EXTENDED = 200


class ItalyProvince(BaseModel):
    name: str
    cities: list[str]


class ItalyRegion(BaseModel):
    name: str
    provinces: list[ItalyProvince]


class DiscoveryCatalog(BaseModel):
    sectors: list[str]
    regions: list[ItalyRegion]


class OsmIndustryPreview(BaseModel):
    industry: str
    mapped: bool
    tags: list[str]
    examples: list[str]
    sectors: list[str] = Field(default_factory=list)


class CreateDiscoveryRequest(BaseModel):
    industry: str = Field(default="", max_length=128)
    location: str = Field(default="", max_length=255)
    region: str = Field(default="", max_length=128)
    province: str = Field(default="", max_length=128)
    city: str = Field(default="", max_length=128)
    max_results: int = Field(default=20, ge=1, le=MAX_RESULTS_EXTENDED)
    extended: bool = False


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
    osm_tags: dict[str, str] | None = None
    osm_start_date: str | None = None
    osm_opening_hours: str | None = None


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
    progress_percent: int = 0
    progress_label: str | None = None


class DiscoveryRunResponse(BaseModel):
    id: UUID
    industry: str
    location: str
    max_results: int
    extended: bool = False
    provider: str
    status: str
    total_found: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    progress_percent: int = 0
    progress_label: str | None = None
    osm_tags: list[str] = Field(default_factory=list)
    companies: list[CompanySummary]
    latest_scan_id: UUID | None = None
