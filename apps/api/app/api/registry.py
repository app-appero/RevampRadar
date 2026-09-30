from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.registry.openapi_company import RegistryError, lookup_by_name, lookup_by_vat

router = APIRouter(tags=["registry"])


@router.get("/registry/company")
def get_registry_company(
    vat: str | None = Query(default=None, min_length=8, max_length=16),
    name: str | None = Query(default=None, min_length=2, max_length=255),
) -> dict[str, Any]:
    """Dati anagrafici (Registro Imprese via OpenAPI.com). Preferire `vat`: la ricerca per nome è approssimativa."""
    if not vat and not name:
        raise HTTPException(status_code=422, detail="Indicare vat o name.")
    settings = get_settings()
    try:
        data = lookup_by_vat(vat, settings) if vat else lookup_by_name(name or "", settings)
    except RegistryError as exc:
        if str(exc) == "openapi_company_token_missing":
            raise HTTPException(status_code=503, detail="Token OpenAPI.com non configurato.") from None
        raise HTTPException(status_code=502, detail=f"Errore provider anagrafico: {exc}") from None
    if data is None:
        raise HTTPException(status_code=404, detail="Azienda non trovata.")
    return data
