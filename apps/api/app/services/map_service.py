from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.config import Settings, get_settings
from app.discovery.osm import fetch_coords_for_external_ids
from app.models.entities import Audit, Company
from app.schemas.map import BackfillResponse, MapCluster, MapPoint, MapResponse
from app.services.contactability import is_contactable
from app.services.geo_cluster import GeoMember, cluster_members


def build_map_payload(session: Session) -> MapResponse:
    mapped = (
        session.query(Company)
        .options(selectinload(Company.websites))
        .filter(Company.latitude.isnot(None), Company.longitude.isnot(None))
        .all()
    )
    unmapped_count = (
        session.query(Company)
        .filter(or_(Company.latitude.is_(None), Company.longitude.is_(None)))
        .count()
    )
    latest_by_website = _latest_audits(session, [site.id for company in mapped for site in company.websites])
    members: list[GeoMember] = []
    audits: dict[UUID, Audit | None] = {}
    for company in mapped:
        assert company.latitude is not None and company.longitude is not None
        audit = _best_audit(company, latest_by_website)
        audits[company.id] = audit
        html = (audit.html_data or {}) if audit else {}
        app_links = html.get("app_links") or []
        opp = audit.opportunity_score if audit else None
        site_score = audit.website_score if audit else None
        has_website = bool(company.website_url or company.websites)
        members.append(
            GeoMember(
                company_id=company.id,
                name=company.name,
                latitude=company.latitude,
                longitude=company.longitude,
                city=company.city,
                category=company.category,
                opportunity_score=opp.opportunity_score if opp else None,
                website_score=site_score.overall_score if site_score else None,
                priority=opp.priority if opp else None,
                has_app=len(app_links) > 0,
                has_website=has_website,
            )
        )
    clusters = cluster_members(members)
    cluster_by_company: dict[UUID, int] = {}
    for cluster in clusters:
        for company_id in cluster.member_ids:
            cluster_by_company[company_id] = cluster.id
    by_id = {item.company_id: item for item in members}
    points: list[MapPoint] = []
    for company in mapped:
        member = by_id[company.id]
        audit = audits[company.id]
        points.append(
            MapPoint(
                company_id=company.id,
                name=member.name,
                city=member.city,
                category=member.category,
                latitude=member.latitude,
                longitude=member.longitude,
                opportunity_score=member.opportunity_score,
                website_score=member.website_score,
                priority=member.priority,
                has_app=member.has_app,
                has_website=member.has_website,
                is_contactable=is_contactable(company),
                cluster_id=cluster_by_company.get(company.id, 0),
                audit_id=audit.id if audit else None,
            )
        )
    return MapResponse(
        points=points,
        clusters=[
            MapCluster(
                id=item.id,
                size=item.size,
                label=item.label,
                centroid_lat=item.centroid_lat,
                centroid_lon=item.centroid_lon,
                avg_opportunity_score=item.avg_opportunity_score,
                high_share=item.high_share,
                app_share=item.app_share,
                no_site_share=item.no_site_share,
                top_city=item.top_city,
                top_category=item.top_category,
            )
            for item in clusters
        ],
        mapped_count=len(points),
        unmapped_count=unmapped_count,
        generated_at=datetime.now(UTC),
    )


def backfill_coordinates(session: Session, settings: Settings | None = None) -> BackfillResponse:
    resolved = settings or get_settings()
    companies = (
        session.query(Company)
        .filter(or_(Company.latitude.is_(None), Company.longitude.is_(None)))
        .all()
    )
    by_external: dict[str, list[Company]] = {}
    skipped = 0
    for company in companies:
        if not company.external_id:
            skipped += 1
            continue
        by_external.setdefault(company.external_id, []).append(company)
    coords = fetch_coords_for_external_ids(resolved, list(by_external))
    updated = 0
    for external_id, members in by_external.items():
        point = coords.get(external_id)
        if point is None:
            skipped += len(members)
            continue
        latitude, longitude = point
        for company in members:
            company.latitude = latitude
            company.longitude = longitude
            updated += 1
    session.commit()
    remaining = (
        session.query(Company)
        .filter(or_(Company.latitude.is_(None), Company.longitude.is_(None)))
        .count()
    )
    return BackfillResponse(updated=updated, skipped=skipped, remaining=remaining)


def _latest_audits(session: Session, website_ids: list[UUID]) -> dict[UUID, Audit]:
    if not website_ids:
        return {}
    rows = (
        session.query(Audit)
        .options(joinedload(Audit.opportunity_score), joinedload(Audit.website_score))
        .filter(Audit.website_id.in_(website_ids), Audit.status == "completed")
        .order_by(Audit.completed_at.desc(), Audit.created_at.desc())
        .all()
    )
    latest: dict[UUID, Audit] = {}
    for audit in rows:
        if audit.website_id not in latest:
            latest[audit.website_id] = audit
    return latest


def _best_audit(company: Company, latest_by_website: dict[UUID, Audit]) -> Audit | None:
    best: Audit | None = None
    for website in company.websites:
        audit = latest_by_website.get(website.id)
        if audit is None:
            continue
        if best is None or _audit_time(audit) > _audit_time(best):
            best = audit
    return best


def _audit_time(audit: Audit) -> datetime:
    stamp = audit.completed_at or audit.created_at
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=UTC)
    return stamp
