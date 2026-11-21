"""Deduplica della discovery con chiavi non uniche ("Multiple rows were found", Romano di Lombardia)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.discovery.service import create_discovery_run, execute_discovery
from app.discovery.types import DiscoveryCandidate
from app.models.entities import Company, DiscoveryResult, DiscoveryRun, Website


class FakeProvider:
    name = "openstreetmap"
    last_warning = None

    def __init__(self, candidates: list[DiscoveryCandidate]) -> None:
        self.candidates = candidates

    def search_businesses(self, query, on_stage=None):
        return list(self.candidates)


@pytest.fixture
def run_with(db_session, sqlite_engine, monkeypatch):
    factory = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.db.get_session_factory", lambda: factory)

    def run(candidates: list[DiscoveryCandidate]) -> DiscoveryRun:
        monkeypatch.setattr("app.discovery.service.get_discovery_provider", lambda settings: FakeProvider(candidates))
        created = create_discovery_run(db_session, industry="parrucchiere",
                                       location="Romano di Lombardia, Bergamo, Lombardia", max_results=50)
        execute_discovery(created.id, Settings())
        db_session.expire_all()
        return db_session.get(DiscoveryRun, created.id)

    return run


def _company(db, name: str, *, city: str | None = None, phone: str | None = None, url: str | None = None,
             external_id: str | None = None) -> Company:
    company = Company(name=name, city=city, phone=phone, source="openstreetmap", external_id=external_id,
                      status="discovered", website_url=url)
    db.add(company)
    db.flush()
    if url:
        from app.scanner.url import normalize_url

        normalized = normalize_url(url)
        db.add(Website(company_id=company.id, url=url, normalized_url=normalized.normalized, domain=normalized.domain))
    db.commit()
    return company


def test_two_namesakes_in_the_same_town_no_longer_crash(db_session, run_with) -> None:
    first = _company(db_session, "Parrucchiera Stefania", city="Romano di Lombardia", external_id="node/1")
    second = _company(db_session, "Parrucchiera Stefania", city="Romano di Lombardia", external_id="node/2")

    run = run_with([DiscoveryCandidate(name="Parrucchiera Stefania", city="Romano di Lombardia",
                                       phone="+39 0363 000001", source="openstreetmap", external_id="node/3")])

    assert run.status == "completed", run.error_message
    assert run.total_found == 1
    linked = db_session.query(DiscoveryResult).filter_by(discovery_run_id=run.id).one()
    # Nome+città ambiguo: non si fonde a caso con una delle due, si crea la nuova scheda.
    assert linked.company_id not in {first.id, second.id}


def test_unique_name_and_city_still_merges(db_session, run_with) -> None:
    known = _company(db_session, "Barberia Romano", city="Romano di Lombardia", external_id="node/10")
    run = run_with([DiscoveryCandidate(name="barberia romano", city="Romano di Lombardia", source="openstreetmap",
                                       external_id="node/11")])
    assert run.status == "completed"
    assert db_session.query(DiscoveryResult).filter_by(discovery_run_id=run.id).one().company_id == known.id


def test_shared_phone_is_ambiguous_not_an_error(db_session, run_with) -> None:
    # Come sul server di sviluppo: due B&B con lo stesso numero.
    _company(db_session, "B&B dei Serafini - Dimora Grecale", phone="+393495776033", external_id="node/20")
    _company(db_session, "B&B dei Serafini - Dimora Chiesetta", phone="+393495776033", external_id="node/21")
    run = run_with([DiscoveryCandidate(name="B&B dei Serafini - Dimora Nuova", phone="+39 349 577 6033",
                                       source="openstreetmap", external_id="node/22")])
    assert run.status == "completed", run.error_message
    assert db_session.query(Company).count() == 3


def test_facebook_pages_are_not_merged_by_domain(db_session, run_with) -> None:
    cafe = _company(db_session, "Conviviale Café", url="https://www.facebook.com/conviviale", external_id="node/30")
    _company(db_session, "Caffè Trento", url="https://www.facebook.com/caffetrento", external_id="node/31")

    run = run_with([
        DiscoveryCandidate(name="Anteprima", website_url="https://www.facebook.com/anteprimabar",
                           source="openstreetmap", external_id="node/32"),
        # Stessa pagina esatta: è la stessa attività.
        DiscoveryCandidate(name="Conviviale", website_url="https://www.facebook.com/conviviale",
                           source="openstreetmap", external_id="node/33"),
    ])

    assert run.status == "completed", run.error_message
    linked = {row.company_id for row in db_session.query(DiscoveryResult).filter_by(discovery_run_id=run.id)}
    assert cafe.id in linked
    anteprima = db_session.query(Company).filter_by(name="Anteprima").one()
    assert anteprima.id in linked
    assert [site.normalized_url for site in anteprima.websites] == ["https://www.facebook.com/anteprimabar"]


def test_same_company_with_two_urls_on_its_domain_is_matched(db_session, run_with) -> None:
    company = _company(db_session, "Elk Bakery", url="https://www.elkbakery.com/", external_id="node/40")
    db_session.add(Website(company_id=company.id, url="http://www.elkbakery.com/menu",
                           normalized_url="http://www.elkbakery.com/menu", domain="www.elkbakery.com"))
    db_session.commit()
    run = run_with([DiscoveryCandidate(name="Elk Bakery Verona", website_url="https://www.elkbakery.com/contatti",
                                       source="openstreetmap", external_id="node/41")])
    assert run.status == "completed", run.error_message
    assert db_session.query(DiscoveryResult).filter_by(discovery_run_id=run.id).one().company_id == company.id
