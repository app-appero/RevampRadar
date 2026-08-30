from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SocialLink(BaseModel):
    network: str
    url: str


class StoreLink(BaseModel):
    store: str
    url: str


class IntelligenceSignals(BaseModel):
    technologies: list[str] = Field(default_factory=list)
    analytics: list[str] = Field(default_factory=list)
    social: list[SocialLink] = Field(default_factory=list)
    app_links: list[StoreLink] = Field(default_factory=list)
    generator: str | None = None
    aging: list[str] = Field(default_factory=list)
    osm_stars: str | None = None
    has_phone: bool = False
    has_email: bool = False
    has_website: bool = False


class IntelligenceHistory(BaseModel):
    previous_audit_id: UUID
    previous_completed_at: datetime | None
    website_score_delta: int | None
    opportunity_score_delta: int | None
    new_finding_codes: list[str]
    resolved_finding_codes: list[str]


class IntelligenceMonitoring(BaseModel):
    last_completed_at: datetime | None
    days_since: int | None
    stale: bool


class IntelligenceResponse(BaseModel):
    company_id: UUID | None
    audit_id: UUID | None
    signals: IntelligenceSignals
    history: IntelligenceHistory | None
    monitoring: IntelligenceMonitoring
