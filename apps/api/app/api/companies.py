"""Inserimento manuale di aziende nel CRM, senza analisi."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.discovery import _company_detail
from app.db import get_db
from app.schemas.company_manual import (
    CompanyImportRequest,
    CompanyImportResponse,
    CompanyMatchItem,
    CompanyMatchResponse,
    InstagramImportRequest,
    InstagramImportResponse,
    ManualCompanyCreate,
    ManualCompanyResponse,
)
from app.services.company_manual import (
    ManualCompanyError,
    create_manual_company,
    import_companies,
    preview_companies,
)
from app.services.company_match import MatchQuery, find_matches, normalized_query, strength
from app.services.crm_service import company_domains
from app.services.instagram import effective_instagram_handle
from app.services.instagram_import import import_instagram_handles

router = APIRouter(tags=["companies"])


@router.get(
    "/companies/match",
    response_model=CompanyMatchResponse,
    summary="Possibili duplicati con punteggio",
    description=(
        "Cerca aziende già presenti che corrispondono ai dati indicati, senza scaricare la pipeline. "
        "Handle Instagram, email, dominio (o stessa pagina sugli host condivisi) e telefono si "
        "confrontano esatti dopo la normalizzazione, mai come pezzi di testo. Il nome si confronta senza "
        "forma giuridica e articoli, anche con l'handle e il nome del sito; `city` alza o abbassa solo "
        "le corrispondenze per nome. Risultati da 50 in su, dal più alto."
    ),
)
def get_company_match(
    db: Session = Depends(get_db),
    name: str | None = Query(default=None, max_length=255),
    instagram: str | None = Query(default=None, max_length=255, description="«@nome», «nome» o URL del profilo."),
    domain: str | None = Query(default=None, max_length=2048, description="Dominio o URL del sito."),
    email: str | None = Query(default=None, max_length=255),
    phone: str | None = Query(default=None, max_length=64),
    city: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=10, ge=1, le=50),
    min_score: int = Query(default=50, ge=1, le=100),
) -> CompanyMatchResponse:
    if not any(value and value.strip() for value in (name, instagram, domain, email, phone)):
        raise HTTPException(status_code=422, detail="Indica almeno uno fra name, instagram, domain, email, phone.")
    query = MatchQuery(name=name, instagram=instagram, domain=domain, email=email, phone=phone, city=city)
    found = find_matches(db, query, limit=limit, min_score=min_score)
    return CompanyMatchResponse(
        normalized=normalized_query(query),
        matches=[
            CompanyMatchItem(
                company_id=item.company.id,
                opportunity_id=item.company.opportunity.id if item.company.opportunity else None,
                name=item.company.name,
                city=item.company.city,
                status=item.company.opportunity.status if item.company.opportunity else None,
                instagram_handle=effective_instagram_handle(item.company),
                domains=sorted(company_domains(item.company)),
                email=item.company.email,
                phone=item.company.phone,
                score=item.score,
                strength=strength(item.score),  # type: ignore[arg-type]
                reasons=item.reasons,
            )
            for item in found
        ],
    )


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


@router.post(
    "/companies/instagram-import",
    response_model=InstagramImportResponse,
    summary="Importa profili Instagram trovati fuori dall'app",
    description=(
        "Lista di handle o URL Instagram (stringhe o oggetti con nome, città, data ultimo post). Crea solo "
        "le schede nuove; segnala come `duplicate` (con l'id esistente) i profili già in CRM e quelli "
        "ripetuti nella lista, come `invalid` quelli non validi. `dry_run=true` = anteprima. Nessuna "
        "chiamata esterna."
    ),
)
def post_instagram_import(payload: InstagramImportRequest, db: Session = Depends(get_db)) -> InstagramImportResponse:
    return import_instagram_handles(db, payload)


@router.post(
    "/companies",
    response_model=ManualCompanyResponse,
    responses={
        409: {
            "description": (
                "`outcome: duplicate`: stesso handle Instagram, dominio o email di un'azienda esistente "
                "(`company_id` è quella esistente). `outcome: conflict`: corrispondenza ambigua."
            )
        }
    },
)
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
    status_code = {"created": 201, "conflict": 409, "duplicate": 409}.get(outcome, 200)
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))
