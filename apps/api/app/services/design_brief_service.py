"""CRUD del Design Brief: default derivato dalla categoria/identità aziendale,
sempre modificabile a mano prima di (ri)generare il Concept.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.concept.design_brief import build_default_design_brief
from app.models.entities import Audit, Company, DesignBrief, Website
from app.schemas.concept import DesignBriefUpdate

_FIELDS = (
    "style",
    "typography",
    "tone_of_voice",
    "spacing",
    "border_radius",
    "image_treatment",
    "primary_cta",
)


class DesignBriefError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def get_or_create_design_brief(session: Session, company_id: UUID) -> DesignBrief:
    company = session.get(Company, company_id)
    if company is None:
        raise DesignBriefError("Azienda non trovata.", status_code=404)
    brief = session.query(DesignBrief).filter_by(company_id=company_id).one_or_none()
    if brief is not None:
        return brief
    defaults = build_default_design_brief(company, _latest_theme_color(session, company))
    brief = DesignBrief(company_id=company_id, source="auto", **defaults)
    session.add(brief)
    session.commit()
    session.refresh(brief)
    return brief


def regenerate_design_brief(session: Session, company_id: UUID) -> DesignBrief:
    """Rigenera i default dalla categoria/identità: sovrascrive eventuali modifiche manuali."""
    company = session.get(Company, company_id)
    if company is None:
        raise DesignBriefError("Azienda non trovata.", status_code=404)
    brief = session.query(DesignBrief).filter_by(company_id=company_id).one_or_none()
    defaults = build_default_design_brief(company, _latest_theme_color(session, company))
    if brief is None:
        brief = DesignBrief(company_id=company_id)
        session.add(brief)
    for key, value in defaults.items():
        setattr(brief, key, value)
    brief.source = "auto"
    session.commit()
    session.refresh(brief)
    return brief


def update_design_brief(session: Session, company_id: UUID, payload: DesignBriefUpdate) -> DesignBrief:
    brief = get_or_create_design_brief(session, company_id)
    data = payload.model_dump(exclude_unset=True)
    if "palette" in data and data["palette"] is not None:
        brief.palette = data["palette"]
    for field in _FIELDS:
        if field in data and data[field] is not None:
            setattr(brief, field, data[field])
    if "notes" in data:
        brief.notes = data["notes"]
    brief.source = "manual"
    session.commit()
    session.refresh(brief)
    return brief


def _latest_theme_color(session: Session, company: Company) -> str | None:
    website = (
        session.query(Website).filter_by(company_id=company.id).order_by(Website.created_at.desc()).first()
    )
    if website is None:
        return None
    audit = (
        session.query(Audit)
        .filter_by(website_id=website.id, status="completed")
        .order_by(Audit.completed_at.desc())
        .first()
    )
    if audit is None or not audit.html_data:
        return None
    return audit.html_data.get("theme_color")
