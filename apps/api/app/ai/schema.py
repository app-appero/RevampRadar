from typing import Literal

from pydantic import BaseModel, Field


class AIFinding(BaseModel):
    category: str
    severity: Literal["low", "medium", "high", "critical"]
    code: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    description: str
    evidence: str
    recommendation: str
    kind: Literal["observation", "inference"] = "observation"


class AIAnalysisResult(BaseModel):
    ui_score: int | None = Field(default=None, ge=0, le=100)
    ux_score: int | None = Field(default=None, ge=0, le=100)
    mobile_usability_score: int | None = Field(default=None, ge=0, le=100)
    conversion_score: int | None = Field(default=None, ge=0, le=100)
    copy_score: int | None = Field(default=None, ge=0, le=100)
    trust_score: int | None = Field(default=None, ge=0, le=100)
    findings: list[AIFinding] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    notes: str | None = None
