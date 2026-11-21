"""Import in blocco di profili Instagram trovati fuori dall'app: crea solo le schede nuove."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.company_manual import (
    InstagramImportItem,
    InstagramImportRequest,
    InstagramImportResponse,
    InstagramImportRow,
    ManualCompanyCreate,
)
from app.services.company_identity import describe, find_identity_duplicates
from app.services.company_manual import ManualCompanyError, create_manual_company
from app.services.instagram import normalize_instagram_handle


def import_instagram_handles(session: Session, request: InstagramImportRequest) -> InstagramImportResponse:
    defaults = request.defaults
    rows: list[InstagramImportRow] = []
    seen: dict[str, InstagramImportRow] = {}
    for raw_item in request.items:
        item = raw_item if isinstance(raw_item, InstagramImportItem) else InstagramImportItem(instagram=raw_item)
        row = InstagramImportRow(input=item.instagram, outcome="invalid")
        try:
            handle = normalize_instagram_handle(item.instagram)
        except ValueError as exc:
            row.error = str(exc)
            rows.append(row)
            continue
        if handle is None:
            row.error = "Profilo Instagram vuoto."
            rows.append(row)
            continue
        row.instagram_handle = handle
        if handle in seen:
            first = seen[handle]
            row.outcome = "duplicate"
            row.company_id, row.opportunity_id = first.company_id, first.opportunity_id
            row.reasons = ["ripetuto nella lista"]
            rows.append(row)
            continue
        seen[handle] = row
        duplicates = find_identity_duplicates(session, instagram_handle=handle)
        if duplicates:
            company = duplicates[0].company
            row.outcome = "duplicate"
            row.company_id = company.id
            row.opportunity_id = company.opportunity.id if company.opportunity else None
            row.reasons = [describe(duplicates[0].reasons)]
            rows.append(row)
            continue
        if request.dry_run:
            row.outcome = "would_create"
            rows.append(row)
            continue
        try:
            payload = ManualCompanyCreate(
                name=item.name or handle,
                instagram_handle=handle,
                instagram_last_post_at=item.instagram_last_post_at,
                city=item.city or defaults.city,
                province=item.province or defaults.province,
                region=item.region or defaults.region,
                category=item.category or defaults.category,
                status=defaults.status,
                source=defaults.source,
                tags=[*defaults.tags, *item.tags],
                notes=[*defaults.notes, *item.notes],
            )
            outcome, company, candidates, _warnings, error = create_manual_company(session, payload)
        except (ManualCompanyError, ValueError) as exc:
            row.error = str(exc)
            rows.append(row)
            continue
        if outcome == "created" and company is not None:
            row.outcome = "created"
        elif outcome in {"duplicate", "existing", "updated"} and company is not None:
            row.outcome = "duplicate"
            row.reasons = ["già presente"]
        else:
            row.outcome = "conflict"
            row.error = error
            row.reasons = [", ".join(candidate.reasons) for candidate in candidates]
        if company is not None:
            row.company_id = company.id
            row.opportunity_id = company.opportunity.id if company.opportunity else None
        rows.append(row)
    return InstagramImportResponse(
        dry_run=request.dry_run,
        created=sum(1 for row in rows if row.outcome == "created"),
        duplicates=sum(1 for row in rows if row.outcome == "duplicate"),
        invalid=sum(1 for row in rows if row.outcome == "invalid"),
        rows=rows,
    )
