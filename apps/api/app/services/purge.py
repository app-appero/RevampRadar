"""Eliminazione fisica di audit, discovery e aziende con tutto ciò che vi è legato.

Le cancellazioni sono esplicite (non affidate al cascade dell'ORM) perché molte relazioni
non lo prevedono. Gli screenshot su disco vengono rimossi solo dopo il commit.
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.entities import (
    Activity,
    Audit,
    AuditFinding,
    BulkScan,
    BulkScanItem,
    Company,
    DiscoveryResult,
    DiscoveryRun,
    GrowthScore,
    Opportunity,
    OpportunityNote,
    OpportunityScore,
    OpportunityTag,
    Proposal,
    Screenshot,
    Website,
    WebsiteScore,
)

logger = logging.getLogger(__name__)

_RUNNING = ("queued", "running")


class PurgeError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _ids(session: Session, column, *conditions) -> list[UUID]:
    return [row[0] for row in session.execute(select(column).where(*conditions)).all()]


def _remove_files(paths: list[str]) -> None:
    for raw in paths:
        try:
            Path(raw).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Screenshot non rimosso (%s): %s", raw, exc)


def _delete_audits(session: Session, audit_ids: list[UUID]) -> list[str]:
    """Cancella gli audit e i loro dati; restituisce i file da rimuovere dopo il commit."""
    if not audit_ids:
        return []
    files = [row[0] for row in session.execute(select(Screenshot.file_path).where(Screenshot.audit_id.in_(audit_ids)))]
    website_ids = _ids(session, Audit.website_id, Audit.id.in_(audit_ids))
    session.execute(BulkScanItem.__table__.update().where(BulkScanItem.audit_id.in_(audit_ids)).values(audit_id=None))
    for model in (AuditFinding, Screenshot, WebsiteScore, OpportunityScore, Proposal):
        session.execute(delete(model).where(model.audit_id.in_(audit_ids)))
    session.execute(delete(Audit).where(Audit.id.in_(audit_ids)))
    session.flush()
    # Un sito senza azienda né altri audit non serve più (es. analisi di un URL singolo).
    for website_id in set(website_ids):
        website = session.get(Website, website_id)
        if website is not None and website.company_id is None:
            still_used = session.execute(select(Audit.id).where(Audit.website_id == website_id).limit(1)).first()
            if still_used is None:
                session.delete(website)
    return files


def _delete_companies(session: Session, company_ids: list[UUID]) -> list[str]:
    if not company_ids:
        return []
    website_ids = _ids(session, Website.id, Website.company_id.in_(company_ids))
    audit_ids = _ids(session, Audit.id, Audit.website_id.in_(website_ids)) if website_ids else []
    # Proposte e punteggi possono puntare all'azienda senza passare dall'audit.
    audit_ids += [
        i
        for i in _ids(session, Proposal.audit_id, Proposal.company_id.in_(company_ids), Proposal.audit_id.is_not(None))
        if i not in audit_ids
    ]
    files = _delete_audits(session, audit_ids)
    opportunity_ids = _ids(session, Opportunity.id, Opportunity.company_id.in_(company_ids))
    if opportunity_ids:
        for model in (Activity, OpportunityNote, OpportunityTag):
            session.execute(delete(model).where(model.opportunity_id.in_(opportunity_ids)))
        session.execute(delete(Opportunity).where(Opportunity.id.in_(opportunity_ids)))
    session.execute(delete(Proposal).where(Proposal.company_id.in_(company_ids)))
    session.execute(delete(OpportunityScore).where(OpportunityScore.company_id.in_(company_ids)))
    session.execute(delete(GrowthScore).where(GrowthScore.company_id.in_(company_ids)))
    session.execute(delete(BulkScanItem).where(BulkScanItem.company_id.in_(company_ids)))
    session.execute(delete(DiscoveryResult).where(DiscoveryResult.company_id.in_(company_ids)))
    session.execute(delete(Website).where(Website.company_id.in_(company_ids)))
    session.execute(delete(Company).where(Company.id.in_(company_ids)))
    return files


def _delete_runs(session: Session, run_ids: list[UUID]) -> list[str]:
    """Cancella le discovery e le aziende trovate solo da quelle (le altre restano)."""
    if not run_ids:
        return []
    company_ids = set(_ids(session, DiscoveryResult.company_id, DiscoveryResult.discovery_run_id.in_(run_ids)))
    scan_ids = _ids(session, BulkScan.id, BulkScan.discovery_run_id.in_(run_ids))
    if scan_ids:
        session.execute(delete(BulkScanItem).where(BulkScanItem.bulk_scan_id.in_(scan_ids)))
        session.execute(delete(BulkScan).where(BulkScan.id.in_(scan_ids)))
    session.execute(delete(DiscoveryResult).where(DiscoveryResult.discovery_run_id.in_(run_ids)))
    session.execute(delete(DiscoveryRun).where(DiscoveryRun.id.in_(run_ids)))
    session.flush()
    kept = set(_ids(session, DiscoveryResult.company_id, DiscoveryResult.company_id.in_(company_ids))) if company_ids else set()
    return _delete_companies(session, sorted(company_ids - kept))


def _finish(session: Session, files: list[str]) -> None:
    session.commit()
    _remove_files(files)


def delete_audit(session: Session, audit_id: UUID) -> None:
    audit = session.get(Audit, audit_id)
    if audit is None:
        raise PurgeError("Audit non trovato.", status_code=404)
    if audit.status in _RUNNING:
        raise PurgeError("L'audit è ancora in corso: attendi che finisca.", status_code=409)
    _finish(session, _delete_audits(session, [audit_id]))


def delete_all_audits(session: Session) -> int:
    if _ids(session, Audit.id, Audit.status.in_(_RUNNING)):
        raise PurgeError("Ci sono audit in corso: attendi che finiscano.", status_code=409)
    ids = _ids(session, Audit.id)
    _finish(session, _delete_audits(session, ids))
    return len(ids)


def delete_discovery(session: Session, run_id: UUID) -> None:
    run = session.get(DiscoveryRun, run_id)
    if run is None:
        raise PurgeError("Discovery non trovata.", status_code=404)
    if run.status in _RUNNING or _ids(session, BulkScan.id, BulkScan.discovery_run_id == run_id, BulkScan.status.in_(_RUNNING)):
        raise PurgeError("La discovery (o la sua scansione) è ancora in corso.", status_code=409)
    _finish(session, _delete_runs(session, [run_id]))


def delete_all_discoveries(session: Session) -> int:
    if _ids(session, DiscoveryRun.id, DiscoveryRun.status.in_(_RUNNING)) or _ids(
        session, BulkScan.id, BulkScan.status.in_(_RUNNING)
    ):
        raise PurgeError("Ci sono discovery o scansioni in corso: attendi che finiscano.", status_code=409)
    ids = _ids(session, DiscoveryRun.id)
    _finish(session, _delete_runs(session, ids))
    return len(ids)


def delete_company(session: Session, company_id: UUID) -> None:
    if session.get(Company, company_id) is None:
        raise PurgeError("Azienda non trovata.", status_code=404)
    if _ids(session, Audit.id, Audit.status.in_(_RUNNING), Audit.website_id.in_(select(Website.id).where(Website.company_id == company_id))):
        raise PurgeError("C'è un audit in corso per questa azienda: attendi che finisca.", status_code=409)
    _finish(session, _delete_companies(session, [company_id]))


def delete_all_companies(session: Session) -> int:
    """Azzera la pipeline: aziende, audit, discovery e scansioni."""
    if _ids(session, Audit.id, Audit.status.in_(_RUNNING)) or _ids(session, DiscoveryRun.id, DiscoveryRun.status.in_(_RUNNING)):
        raise PurgeError("Ci sono audit o discovery in corso: attendi che finiscano.", status_code=409)
    company_ids = _ids(session, Company.id)
    files = _delete_companies(session, company_ids)
    session.flush()
    files += _delete_audits(session, _ids(session, Audit.id))
    run_ids = _ids(session, DiscoveryRun.id)
    scan_ids = _ids(session, BulkScan.id)
    if scan_ids:
        session.execute(delete(BulkScanItem).where(BulkScanItem.bulk_scan_id.in_(scan_ids)))
        session.execute(delete(BulkScan).where(BulkScan.id.in_(scan_ids)))
    if run_ids:
        session.execute(delete(DiscoveryResult).where(DiscoveryResult.discovery_run_id.in_(run_ids)))
        session.execute(delete(DiscoveryRun).where(DiscoveryRun.id.in_(run_ids)))
    _finish(session, files)
    return len(company_ids)
