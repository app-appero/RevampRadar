from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GrowthScoreResponse(BaseModel):
    id: UUID
    company_id: UUID
    score: int
    priority: str
    confidence: float
    explanation: str
    top_reasons: list[str]
    positive_factors: list[str]
    negative_factors: list[str]
    recommended_service: str
    components: dict | None
    peer_sample_size: int
    formula_version: str
    created_at: datetime
    updated_at: datetime
