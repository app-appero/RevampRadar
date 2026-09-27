from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.concept.service import ConceptError, delete_concept, generate_new_concept, get_concept, list_concepts
from app.db import get_db
from app.models.entities import Concept
from app.schemas.concept import ConceptSummary, DesignBriefResponse, DesignBriefUpdate
from app.services.design_brief_service import (
    DesignBriefError,
    get_or_create_design_brief,
    regenerate_design_brief,
    update_design_brief,
)

router = APIRouter(tags=["concept"])


@router.get("/companies/{company_id}/design-brief", response_model=DesignBriefResponse)
def get_design_brief(company_id: UUID, db: Session = Depends(get_db)) -> DesignBriefResponse:
    try:
        brief = get_or_create_design_brief(db, company_id)
    except DesignBriefError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _design_brief_response(brief)


@router.put("/companies/{company_id}/design-brief", response_model=DesignBriefResponse)
def put_design_brief(
    company_id: UUID,
    payload: DesignBriefUpdate,
    db: Session = Depends(get_db),
) -> DesignBriefResponse:
    try:
        brief = update_design_brief(db, company_id, payload)
    except DesignBriefError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _design_brief_response(brief)


@router.post("/companies/{company_id}/design-brief/regenerate", response_model=DesignBriefResponse)
def post_regenerate_design_brief(company_id: UUID, db: Session = Depends(get_db)) -> DesignBriefResponse:
    try:
        brief = regenerate_design_brief(db, company_id)
    except DesignBriefError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _design_brief_response(brief)


@router.get("/companies/{company_id}/concepts", response_model=list[ConceptSummary])
def get_concepts(company_id: UUID, db: Session = Depends(get_db)) -> list[ConceptSummary]:
    return [_concept_summary(item) for item in list_concepts(db, company_id)]


@router.post("/companies/{company_id}/concepts", status_code=201, response_model=ConceptSummary)
def post_generate_concept(company_id: UUID, db: Session = Depends(get_db)) -> ConceptSummary:
    try:
        concept = generate_new_concept(db, company_id)
    except ConceptError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _concept_summary(concept)


@router.delete("/companies/{company_id}/concepts/{concept_id}", status_code=204)
def delete_concept_endpoint(company_id: UUID, concept_id: UUID, db: Session = Depends(get_db)) -> None:
    try:
        delete_concept(db, company_id, concept_id)
    except ConceptError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/companies/{company_id}/concepts/{concept_id}/files/{filename}")
def get_concept_file(
    company_id: UUID,
    concept_id: UUID,
    filename: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    concept = get_concept(db, company_id, concept_id)
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept non trovato.")
    if filename not in {"index.html", "styles.css"}:
        raise HTTPException(status_code=404, detail="File non disponibile.")
    path = Path(concept.html_path).parent / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File non disponibile.")
    media_type = "text/html" if filename.endswith(".html") else "text/css"
    return FileResponse(path, media_type=media_type)


def _design_brief_response(brief) -> DesignBriefResponse:
    return DesignBriefResponse(
        style=brief.style,
        palette=brief.palette,
        typography=brief.typography,
        tone_of_voice=brief.tone_of_voice,
        spacing=brief.spacing,
        border_radius=brief.border_radius,
        image_treatment=brief.image_treatment,
        primary_cta=brief.primary_cta,
        notes=brief.notes,
        source=brief.source,
        updated_at=brief.updated_at,
    )


def _concept_summary(concept: Concept) -> ConceptSummary:
    return ConceptSummary(
        id=concept.id,
        version=concept.version,
        status=concept.status,
        is_current=concept.is_current,
        source=concept.source,
        generator_version=concept.generator_version,
        sections=concept.sections,
        error_message=concept.error_message,
        created_at=concept.created_at,
        updated_at=concept.updated_at,
        open_url=f"/companies/{concept.company_id}/concepts/{concept.id}/files/index.html",
    )
