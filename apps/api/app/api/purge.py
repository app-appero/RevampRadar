from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import purge

router = APIRouter(tags=["purge"])


class PurgeResult(BaseModel):
    deleted: int


def _guard(call, *args):
    try:
        return call(*args)
    except purge.PurgeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _require_confirm(confirm: bool) -> None:
    if not confirm:
        raise HTTPException(status_code=400, detail="Aggiungi confirm=true per eliminare tutto.")


@router.delete("/audits/{audit_id}", status_code=204)
def delete_audit(audit_id: UUID, db: Session = Depends(get_db)) -> None:
    _guard(purge.delete_audit, db, audit_id)


@router.delete("/audits", response_model=PurgeResult)
def delete_all_audits(confirm: bool = Query(default=False), db: Session = Depends(get_db)) -> PurgeResult:
    _require_confirm(confirm)
    return PurgeResult(deleted=_guard(purge.delete_all_audits, db))


@router.delete("/discoveries/{run_id}", status_code=204)
def delete_discovery(run_id: UUID, db: Session = Depends(get_db)) -> None:
    _guard(purge.delete_discovery, db, run_id)


@router.delete("/discoveries", response_model=PurgeResult)
def delete_all_discoveries(confirm: bool = Query(default=False), db: Session = Depends(get_db)) -> PurgeResult:
    _require_confirm(confirm)
    return PurgeResult(deleted=_guard(purge.delete_all_discoveries, db))


@router.delete("/companies/{company_id}", status_code=204)
def delete_company(company_id: UUID, db: Session = Depends(get_db)) -> None:
    _guard(purge.delete_company, db, company_id)


@router.delete("/companies", response_model=PurgeResult)
def delete_all_companies(confirm: bool = Query(default=False), db: Session = Depends(get_db)) -> PurgeResult:
    _require_confirm(confirm)
    return PurgeResult(deleted=_guard(purge.delete_all_companies, db))
