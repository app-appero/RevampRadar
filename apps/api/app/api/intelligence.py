from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.intelligence import IntelligenceResponse
from app.services.intelligence import intelligence_for_audit, intelligence_for_company

router = APIRouter(tags=["intelligence"])


@router.get("/audits/{audit_id}/intelligence", response_model=IntelligenceResponse)
def get_audit_intelligence(audit_id: UUID, db: Session = Depends(get_db)) -> IntelligenceResponse:
    data = intelligence_for_audit(db, audit_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Intelligence disponibile solo per audit completati.")
    return IntelligenceResponse.model_validate(data)


@router.get("/companies/{company_id}/intelligence", response_model=IntelligenceResponse)
def get_company_intelligence(company_id: UUID, db: Session = Depends(get_db)) -> IntelligenceResponse:
    data = intelligence_for_company(db, company_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Azienda non trovata.")
    return IntelligenceResponse.model_validate(data)
