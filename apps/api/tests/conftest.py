from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import get_db, reset_engine
from app.main import create_app
from app.models import Base


@pytest.fixture(autouse=True)
def isolated_enrich_jobs() -> Generator[None, None, None]:
    """I job di arricchimento vivono in un registro in memoria a livello di modulo.

    Senza pulizia, i job creati da un test (es. test_bulk_enrich) restano visibili ai test
    successivi: falsano i controlli "nessun job avviato" e il limite di un job per tipo.
    """
    from app.jobs.bulk_enrich import _JOBS, _LOCK

    with _LOCK:
        _JOBS.clear()
    yield
    with _LOCK:
        _JOBS.clear()


@pytest.fixture
def sqlite_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(sqlite_engine) -> Generator[Session, None, None]:
    factory = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    get_settings.cache_clear()
    reset_engine()
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    reset_engine()
