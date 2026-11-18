"""Audit free_only: con le chiavi configurate non deve partire nessuna chiamata AI o Google."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx
import pytest
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.models.entities import AiCredentials, Audit, OpportunityScore, WebsiteScore
from app.scanner.http import HttpScanResult
from app.scanner.seo import SeoScanResult
from app.services.audit_service import create_audit, execute_audit

PAID_HOSTS = ("api.openai.com", "api.anthropic.com", "googleapis.com", "google.com")

HTML = """<!doctype html><html lang="it"><head>
<title>Hotel Sole</title><meta name="viewport" content="width=device-width">
</head><body><h1>Hotel Sole</h1><p>Camere vista mare.</p></body></html>"""


class ProviderCalls:
    """Mock dei provider: registra ogni tentativo di usare AI o PageSpeed."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        # strict: ogni chiamata fa fallire il test. Nella controprova (modalità completa)
        # i mock rispondono come un provider non disponibile, gestito senza eccezioni.
        self.strict = True

    def record(self, name: str):
        def _called(*args, **kwargs):
            self.calls.append(name)
            if self.strict:
                raise AssertionError(f"Chiamata non ammessa in free mode: {name}")
            if name == "google.pagespeed":
                return None
            raise RuntimeError("mock provider")

        return _called


@pytest.fixture
def keys_settings() -> Settings:
    return Settings(
        ai_provider="claude",
        anthropic_api_key="sk-ant-configured",
        openai_api_key="sk-openai-configured",
        pagespeed_api_key="psi-configured",
        screenshot_dir="/tmp/revampradar-test-shots",
    )


@pytest.fixture
def guarded(monkeypatch, sqlite_engine, db_session):
    """Scanner deterministico simulato + provider a pagamento intercettati."""
    factory = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr("app.db.get_session_factory", lambda: factory)
    # Chiavi anche nel database (Impostazioni), che hanno priorità su .env.
    db_session.add(
        AiCredentials(
            provider="claude",
            anthropic_api_key="sk-ant-db",
            openai_api_key="sk-openai-db",
            google_places_api_key="places-db",
        )
    )
    db_session.commit()

    spy = ProviderCalls()
    monkeypatch.setattr("app.ai.claude_provider.ClaudeProvider.analyze", spy.record("anthropic.analyze"))
    monkeypatch.setattr("app.ai.claude_provider.ClaudeProvider.complete_json", spy.record("anthropic.complete"))
    monkeypatch.setattr("app.ai.openai_provider.OpenAICompatibleProvider.analyze", spy.record("openai.analyze"))
    monkeypatch.setattr(
        "app.ai.openai_provider.OpenAICompatibleProvider.complete_json", spy.record("openai.complete")
    )
    monkeypatch.setattr("app.services.audit_service.fetch_pagespeed", spy.record("google.pagespeed"))
    monkeypatch.setattr("app.discovery.places.find_place", spy.record("google.places"))

    # Rete: qualsiasi richiesta httpx verso un host a pagamento fa fallire il test.
    original_send = httpx.Client.send

    def guarded_send(self, request, *args, **kwargs):
        host = urlparse(str(request.url)).hostname or ""
        if any(host == paid or host.endswith("." + paid) for paid in PAID_HOSTS):
            spy.calls.append(f"http:{host}")
            raise AssertionError(f"Richiesta HTTP verso provider a pagamento: {host}")
        return original_send(self, request, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "send", guarded_send)

    monkeypatch.setattr(
        "app.services.audit_service.scan_http",
        lambda url, settings: HttpScanResult(
            ok=True,
            final_url="https://hotelsole.test/",
            status_code=200,
            https=True,
            response_time_ms=180,
            content_type="text/html",
            page_size_bytes=len(HTML),
            html=HTML,
        ),
    )
    monkeypatch.setattr(
        "app.services.audit_service.scan_seo",
        lambda url, html, settings: SeoScanResult(robots_found=True, sitemap_found=False),
    )
    monkeypatch.setattr(
        "app.services.audit_service.capture_screenshots",
        lambda url, output_dir, settings: {
            "ok": True,
            "screenshots": [],
            "performance": {"load_ms": 900},
            "error": None,
        },
    )
    monkeypatch.setattr("app.discovery.contacts.extract_public_email", lambda settings, url: None)
    return spy


def test_free_only_skips_ai_and_pagespeed_but_scores(db_session, guarded, keys_settings) -> None:
    audit = create_audit(db_session, "https://hotelsole.test", free_only=True)
    execute_audit(audit.id, keys_settings)

    db_session.expire_all()
    stored = db_session.get(Audit, audit.id)
    assert stored is not None
    assert guarded.calls == []
    assert stored.status == "completed"
    assert stored.free_only is True
    assert stored.ai_data["status"] == "skipped_free_mode"
    assert stored.performance_data["pagespeed"]["status"] == "skipped_free_mode"
    assert db_session.query(WebsiteScore).filter_by(audit_id=audit.id).one().overall_score > 0
    assert db_session.query(OpportunityScore).filter_by(audit_id=audit.id).one().opportunity_score >= 0


def test_full_mode_does_reach_the_mocked_providers(db_session, guarded, keys_settings) -> None:
    """Controprova: senza free_only gli stessi mock vengono chiamati, quindi intercettano davvero."""
    guarded.strict = False
    audit = create_audit(db_session, "https://hotelsole.test", free_only=False)
    execute_audit(audit.id, keys_settings)

    assert "google.pagespeed" in guarded.calls
    assert "anthropic.analyze" in guarded.calls
    db_session.expire_all()
    assert db_session.get(Audit, audit.id).ai_data["status"] == "failed"


def test_post_audit_defaults_to_free_mode(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.audits.execute_audit", lambda audit_id: None)

    default = client.post("/audits", json={"url": "https://free.example"})
    assert default.status_code == 202
    assert default.json()["free_only"] is True
    assert default.json()["ai_status"] == "skipped_free_mode"

    full = client.post("/audits", json={"url": "https://full.example", "free_only": False})
    assert full.json()["free_only"] is False
    assert full.json()["ai_status"] == "pending"

    fetched = client.get(f"/audits/{default.json()['id']}")
    assert fetched.json()["ai_status"] == "skipped_free_mode"


def test_automatic_jobs_create_free_audits(db_session) -> None:
    # bulk scan e analisi in blocco chiamano create_audit senza flag: modalità gratuita.
    audit = create_audit(db_session, "https://batch.example")
    assert audit.free_only is True
