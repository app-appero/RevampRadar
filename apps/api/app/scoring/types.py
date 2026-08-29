from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class ScoreFinding(Protocol):
    category: str
    severity: str
    code: str
    title: str


@dataclass(frozen=True)
class WebsiteScoreDraft:
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
    components: dict


@dataclass(frozen=True)
class BusinessScoreDraft:
    score: int
    confidence: float
    explanation: str
    positive_factors: list[str]
    negative_factors: list[str]


@dataclass(frozen=True)
class OpportunityScoreDraft:
    website_score: int
    business_score: int
    opportunity_score: int
    confidence: float
    priority: str
    recommended_service: str
    explanation: str
    top_reasons: list[str]
    positive_factors: list[str]
    negative_factors: list[str]
    components: dict


def findings_in(findings: Sequence[ScoreFinding], *categories: str) -> list[ScoreFinding]:
    wanted = set(categories)
    return [item for item in findings if item.category in wanted]


def has_code(findings: Sequence[ScoreFinding], code: str) -> bool:
    return any(item.code == code for item in findings)
