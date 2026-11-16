"""Inserimento manuale di aziende nel CRM, senza analisi."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.discovery import _company_detail
from app.db import get_db
from app.schemas.company_manual import (
    CompanyImportRequest,
    CompanyImportResponse,
    ManualCompanyCreate,
    ManualCompanyResponse,
)
from app.services.company_manual import (
    ManualCompanyError,
    create_manual_company,
    import_companies,
    preview_companies,
)

router = APIRouter(tags=["companies"])


@router.post("/companies/import/preview", response_model=CompanyImportResponse)
def preview_company_import(payload: CompanyImportRequest, db: Session = Depends(get_db)) -> CompanyImportResponse:
    """Anteprima senza modifiche: nuove, già presenti, ambigue, non valide, aggiornamenti."""
    return CompanyImportResponse(create_missing=True, dry_run=True, rows=preview_companies(db, payload.rows))


@router.post("/companies/import", response_model=CompanyImportResponse)
def post_company_import(payload: CompanyImportRequest, db: Session = Depends(get_db)) -> CompanyImportResponse:
    """Importa anagrafiche. Crea le mancanti solo con create_missing=true. Non avvia analisi."""
    try:
        rows = import_companies(db, payload.rows, create_missing=payload.create_missing)
    except ManualCompanyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return CompanyImportResponse(create_missing=payload.create_missing, dry_run=False, rows=rows)


@router.post("/companies", response_model=ManualCompanyResponse)
def post_company(payload: ManualCompanyCreate, db: Session = Depends(get_db)) -> JSONResponse:
    """Crea un'azienda e la sua Opportunity. Non avvia audit, scanner, AI o altre chiamate esterne."""
    try:
        outcome, company, candidates, warnings, error = create_manual_company(db, payload)
    except ManualCompanyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    body = ManualCompanyResponse(
        outcome=outcome,  # type: ignore[arg-type]
        company_id=company.id if company is not None else None,
        opportunity_id=company.opportunity.id if company is not None and company.opportunity is not None else None,
        status=company.opportunity.status if company is not None and company.opportunity is not None else None,
        error=error,
        warnings=warnings,
        candidates=candidates,
        company=_company_detail(company) if company is not None else None,
    )
    status_code = {"created": 201, "conflict": 409}.get(outcome, 200)
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))
