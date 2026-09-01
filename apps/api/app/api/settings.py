from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.entities import SenderProfile
from app.schemas.profile import SenderProfileResponse, SenderProfileUpdate
from app.services.sender_profile import get_or_create_sender_profile, update_sender_profile

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/profile", response_model=SenderProfileResponse)
def get_profile(db: Session = Depends(get_db)) -> SenderProfileResponse:
    return _to_response(get_or_create_sender_profile(db))


@router.put("/profile", response_model=SenderProfileResponse)
def put_profile(payload: SenderProfileUpdate, db: Session = Depends(get_db)) -> SenderProfileResponse:
    return _to_response(update_sender_profile(db, payload))


def _to_response(profile: SenderProfile) -> SenderProfileResponse:
    return SenderProfileResponse(
        display_name=profile.display_name,
        intro=profile.intro,
        website_url=profile.website_url,
        freelancer_links=profile.freelancer_links or [],
        social_links=profile.social_links or [],
        updated_at=profile.updated_at,
    )
