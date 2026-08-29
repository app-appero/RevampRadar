from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.config import get_settings
from app.db import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> JSONResponse:
    settings = get_settings()
    payload = {
        "status": "ok",
        "service": settings.app_name,
        "version": __version__,
        "environment": settings.app_env,
        "database": "ok",
    }

    try:
        check_database()
    except SQLAlchemyError:
        payload["status"] = "degraded"
        payload["database"] = "unavailable"
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload)

    return JSONResponse(status_code=status.HTTP_200_OK, content=payload)
