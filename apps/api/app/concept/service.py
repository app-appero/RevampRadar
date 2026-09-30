"""Persistenza e versionamento del Concept Homepage HTML.

Ogni generazione crea una nuova versione su disco (data/concepts/{company}/{concept}/)
e in DB; la versione precedente resta consultabile, non viene cancellata.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.concept import GENERATOR_VERSION
from app.concept.generator import generate_concept
from app.config import Settings, get_settings
from app.deep_research.service import get_research
from app.models.entities import Company, Concept, DesignBrief
from app.services.design_brief_service import get_or_create_design_brief


class ConceptError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def list_concepts(session: Session, company_id: UUID) -> list[Concept]:
    return session.query(Concept).filter_by(company_id=company_id).order_by(Concept.version.desc()).all()


def get_concept(session: Session, company_id: UUID, concept_id: UUID) -> Concept | None:
    return session.query(Concept).filter_by(company_id=company_id, id=concept_id).one_or_none()


def _design_brief_dict(brief: DesignBrief) -> dict:
    return {
        "style": brief.style,
        "palette": brief.palette,
        "typography": brief.typography,
        "tone_of_voice": brief.tone_of_voice,
        "spacing": brief.spacing,
        "border_radius": brief.border_radius,
        "image_treatment": brief.image_treatment,
        "primary_cta": brief.primary_cta,
    }


def generate_new_concept(session: Session, company_id: UUID, settings: Settings | None = None) -> Concept:
    resolved = settings or get_settings()
    company = session.get(Company, company_id)
    if company is None:
        raise ConceptError("Azienda non trovata.", status_code=404)

    research = get_research(session, company_id)
    if research is None or research.status in {"never", "in_progress"}:
        raise ConceptError(
            "Serve prima un 'Approfondisci prospect' completato (anche parzialmente).",
            status_code=409,
        )

    design_brief_row = get_or_create_design_brief(session, company_id)
    design_brief_dict = _design_brief_dict(design_brief_row)

    output = generate_concept(company, research.brief, design_brief_dict)

    previous_current = session.query(Concept).filter_by(company_id=company_id, is_current=True).all()
    next_version = session.query(Concept).filter_by(company_id=company_id).count() + 1

    concept = Concept(
        company_id=company_id,
        version=next_version,
        status="ready",
        is_current=True,
        html_path="",
        css_path="",
        sections=output.sections,
        design_brief_snapshot=design_brief_dict,
        company_brief_snapshot=research.brief,
        generator_version=GENERATOR_VERSION,
        source="deterministic",
        error_message=None,
    )
    session.add(concept)
    session.flush()

    concept_dir = Path(resolved.concept_dir) / str(company_id) / str(concept.id)
    concept_dir.mkdir(parents=True, exist_ok=True)
    html_path = concept_dir / "index.html"
    css_path = concept_dir / "styles.css"
    html_path.write_text(output.html, encoding="utf-8")
    css_path.write_text(output.css, encoding="utf-8")
    concept.html_path = str(html_path)
    concept.css_path = str(css_path)

    for old in previous_current:
        old.is_current = False

    session.commit()
    session.refresh(concept)
    return concept


def delete_concept(session: Session, company_id: UUID, concept_id: UUID) -> None:
    concept = get_concept(session, company_id, concept_id)
    if concept is None:
        raise ConceptError("Concept non trovato.", status_code=404)
    concept_dir = Path(concept.html_path).parent if concept.html_path else None
    was_current = concept.is_current
    session.delete(concept)
    session.commit()
    if concept_dir is not None and concept_dir.exists():
        shutil.rmtree(concept_dir, ignore_errors=True)
    if was_current:
        latest = (
            session.query(Concept).filter_by(company_id=company_id).order_by(Concept.version.desc()).first()
        )
        if latest is not None:
            latest.is_current = True
            session.commit()
