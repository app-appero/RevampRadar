from __future__ import annotations

from app.discovery.osm import social_contact_links
from app.models.entities import Company


def is_contactable(company: Company) -> bool:
    """Vero se c'è almeno un modo per contattare l'azienda: sito, telefono, email o social."""
    if company.website_url or company.websites or company.phone or company.email:
        return True
    tags = (company.extra or {}).get("osm_tags") if company.extra else None
    return bool(social_contact_links(tags))
