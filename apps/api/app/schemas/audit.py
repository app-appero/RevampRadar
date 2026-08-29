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


class WebsiteScoreResponse(BaseModel):
    overall_score: int
    technical_score: int
    performance_score: int
    ui_score: int | None
    ux_score: int
    mobile_score: int
    conversion_score: int
    seo_score: int
    trust_score: int
    explanation: str
    components: dict | None
    formula_version: str


class OpportunityScoreResponse(BaseModel):
    website_score: int
    business_score: int
    opportunity_score: int
    confidence: float
    priority: str
    explanation: str
    top_reasons: list[str]
    positive_factors: list[str]
    negative_factors: list[str]
    recommended_service: str
    components: dict | None
    formula_version: str


class AIAnalysisResponse(BaseModel):
    status: str
    prompt_version: str | None = None
    provider: str | None = None
    model: str | None = None
    reason: str | None = None
    error: str | None = None
    ui_score: int | None = None
    ux_score: int | None = None
    confidence: float | None = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    notes: str | None = None


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
    website_score: WebsiteScoreResponse | None = None
    opportunity_score: OpportunityScoreResponse | None = None
    ai_analysis: AIAnalysisResponse | None = None
