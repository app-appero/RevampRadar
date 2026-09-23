from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.audits import router as audits_router
from app.api.bulk_scans import router as bulk_scans_router
from app.api.crm import router as crm_router
from app.api.discovery import router as discovery_router
from app.api.growth import router as growth_router
from app.api.health import router as health_router
from app.api.intelligence import router as intelligence_router
from app.api.map import router as map_router
from app.api.proposals import router as proposals_router
from app.api.settings import router as settings_router
from app.config import get_settings
from app.errors import register_error_handlers
from app.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="RevampRadar API",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(audits_router)
    app.include_router(discovery_router)
    app.include_router(bulk_scans_router)
    app.include_router(crm_router)
    app.include_router(proposals_router)
    app.include_router(settings_router)
    app.include_router(intelligence_router)
    app.include_router(map_router)
    app.include_router(growth_router)
    return app


app = create_app()
