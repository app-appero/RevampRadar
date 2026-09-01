from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MapPoint(BaseModel):
    company_id: UUID
    name: str
    city: str | None
    category: str | None
    latitude: float
    longitude: float
    opportunity_score: int | None
    website_score: int | None
    priority: str | None
    has_app: bool
    has_website: bool
    cluster_id: int
    audit_id: UUID | None = None


class MapCluster(BaseModel):
    id: int
    size: int
    label: str
    centroid_lat: float
    centroid_lon: float
    avg_opportunity_score: float | None
    high_share: float
    app_share: float
    no_site_share: float = 0
    top_city: str | None
    top_category: str | None


class MapResponse(BaseModel):
    points: list[MapPoint]
    clusters: list[MapCluster]
    mapped_count: int
    unmapped_count: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BackfillResponse(BaseModel):
    updated: int
    skipped: int
    remaining: int
