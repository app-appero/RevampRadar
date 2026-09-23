from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models.entities import AiCredentials, EmailTemplates, SenderProfile
from app.proposals.templates import (
    DEFAULT_GREENFIELD_EMAIL_TEMPLATE,
    DEFAULT_REFACTOR_EMAIL_TEMPLATE,
    GREENFIELD_TOKENS,
    REFACTOR_TOKENS,
)
from app.schemas.profile import (
    AiCredentialsResponse,
    AiCredentialsUpdate,
    EmailTemplatesResponse,
    EmailTemplatesUpdate,
    SenderProfileResponse,
    SenderProfileUpdate,
)
from app.services.ai_settings import (
    get_or_create_ai_credentials,
    is_ai_available,
    key_preview,
    update_ai_credentials,
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


@router.get("/ai", response_model=AiCredentialsResponse)
def get_ai_credentials(db: Session = Depends(get_db)) -> AiCredentialsResponse:
    return _ai_response(db, get_or_create_ai_credentials(db))


@router.put("/ai", response_model=AiCredentialsResponse)
def put_ai_credentials(payload: AiCredentialsUpdate, db: Session = Depends(get_db)) -> AiCredentialsResponse:
    try:
        row = update_ai_credentials(
            db,
            provider=payload.provider,
            anthropic_api_key=payload.anthropic_api_key,
            openai_api_key=payload.openai_api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _ai_response(db, row)


def _to_response(profile: SenderProfile) -> SenderProfileResponse:
    return SenderProfileResponse(
        display_name=profile.display_name,
        intro=profile.intro,
        website_url=profile.website_url,
        freelancer_links=profile.freelancer_links or [],
        social_links=profile.social_links or [],
        updated_at=profile.updated_at,
    )


def _ai_response(db: Session, row: AiCredentials) -> AiCredentialsResponse:
    return AiCredentialsResponse(
        provider=row.provider,
        has_anthropic_key=bool(row.anthropic_api_key),
        has_openai_key=bool(row.openai_api_key),
        anthropic_key_preview=key_preview(row.anthropic_api_key),
        openai_key_preview=key_preview(row.openai_api_key),
        ai_available=is_ai_available(db, get_settings()),
        updated_at=row.updated_at,
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
