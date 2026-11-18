from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.discovery.normalize import normalize_candidate
from app.discovery.provider import get_discovery_provider
from app.discovery.types import DiscoveryCandidate
from app.models.entities import Company, DiscoveryResult, DiscoveryRun, Website
from app.scanner.url import UrlValidationError, normalize_url
from app.schemas.discovery import MAX_RESULTS_EXTENDED, MAX_RESULTS_STANDARD


class DiscoveryServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def update_company_contacts(
    session: Session,
    company: Company,
    *,
    phone: str | None,
    email: str | None,
    social_links: list[tuple[str, str]] | None = None,
) -> Company:
    from app.discovery.normalize import normalize_email, normalize_phone

    normalized_email = normalize_email(email)
    if email and (
        normalized_email is None
        or re.fullmatch(r"[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+", normalized_email) is None
    ):
        raise DiscoveryServiceError("Inserisci un indirizzo email valido.", status_code=422)
    company.phone = normalize_phone(phone)
    company.email = normalized_email
    if social_links is not None:
        extra = dict(company.extra or {})
        extra["social_links"] = _clean_social_links(social_links)
        company.extra = extra
    if company.phone or company.email:
        company.places_checked_at = company.places_checked_at or datetime.now(UTC)
    session.commit()
    session.refresh(company)
    return company


def _clean_social_links(links: list[tuple[str, str]]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    seen: set[str] = set()
    for label, raw_url in links:
        url = raw_url.strip()
        if not url:
            continue
        if "://" not in url:
            url = f"https://{url}"
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or "." not in parsed.netloc or len(url) > 2048:
            raise DiscoveryServiceError(f"Link social non valido: {raw_url.strip()}", status_code=422)
        if url in seen:
            continue
        seen.add(url)
        name = label.strip()[:40] or parsed.netloc.removeprefix("www.").split(".")[0].capitalize()
        cleaned.append({"label": name, "url": url})
    return cleaned


def create_discovery_run(
    session: Session,
    *,
    industry: str,
    location: str,
    max_results: int,
    provider_name: str = "openstreetmap",
    extended: bool = False,
    require_contactable: bool = False,
) -> DiscoveryRun:
    industry_value = industry.strip() or "tutti"
    location_value = location.strip() or "Italia"
    cap = MAX_RESULTS_EXTENDED if extended else MAX_RESULTS_STANDARD
    if max_results < 1 or max_results > cap:
        raise DiscoveryServiceError(
            f"max_results deve essere tra 1 e {cap}"
            + (" con ricerca estesa." if extended else " (usa ricerca estesa per arrivare a 200)."),
            status_code=422,
        )
    run = DiscoveryRun(
        industry=industry_value,
        location=location_value,
        max_results=max_results,
        extended=extended,
        require_contactable=require_contactable,
        provider=provider_name,
        status="queued",
        total_found=0,
        progress_percent=0,
        progress_label="In coda",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def execute_discovery(run_id: UUID, settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    from app.db import get_session_factory

    session = get_session_factory()()
    try:
        run = session.get(DiscoveryRun, run_id)
        if run is None:
            return
        run.status = "running"
        run.started_at = datetime.now(UTC)
        _set_progress(session, run, 8, "Avvio ricerca")
        _run_discovery(session, run, resolved)
        session.commit()
    except Exception as exc:
        session.rollback()
        run = session.get(DiscoveryRun, run_id)
        if run is not None:
            run.status = "failed"
            run.error_message = str(exc)
            run.completed_at = datetime.now(UTC)
            # Prima restava l'ultima fase (es. "ricerca per comuni 0/204") e sembrava bloccata.
            stage = run.progress_label or "errore"
            run.progress_label = stage if stage.startswith("Fallita") else f"Fallita · {stage}"[:128]
            session.commit()
        raise
    finally:
        session.close()


RETRYABLE_STATUSES = frozenset({"failed", "partial"})
# Una ricerca "running"/"queued" da così tanto è rimasta orfana (es. API riavviata da un deploy).
STALE_RUN_AFTER = timedelta(minutes=30)


def reset_discovery_for_retry(session: Session, run_id: UUID, *, now: datetime | None = None) -> DiscoveryRun:
    """Rimette in coda una discovery fallita, parziale o bloccata, con gli stessi parametri.

    I risultati già trovati restano collegati: il nuovo giro aggiunge solo le aziende mancanti.
    """
    run = session.get(DiscoveryRun, run_id)
    if run is None:
        raise DiscoveryServiceError("Discovery non trovata.", status_code=404)
    current = now or datetime.now(UTC)
    if run.status not in RETRYABLE_STATUSES:
        since = run.started_at or run.created_at
        if since is not None and since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        stale = run.status in {"queued", "running"} and since is not None and current - since > STALE_RUN_AFTER
        if not stale:
            if run.status in {"queued", "running"}:
                raise DiscoveryServiceError("La discovery è ancora in corso.", status_code=409)
            raise DiscoveryServiceError(
                "La discovery è già completata: avviane una nuova per ripetere la ricerca.", status_code=409
            )
    run.status = "queued"
    run.error_message = None
    run.started_at = None
    run.completed_at = None
    run.progress_percent = 0
    run.progress_label = "In coda · nuovo tentativo"
    session.commit()
    session.refresh(run)
    return run


def load_discovery_run(session: Session, run_id: UUID) -> DiscoveryRun | None:
    return (
        session.query(DiscoveryRun)
        .options(
            selectinload(DiscoveryRun.results).selectinload(DiscoveryResult.company).selectinload(Company.websites)
        )
        .filter(DiscoveryRun.id == run_id)
        .one_or_none()
    )


def list_companies(session: Session) -> list[Company]:
    return (
        session.query(Company)
        .options(selectinload(Company.websites))
        .order_by(Company.created_at.desc())
        .all()
    )


def list_company_categories(session: Session) -> list[str]:
    rows = (
        session.query(Company.category)
        .filter(Company.category.isnot(None), Company.category != "")
        .distinct()
        .all()
    )
    return sorted({row[0] for row in rows}, key=str.lower)


def get_company(session: Session, company_id: UUID) -> Company | None:
    return (
        session.query(Company)
        .options(selectinload(Company.websites))
        .filter(Company.id == company_id)
        .one_or_none()
    )


def resolve_company_location(session: Session, company: Company, settings: Settings) -> Company:
    """Riempie città/regione mancanti da Nominatim, usando le coordinate già note.

    Non sovrascrive città/regione già presenti (potrebbero venire da OSM e non è
    detto che il dato di Nominatim sia più preciso). Ricalcola il Growth Score se
    l'azienda non ha sito: il confronto "stessa zona" dipende da città/regione.
    """
    if company.latitude is None or company.longitude is None:
        raise DiscoveryServiceError("Nessuna coordinata nota per questa azienda.", status_code=422)
    from app.discovery.osm import reverse_geocode

    try:
        found = reverse_geocode(settings, company.latitude, company.longitude)
    except RuntimeError as exc:
        raise DiscoveryServiceError(str(exc), status_code=502) from exc
    if not found:
        raise DiscoveryServiceError(
            "Nominatim non ha restituito un indirizzo per queste coordinate.", status_code=404
        )
    changed = False
    if not company.city and found.get("city"):
        company.city = found["city"]
        changed = True
    if not company.region and found.get("region"):
        company.region = found["region"]
        changed = True
    if not company.country and found.get("country"):
        company.country = found["country"]
        changed = True
    if not changed:
        raise DiscoveryServiceError(
            "Nominatim non ha aggiunto nulla di nuovo (città/regione già presenti o non trovate).",
            status_code=404,
        )
    session.flush()
    if not company.website_url:
        from app.services.growth_service import compute_and_store_growth_score

        compute_and_store_growth_score(session, company)
    session.commit()
    session.refresh(company)
    return company


def enrich_company_from_places(session: Session, company: Company, settings: Settings) -> Company:
    """Completa sito/telefono da Places ed email dal sito, senza sovrascrivere dati."""
    from app.discovery.places import find_place
    from app.services.ai_settings import get_or_create_ai_credentials

    website_url = company.website_url or (company.websites[0].normalized_url if company.websites else None)
    found = None
    places_checked = False
    if not website_url or not company.phone:
        key = (get_or_create_ai_credentials(session).google_places_api_key or "").strip()
        if key:
            try:
                found = find_place(
                    settings,
                    key,
                    name=company.name,
                    city=company.city,
                    latitude=company.latitude,
                    longitude=company.longitude,
                )
            except RuntimeError as exc:
                raise DiscoveryServiceError(str(exc), status_code=502) from exc
            company.places_checked_at = datetime.now(UTC)
            places_checked = True
        elif not website_url:
            raise DiscoveryServiceError(
                "Manca la chiave Google Places: inseriscila in Impostazioni.", status_code=422
            )

    if not company.website_url and found and found.get("website"):
        try:
            company.website_url = normalize_url(found["website"]).normalized
        except UrlValidationError:
            company.website_url = None
        else:
            _link_website(session, company, company.website_url)
    if not company.phone and found and found.get("phone"):
        company.phone = found["phone"][:64]

    website_url = company.website_url or (company.websites[0].normalized_url if company.websites else None)
    if not company.email and website_url:
        from app.discovery.contacts import extract_public_email

        company.email = extract_public_email(settings, website_url)

    if places_checked:
        from app.services.crm_service import mark_uncontactable_after_places_check

        mark_uncontactable_after_places_check(session, company)

    session.commit()
    session.refresh(company)
    return company


def _set_progress(session: Session, run: DiscoveryRun, percent: int, label: str) -> None:
    run.progress_percent = max(0, min(100, percent))
    run.progress_label = label
    session.commit()


def _run_discovery(session: Session, run: DiscoveryRun, settings: Settings) -> None:
    from app.discovery.types import DiscoveryQuery

    provider = get_discovery_provider(settings)
    run.provider = provider.name
    query = DiscoveryQuery(
        industry=run.industry,
        location=run.location,
        max_results=run.max_results,
        include_without_website=bool(run.extended),
    )

    def on_stage(label: str, percent: int | None = None) -> None:
        if percent is None:
            percent = 18 if "località" in label.lower() else 40
        _set_progress(session, run, percent, label[:128])

    _set_progress(session, run, 12, "Ricerca OpenStreetMap")
    try:
        raw_candidates = provider.search_businesses(query, on_stage=on_stage)
    except TypeError:
        raw_candidates = provider.search_businesses(query)

    _set_progress(session, run, 55, "Normalizzazione risultati")
    # Su un nuovo tentativo (retry) i risultati già collegati restano e contano nel totale.
    persisted = (
        session.query(func.count(DiscoveryResult.id)).filter(DiscoveryResult.discovery_run_id == run.id).scalar() or 0
    )
    skipped_uncontactable = 0
    seen_company_ids: set[UUID] = set()
    for raw in raw_candidates:
        candidate = normalize_candidate(raw)
        if candidate is None:
            continue
        if run.require_contactable and not _is_contactable(candidate):
            skipped_uncontactable += 1
            continue
        company = _upsert_company(session, candidate)
        if company.id in seen_company_ids:
            continue
        already = (
            session.query(DiscoveryResult)
            .filter_by(discovery_run_id=run.id, company_id=company.id)
            .one_or_none()
        )
        if already is None:
            session.add(DiscoveryResult(discovery_run_id=run.id, company_id=company.id))
            persisted += 1
        seen_company_ids.add(company.id)
        cap = max(run.max_results, 1)
        percent = 55 + int(40 * min(persisted, cap) / cap)
        label = f"Aziende trovate · {persisted}"
        if skipped_uncontactable:
            label += f" · {skipped_uncontactable} escluse (incontattabili)"
        _set_progress(session, run, percent, label)
        if persisted >= run.max_results:
            break
    run.total_found = persisted
    run.status = "completed"
    run.progress_percent = 100
    warning = getattr(provider, "last_warning", None)
    if warning:
        # Alcuni comuni non hanno risposto (Overpass): risultati validi ma incompleti.
        run.status = "partial"
        run.error_message = warning
        run.progress_label = f"Parziale · {persisted} aziende"
    elif persisted == 0:
        from app.discovery.osm import empty_search_message

        run.error_message = empty_search_message(run.industry, run.location)
        run.progress_label = "Nessun risultato"
    else:
        run.progress_label = "Completata"
        if skipped_uncontactable:
            run.progress_label += f" · {skipped_uncontactable} escluse (incontattabili)"
    run.completed_at = datetime.now(UTC)


def _is_contactable(candidate: DiscoveryCandidate) -> bool:
    if candidate.website_url or candidate.phone or candidate.email:
        return True
    from app.discovery.osm import social_contact_links

    tags = (candidate.extra or {}).get("osm_tags") if candidate.extra else None
    return bool(social_contact_links(tags))


def _upsert_company(session: Session, candidate: DiscoveryCandidate) -> Company:
    company = _find_duplicate(session, candidate)
    if company is None:
        company = Company(
            name=candidate.name,
            category=candidate.category,
            city=candidate.city,
            region=candidate.region,
            country=candidate.country,
            latitude=candidate.latitude,
            longitude=candidate.longitude,
            website_url=candidate.website_url,
            phone=candidate.phone,
            email=candidate.email,
            source=candidate.source,
            external_id=candidate.external_id,
            status="discovered",
            extra=candidate.extra,
        )
        session.add(company)
        session.flush()
        from app.services.crm_service import ensure_opportunity

        ensure_opportunity(session, company)
    else:
        _fill_missing(company, candidate)
    if candidate.website_url:
        _link_website(session, company, candidate.website_url)
    if not company.website_url:
        from app.services.growth_service import compute_and_store_growth_score

        compute_and_store_growth_score(session, company)
    return company


def _find_duplicate(session: Session, candidate: DiscoveryCandidate) -> Company | None:
    if candidate.source and candidate.external_id:
        match = (
            session.query(Company)
            .filter_by(source=candidate.source, external_id=candidate.external_id)
            .one_or_none()
        )
        if match:
            return match
    if candidate.phone:
        match = session.query(Company).filter_by(phone=candidate.phone).one_or_none()
        if match:
            return match
    if candidate.website_url:
        try:
            normalized = normalize_url(candidate.website_url)
        except UrlValidationError:
            normalized = None
        if normalized:
            website = session.query(Website).filter_by(normalized_url=normalized.normalized).one_or_none()
            if website and website.company_id:
                return session.get(Company, website.company_id)
            website = session.query(Website).filter_by(domain=normalized.domain).one_or_none()
            if website and website.company_id:
                return session.get(Company, website.company_id)
    if candidate.name and candidate.city:
        return (
            session.query(Company)
            .filter(func.lower(Company.name) == candidate.name.lower())
            .filter(func.lower(Company.city) == candidate.city.lower())
            .one_or_none()
        )
    return None


def _fill_missing(company: Company, candidate: DiscoveryCandidate) -> None:
    if not company.category and candidate.category:
        company.category = candidate.category
    if not company.city and candidate.city:
        company.city = candidate.city
    if not company.region and candidate.region:
        company.region = candidate.region
    if not company.country and candidate.country:
        company.country = candidate.country
    if not company.website_url and candidate.website_url:
        company.website_url = candidate.website_url
    if not company.phone and candidate.phone:
        company.phone = candidate.phone
    if not company.email and candidate.email:
        company.email = candidate.email
    if not company.external_id and candidate.external_id:
        company.external_id = candidate.external_id
    if candidate.latitude is not None and candidate.longitude is not None:
        company.latitude = candidate.latitude
        company.longitude = candidate.longitude
    province = (candidate.extra or {}).get("province") if candidate.extra else None
    if province and not (company.extra or {}).get("province"):
        company.extra = {**(company.extra or {}), "province": province}
    incoming = (candidate.extra or {}).get("osm_tags") if candidate.extra else None
    if isinstance(incoming, dict) and incoming:
        extra = dict(company.extra or {})
        current = extra.get("osm_tags") if isinstance(extra.get("osm_tags"), dict) else {}
        extra["osm_tags"] = {**current, **incoming}
        company.extra = extra


def _link_website(session: Session, company: Company, website_url: str) -> None:
    try:
        normalized = normalize_url(website_url)
    except UrlValidationError:
        return
    website = session.query(Website).filter_by(normalized_url=normalized.normalized).one_or_none()
    if website is None:
        website = session.query(Website).filter_by(domain=normalized.domain).one_or_none()
    if website is None:
        website = Website(
            company_id=company.id,
            url=normalized.original,
            normalized_url=normalized.normalized,
            domain=normalized.domain,
        )
        session.add(website)
        return
    if website.company_id is None:
        website.company_id = company.id
