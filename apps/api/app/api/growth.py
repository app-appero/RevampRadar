from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.entities import Company
from app.schemas.growth import GrowthScoreResponse
from app.services.growth_service import compute_and_store_growth_score, get_growth_score

router = APIRouter(tags=["growth"])


@router.get("/companies/{company_id}/growth-score", response_model=GrowthScoreResponse)
def get_company_growth_score(company_id: UUID, db: Session = Depends(get_db)) -> GrowthScoreResponse:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Azienda non trovata.")
    score = get_growth_score(db, company_id)
    if score is None:
        score = compute_and_store_growth_score(db, company)
        db.commit()
    return _to_response(score)


@router.post("/companies/{company_id}/growth-score", response_model=GrowthScoreResponse)
def post_company_growth_score(company_id: UUID, db: Session = Depends(get_db)) -> GrowthScoreResponse:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Azienda non trovata.")
    score = compute_and_store_growth_score(db, company)
    db.commit()
    return _to_response(score)


def _to_response(score) -> GrowthScoreResponse:
    return GrowthScoreResponse(
        id=score.id,
        company_id=score.company_id,
        score=score.score,
        priority=score.priority,
        confidence=score.confidence,
        explanation=score.explanation,
        top_reasons=score.top_reasons,
        positive_factors=score.positive_factors,
        negative_factors=score.negative_factors,
        recommended_service=score.recommended_service,
        components=score.components,
        peer_sample_size=score.peer_sample_size,
        formula_version=score.formula_version,
        created_at=score.created_at,
        updated_at=score.updated_at,
    )
