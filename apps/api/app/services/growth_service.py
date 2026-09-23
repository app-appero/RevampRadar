from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import Company, GrowthScore
from app.scoring.greenfield import compute_growth_score, rating_from_osm_tags

_PEER_LIMIT = 60


def compute_and_store_growth_score(session: Session, company: Company) -> GrowthScore:
    peer_total, peer_with_website = _peer_stats(session, company)
    draft = compute_growth_score(
        name=company.name,
        category=company.category,
        city=company.city,
        phone=company.phone,
        email=company.email,
        rating=rating_from_osm_tags(company.extra),
        peer_total=peer_total,
        peer_with_website=peer_with_website,
    )
    existing = session.query(GrowthScore).filter_by(company_id=company.id).one_or_none()
    if existing is None:
        existing = GrowthScore(company_id=company.id)
        session.add(existing)
    existing.score = draft.score
    existing.priority = draft.priority
    existing.confidence = draft.confidence
    existing.explanation = draft.explanation
    existing.top_reasons = draft.top_reasons
    existing.positive_factors = draft.positive_factors
    existing.negative_factors = draft.negative_factors
    existing.recommended_service = draft.recommended_service
    existing.components = draft.components
    existing.peer_sample_size = draft.peer_sample_size
    existing.formula_version = draft.formula_version
    session.flush()
    return existing


def get_growth_score(session: Session, company_id: UUID) -> GrowthScore | None:
    return session.query(GrowthScore).filter_by(company_id=company_id).one_or_none()


def latest_growth_scores_map(session: Session, company_ids: list[UUID]) -> dict[UUID, GrowthScore]:
    if not company_ids:
        return {}
    rows = session.query(GrowthScore).filter(GrowthScore.company_id.in_(company_ids)).all()
    return {row.company_id: row for row in rows}


def _peer_stats(session: Session, company: Company) -> tuple[int, int]:
    if not company.category:
        return (0, 0)
    q = session.query(Company).filter(
        func.lower(Company.category) == company.category.lower(),
        Company.id != company.id,
    )
    if company.city:
        q = q.filter(func.lower(Company.city) == company.city.lower())
    elif company.region:
        q = q.filter(func.lower(Company.region) == company.region.lower())
    peers = q.limit(_PEER_LIMIT).all()
    total = len(peers)
    with_website = sum(1 for peer in peers if peer.website_url)
    return (total, with_website)
