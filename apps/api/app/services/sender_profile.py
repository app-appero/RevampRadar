import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.discovery.osm import geocode_point
from app.models.entities import SenderProfile
from app.proposals.sender import (
    DEFAULT_SENDER,
    SenderProfileView,
    links_from_payload,
    links_to_payload,
)
from app.schemas.profile import SenderProfileUpdate

logger = logging.getLogger(__name__)


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

    new_location = (payload.reference_location or "").strip() or None
    if new_location != profile.reference_location:
        profile.reference_location = new_location
        if new_location is None:
            profile.reference_latitude = None
            profile.reference_longitude = None
        else:
            point = _safe_geocode(new_location)
            if point is not None:
                profile.reference_latitude, profile.reference_longitude = point
            else:
                profile.reference_latitude = None
                profile.reference_longitude = None
    profile.local_radius_km = payload.local_radius_km
    profile.local_mention_enabled = payload.local_mention_enabled
    profile.local_mention_text = (payload.local_mention_text or "").strip() or None

    session.commit()
    session.refresh(profile)
    return profile


def _safe_geocode(location: str) -> tuple[float, float] | None:
    try:
        return geocode_point(get_settings(), location)
    except Exception as exc:  # noqa: BLE001 - non deve bloccare il salvataggio impostazioni
        logger.warning("Geocodifica località di riferimento fallita: %s", exc)
        return None


def profile_view(profile: SenderProfile) -> SenderProfileView:
    return SenderProfileView(
        display_name=profile.display_name,
        intro=profile.intro,
        website_url=profile.website_url,
        freelancer_links=links_from_payload(profile.freelancer_links),
        social_links=links_from_payload(profile.social_links),
        other_links=links_from_payload(profile.other_links),
        reference_latitude=profile.reference_latitude,
        reference_longitude=profile.reference_longitude,
        local_radius_km=profile.local_radius_km,
        local_mention_enabled=profile.local_mention_enabled,
        local_mention_text=profile.local_mention_text,
    )
