"""CRUD dei Business Signals: MVP a inserimento manuale (valore + fonte + affidabilità).

Nessun provider a pagamento è collegato di default (vedi AGENTS.md, nessuna
dipendenza senza necessità concreta): il dato economico, quando non ottenibile
in automatico, si inserisce a mano e resta marcato come tale.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.entities import BusinessSignal, Company
from app.schemas.deep_research import BusinessSignalCreate


class BusinessSignalError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def list_business_signals(session: Session, company_id: UUID) -> list[BusinessSignal]:
    return (
        session.query(BusinessSignal)
        .filter_by(company_id=company_id)
        .order_by(BusinessSignal.key, BusinessSignal.period.desc())
        .all()
    )


def upsert_business_signal(
    session: Session, company_id: UUID, payload: BusinessSignalCreate
) -> BusinessSignal:
    company = session.get(Company, company_id)
    if company is None:
        raise BusinessSignalError("Azienda non trovata.", status_code=404)
    existing = (
        session.query(BusinessSignal)
        .filter_by(company_id=company_id, key=payload.key, period=payload.period)
        .one_or_none()
    )
    if existing is None:
        existing = BusinessSignal(company_id=company_id, key=payload.key, period=payload.period)
        session.add(existing)
    existing.label = payload.label
    existing.value = payload.value
    existing.unit = payload.unit
    existing.source = payload.source
    existing.source_url = payload.source_url
    existing.observed_at = payload.observed_at
    existing.confidence = payload.confidence
    existing.is_manual = True
    session.commit()
    session.refresh(existing)
    return existing


def delete_business_signal(session: Session, company_id: UUID, signal_id: UUID) -> None:
    signal = session.query(BusinessSignal).filter_by(company_id=company_id, id=signal_id).one_or_none()
    if signal is None:
        raise BusinessSignalError("Segnale non trovato.", status_code=404)
    session.delete(signal)
    session.commit()
