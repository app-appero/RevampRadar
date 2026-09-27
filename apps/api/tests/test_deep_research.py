from datetime import UTC, datetime

from app.config import Settings
from app.deep_research.brief import build_company_brief, extract_value_elements, summarize_business_signals
from app.deep_research.crawler import ResearchPage, select_priority_pages
from app.deep_research.digital_presence import build_digital_presence
from app.deep_research.service import _run_research, refresh_stale_status
from app.models.entities import Audit, BusinessSignal, Company, CompanyResearch, Website


def _make_company(**kwargs) -> Company:
    defaults = dict(
        name="Trattoria Del Borgo", category="ristorante", city="Foggia", source="manual", status="discovered"
    )
    defaults.update(kwargs)
    return Company(**defaults)


def test_select_priority_pages_matches_known_url_patterns() -> None:
    links = [
        "https://example.test/",
        "https://example.test/chi-siamo",
        "https://example.test/servizi",
        "https://example.test/blog/post-1",
        "https://example.test/contatti",
    ]
    selected = select_priority_pages(links)
    kinds = [kind for kind, _ in selected]
    assert "chi_siamo" in kinds
    assert "servizi" in kinds
    assert "contatti" in kinds
    assert len(selected) <= 5


def test_digital_presence_reports_found_and_not_found_channels() -> None:
    company = _make_company(website_url="https://example.test", extra={"osm_tags": {"contact:facebook": "example"}})
    html_data = {"social_links": [{"network": "instagram", "url": "https://instagram.com/example"}]}
    presence = build_digital_presence(company, html_data)
    channels = presence["channels"]
    assert channels["website"]["found"] is True
    assert channels["website"]["source"] == "azienda"
    assert channels["facebook"]["found"] is True
    assert channels["facebook"]["source"] == "osm"
    assert channels["instagram"]["found"] is True
    assert channels["instagram"]["source"] == "sito"
    assert channels["tiktok"]["found"] is False
    assert channels["tiktok"]["url"] is None


def test_extract_value_elements_only_reports_real_matches() -> None:
    pages = [
        ResearchPage(
            kind="chi_siamo",
            url="https://example.test/chi-siamo",
            title="Chi siamo",
            text_excerpt="Dal 1998 offriamo prodotti artigianali certificati ISO 9001.",
        )
    ]
    found = extract_value_elements(pages)
    labels = {item["label"] for item in found}
    assert "Certificazioni" in labels
    assert "Storia/anzianità dichiarata" in labels
    assert "Produzione/artigianalità" in labels
    assert "Riconoscimenti/premi" not in labels


def test_extract_value_elements_empty_when_no_evidence() -> None:
    pages = [
        ResearchPage(
            kind="chi_siamo",
            url="https://example.test/chi-siamo",
            title="Chi siamo",
            text_excerpt="Un testo qualsiasi senza segnali particolari.",
        )
    ]
    assert extract_value_elements(pages) == []


def test_summarize_business_signals_picks_latest_period_and_flags_manual() -> None:
    signals = [
        BusinessSignal(
            company_id=None,
            key="revenue",
            period="2023",
            label="Fatturato",
            value="1800000",
            source="visura",
            confidence="verified",
            is_manual=False,
        ),
        BusinessSignal(
            company_id=None,
            key="revenue",
            period="2024",
            label="Fatturato",
            value="2300000",
            source="visura",
            confidence="verified",
            is_manual=False,
        ),
        BusinessSignal(
            company_id=None,
            key="employees",
            period="",
            label="Dipendenti",
            value="18",
            source="LinkedIn",
            confidence="manual",
            is_manual=True,
        ),
    ]
    summary = summarize_business_signals(signals)
    assert summary["revenue_available"] is True
    assert summary["revenue_latest"]["value"] == "2300000"
    assert summary["revenue_latest"]["period"] == "2024"
    assert len(summary["revenue_history"]) == 2
    assert summary["employees"]["value"] == "18"
    assert summary["employees"]["is_manual"] is True
    assert summary["founding_year"] is None


def test_build_company_brief_lists_missing_information_when_nothing_found() -> None:
    company = _make_company()
    brief = build_company_brief(
        company=company,
        pages=[],
        digital_presence=build_digital_presence(company, None),
        business_signals=[],
        audit_findings=[],
        ai_text=None,
    )
    assert brief["what_it_does"] is None
    assert "Fatturato" in brief["missing_information"]
    assert "Numero dipendenti" in brief["missing_information"]
    assert brief["value_elements"] == []


def test_build_company_brief_never_invents_ai_text_it_does_not_receive() -> None:
    company = _make_company()
    pages = [
        ResearchPage(
            kind="chi_siamo",
            url="https://example.test/chi-siamo",
            title="Chi siamo",
            text_excerpt="Ristorante di famiglia dal 1998.",
        )
    ]
    brief = build_company_brief(
        company=company,
        pages=pages,
        digital_presence=build_digital_presence(company, None),
        business_signals=[],
        audit_findings=[],
        ai_text=None,
    )
    # senza AI, la sintesi e' deterministica: solo titolo/estratto delle pagine raccolte
    assert brief["what_it_does_source"] == "deterministic"
    assert "1998" in brief["what_it_does"]


def test_run_research_is_partial_without_website(db_session) -> None:
    company = _make_company()
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)

    research = CompanyResearch(company_id=company.id, status="in_progress", research_version="test")
    db_session.add(research)
    db_session.commit()

    _run_research(db_session, research, company, Settings())
    db_session.commit()

    assert research.status == "partial"
    assert research.brief is not None
    assert research.brief["pages_researched"] == []
    assert research.progress_percent == 100


def test_refresh_stale_status_when_newer_audit_arrives(db_session) -> None:
    company = _make_company(website_url="https://example.test")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)

    website = Website(
        company_id=company.id, url="https://example.test", normalized_url="https://example.test/", domain="example.test"
    )
    db_session.add(website)
    db_session.commit()
    db_session.refresh(website)

    research = CompanyResearch(
        company_id=company.id,
        status="completed",
        research_version="test",
        completed_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    db_session.add(research)
    db_session.commit()

    older_audit = Audit(
        website_id=website.id,
        status="completed",
        request_url=website.url,
        scanner_version="1.0",
        completed_at=datetime(2024, 12, 1, tzinfo=UTC),
    )
    db_session.add(older_audit)
    db_session.commit()
    refresh_stale_status(db_session, research, company)
    assert research.status == "completed"

    newer_audit = Audit(
        website_id=website.id,
        status="completed",
        request_url=website.url,
        scanner_version="1.0",
        completed_at=datetime(2025, 6, 1, tzinfo=UTC),
    )
    db_session.add(newer_audit)
    db_session.commit()
    refresh_stale_status(db_session, research, company)
    assert research.status == "stale"


def test_start_research_rejects_second_call_while_in_progress(client, db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.api.deep_research.execute_research", lambda company_id: None)
    company = _make_company()
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    company_id = str(company.id)

    first = client.post(f"/companies/{company_id}/research")
    assert first.status_code == 202
    assert first.json()["status"] == "in_progress"

    second = client.post(f"/companies/{company_id}/research")
    assert second.status_code == 409


def test_business_signal_crud(client, db_session) -> None:
    company = _make_company()
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    company_id = str(company.id)

    response = client.put(
        f"/companies/{company_id}/business-signals",
        json={
            "key": "employees",
            "label": "Dipendenti",
            "value": "18",
            "source": "LinkedIn azienda",
            "confidence": "manual",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_manual"] is True
    signal_id = body["id"]

    listed = client.get(f"/companies/{company_id}/business-signals")
    assert len(listed.json()) == 1

    deleted = client.delete(f"/companies/{company_id}/business-signals/{signal_id}")
    assert deleted.status_code == 204
    assert client.get(f"/companies/{company_id}/business-signals").json() == []


def test_business_signal_upsert_same_key_and_period_replaces_value(db_session) -> None:
    from app.schemas.deep_research import BusinessSignalCreate
    from app.services.business_signals import upsert_business_signal

    company = _make_company()
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)

    upsert_business_signal(
        db_session, company.id, BusinessSignalCreate(key="employees", label="Dipendenti", value="10", source="a")
    )
    upsert_business_signal(
        db_session, company.id, BusinessSignalCreate(key="employees", label="Dipendenti", value="12", source="b")
    )
    rows = db_session.query(BusinessSignal).filter_by(company_id=company.id).all()
    assert len(rows) == 1
    assert rows[0].value == "12"
    assert rows[0].source == "b"
