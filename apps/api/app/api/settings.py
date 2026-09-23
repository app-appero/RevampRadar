from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.entities import EmailTemplates, SenderProfile
from app.proposals.templates import (
    DEFAULT_GREENFIELD_EMAIL_TEMPLATE,
    DEFAULT_REFACTOR_EMAIL_TEMPLATE,
    GREENFIELD_TOKENS,
    REFACTOR_TOKENS,
)
from app.schemas.profile import (
    EmailTemplatesResponse,
    EmailTemplatesUpdate,
    SenderProfileResponse,
    SenderProfileUpdate,
)
from app.services.email_templates import get_or_create_email_templates, update_email_templates
from app.services.sender_profile import get_or_create_sender_profile, update_sender_profile

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/profile", response_model=SenderProfileResponse)
def get_profile(db: Session = Depends(get_db)) -> SenderProfileResponse:
    return _to_response(get_or_create_sender_profile(db))


@router.put("/profile", response_model=SenderProfileResponse)
def put_profile(payload: SenderProfileUpdate, db: Session = Depends(get_db)) -> SenderProfileResponse:
    return _to_response(update_sender_profile(db, payload))


@router.get("/email-templates", response_model=EmailTemplatesResponse)
def get_email_templates(db: Session = Depends(get_db)) -> EmailTemplatesResponse:
    return _templates_response(get_or_create_email_templates(db))


@router.put("/email-templates", response_model=EmailTemplatesResponse)
def put_email_templates(payload: EmailTemplatesUpdate, db: Session = Depends(get_db)) -> EmailTemplatesResponse:
    row = update_email_templates(
        db,
        refactor_body=payload.refactor_body,
        greenfield_body=payload.greenfield_body,
    )
    return _templates_response(row)


def _to_response(profile: SenderProfile) -> SenderProfileResponse:
    return SenderProfileResponse(
        display_name=profile.display_name,
        intro=profile.intro,
        website_url=profile.website_url,
        freelancer_links=profile.freelancer_links or [],
        social_links=profile.social_links or [],
        updated_at=profile.updated_at,
    )


def _templates_response(row: EmailTemplates) -> EmailTemplatesResponse:
    return EmailTemplatesResponse(
        refactor_body=row.refactor_body,
        greenfield_body=row.greenfield_body,
        refactor_default=DEFAULT_REFACTOR_EMAIL_TEMPLATE,
        greenfield_default=DEFAULT_GREENFIELD_EMAIL_TEMPLATE,
        refactor_tokens=list(REFACTOR_TOKENS),
        greenfield_tokens=list(GREENFIELD_TOKENS),
        updated_at=row.updated_at,
    )
