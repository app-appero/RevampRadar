from sqlalchemy.orm import Session

from app.models.entities import SenderProfile
from app.proposals.sender import (
    DEFAULT_SENDER,
    SenderProfileView,
    links_from_payload,
    links_to_payload,
)
from app.schemas.profile import SenderProfileUpdate


def get_or_create_sender_profile(session: Session) -> SenderProfile:
    profile = session.query(SenderProfile).order_by(SenderProfile.created_at.asc()).first()
    if profile is not None:
        return profile
    profile = SenderProfile(
        display_name=DEFAULT_SENDER.display_name,
        intro=DEFAULT_SENDER.intro,
        website_url=DEFAULT_SENDER.website_url,
        freelancer_links=links_to_payload(DEFAULT_SENDER.freelancer_links),
        social_links=links_to_payload(DEFAULT_SENDER.social_links),
        other_links=links_to_payload(DEFAULT_SENDER.other_links),
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def update_sender_profile(session: Session, payload: SenderProfileUpdate) -> SenderProfile:
    profile = get_or_create_sender_profile(session)
    profile.display_name = payload.display_name.strip()
    profile.intro = payload.intro.strip()
    profile.website_url = payload.website_url.strip()
    profile.freelancer_links = [item.model_dump() for item in payload.freelancer_links]
    profile.social_links = [item.model_dump() for item in payload.social_links]
    profile.other_links = [item.model_dump() for item in payload.other_links]
    session.commit()
    session.refresh(profile)
    return profile


def profile_view(profile: SenderProfile) -> SenderProfileView:
    return SenderProfileView(
        display_name=profile.display_name,
        intro=profile.intro,
        website_url=profile.website_url,
        freelancer_links=links_from_payload(profile.freelancer_links),
        social_links=links_from_payload(profile.social_links),
        other_links=links_from_payload(profile.other_links),
    )
