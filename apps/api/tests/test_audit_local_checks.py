"""Punteggio sito gratuito: controlli locali (TLS, overflow a 390px, anno nel footer, link rotti)."""

from __future__ import annotations

import glob
import os

import httpx
import pytest
from bs4 import BeautifulSoup

import app.scanner.http as http_module
from app.config import Settings
from app.models.entities import Audit, AuditFinding
from app.scanner.findings import build_findings
from app.scanner.html import extract_footer_year, scan_html
from app.scanner.http import HttpScanResult, scan_http
from app.scanner.links import check_links, internal_page_links
from app.services.audit_service import create_audit, execute_audit

# Riusa provider finti e blocco delle chiamate a pagamento del test free mode.
from tests.test_audit_free_mode import guarded, keys_settings  # noqa: F401

# --- anno nel footer ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("html", "year"),
    [
        ("<footer>© 2019 Bar Rossi - P.IVA 0123</footer>", 2019),
        ("<footer>Copyright 2015-2024 Fiori di Lia</footer>", 2024),
        ("<body><p>Menu 2026</p><div>&copy; 2018 Tutti i diritti riservati</div></body>", 2018),
        ("<footer>Via Roma 12, 24058 Romano di Lombardia</footer>", None),  # CAP, non è un anno
    ],
)
def test_footer_year_extraction(html: str, year: int | None) -> None:
    assert extract_footer_year(BeautifulSoup(html, "html.parser")) == year


def test_stale_footer_year_becomes_a_trust_finding() -> None:
    http = HttpScanResult(ok=True, status_code=200, https=True, final_url="https://x.it/", tls_valid=True)
    old = scan_html("<html><head><title>X</title></head><body><footer>© 2023 X</footer></body></html>", "https://x.it/")
    recent = scan_html("<html><head><title>X</title></head><body><footer>© 2025 X</footer></body></html>", "https://x.it/")
    codes = {item.code: item for item in build_findings(http, old, None, current_year=2026)}
    assert codes["HTML_STALE_FOOTER_YEAR"].category == "trust"
    assert "HTML_STALE_FOOTER_YEAR" not in {item.code for item in build_findings(http, recent, None, current_year=2026)}


# --- certificato TLS ---------------------------------------------------------------------


@pytest.fixture
def fake_site(monkeypatch):
    """Il sito ha il certificato scaduto: con verifica fallisce, senza verifica risponde."""
    monkeypatch.setattr(http_module, "is_public_hostname", lambda host: True)
    seen: list[bool] = []

    def client(settings, *, verify=True, timeout=None):
        seen.append(verify)

        def handler(request: httpx.Request) -> httpx.Response:
            if verify and request.url.host == "scaduto.example":
                raise httpx.ConnectError(
                    "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired"
                )
            # Corpo come stream, come una risposta vera (altrimenti httpx non valorizza elapsed).
            body = httpx.ByteStream(b"<title>Ok</title>")
            return httpx.Response(200, headers={"content-type": "text/html"}, stream=body)

        return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)

    monkeypatch.setattr(http_module, "scanner_client", client)
    return seen


def test_expired_certificate_is_reported_and_page_still_read(fake_site) -> None:
    result = scan_http("https://scaduto.example/", Settings())
    assert result.ok is True
    assert result.tls_valid is False
    assert "certificate has expired" in result.tls_error
    assert result.html == "<title>Ok</title>"
    assert fake_site == [True, False]
    findings = {item.code: item for item in build_findings(result, scan_html(result.html, result.final_url), None)}
    assert findings["TLS_INVALID_CERTIFICATE"].severity == "critical"


def test_valid_certificate_is_marked_valid(fake_site) -> None:
    result = scan_http("https://valido.example/", Settings())
    assert result.tls_valid is True
    assert fake_site == [True]


# --- link interni rotti ------------------------------------------------------------------


def test_internal_page_links_keeps_same_site_pages_only() -> None:
    links = [
        "https://www.bar.it/", "https://bar.it/menu", "https://bar.it/menu#prezzi", "https://bar.it/logo.png",
        "https://facebook.com/bar", "mailto:info@bar.it", "https://bar.it/contatti", "https://bar.it/chi-siamo",
    ]
    assert internal_page_links(links, "https://www.bar.it/", 2) == ["https://bar.it/menu", "https://bar.it/contatti"]


def test_check_links_reports_errors_and_handles_head_not_allowed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/rotto":
            return httpx.Response(404)
        if path == "/no-head" and request.method == "HEAD":
            return httpx.Response(405)
        if path == "/giu":
            raise httpx.ConnectError("down")
        return httpx.Response(200)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    urls = ["https://bar.it/ok", "https://bar.it/rotto", "https://bar.it/no-head", "https://bar.it/giu"]
    report = check_links(urls, Settings(), client)
    assert report["checked"] == 4
    assert report["broken"] == [
        {"url": "https://bar.it/rotto", "status": 404},
        {"url": "https://bar.it/giu", "status": None, "error": "ConnectError"},
    ]


# --- overflow a 390px con un browser vero --------------------------------------------------


def _chromium():
    from playwright.sync_api import sync_playwright

    candidates = [os.environ.get("BROWSER_EXECUTABLE_PATH", "")]
    candidates += glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome")
    manager = sync_playwright().start()
    for path in [item for item in candidates if item] + [None]:
        try:
            kwargs = {"headless": True, "args": ["--no-sandbox"]}
            if path:
                kwargs["executable_path"] = path
            return manager, manager.chromium.launch(**kwargs)
        except Exception:  # noqa: BLE001
            continue
    manager.stop()
    pytest.skip("Chromium non disponibile per Playwright")


def test_horizontal_overflow_is_measured_at_390px() -> None:
    from app.scanner.browser import MOBILE_VIEWPORT, measure_horizontal_overflow

    manager, browser = _chromium()
    try:
        page = browser.new_page(viewport={"width": MOBILE_VIEWPORT[0], "height": MOBILE_VIEWPORT[1]})
        page.set_content("<html><body style='margin:0'><img style='width:600px;height:10px'></body></html>")
        expected = {"viewport_width": 390, "scroll_width": 600, "overflow_px": 210}
        assert measure_horizontal_overflow(page, 390) == expected
        page.set_content("<html><body style='margin:0'><img style='max-width:100%;width:600px'></body></html>")
        assert measure_horizontal_overflow(page, 390)["overflow_px"] == 0
    finally:
        browser.close()
        manager.stop()


# --- audit gratuito completo ---------------------------------------------------------------

STALE_HTML = """<!doctype html><html lang="it"><head><title>Bar Rossi</title>
<meta name="viewport" content="width=device-width"></head><body><h1>Bar Rossi</h1>
<a href="/menu">Menu</a><a href="/contatti">Contatti</a><footer>© 2019 Bar Rossi</footer></body></html>"""


def test_free_audit_runs_local_checks_without_paid_calls(client, db_session, guarded, keys_settings, monkeypatch):  # noqa: F811
    monkeypatch.setattr(
        "app.services.audit_service.scan_http",
        lambda url, settings: HttpScanResult(ok=True, final_url="https://barrossi.example/", status_code=200,
                                             https=True, tls_valid=True, html=STALE_HTML, content_type="text/html"),
    )
    monkeypatch.setattr(
        "app.services.audit_service.capture_screenshots",
        lambda url, output_dir, settings: {
            "ok": True, "screenshots": [], "performance": {},
            "mobile_layout": {"viewport_width": 390, "scroll_width": 600, "overflow_px": 210},
        },
    )
    checked: list[list[str]] = []

    def fake_links(urls, settings):
        checked.append(urls)
        return {"checked": len(urls), "broken": [{"url": urls[0], "status": 404}]}

    monkeypatch.setattr("app.services.audit_service.check_links", fake_links)

    audit = create_audit(db_session, "https://barrossi.example", free_only=True)
    execute_audit(audit.id, keys_settings)

    assert guarded.calls == []  # nessuna chiamata AI, PageSpeed o Places
    assert checked == [["https://barrossi.example/menu", "https://barrossi.example/contatti"]]
    db_session.expire_all()
    stored = db_session.get(Audit, audit.id)
    assert stored.status == "completed"
    codes = {row.code for row in db_session.query(AuditFinding).filter_by(audit_id=audit.id)}
    assert {"MOBILE_HORIZONTAL_OVERFLOW", "HTML_STALE_FOOTER_YEAR", "LINKS_BROKEN"} <= codes

    checks = {item["code"]: item for item in client.get(f"/audits/{audit.id}").json()["checks"]}
    assert {code: item["status"] for code, item in checks.items()} == {
        "http_status": "ok",
        "tls": "ok",
        "viewport": "ok",
        "title": "ok",
        "footer_year": "problem",
        "broken_links": "problem",
        "mobile_overflow_390": "problem",
    }
    assert checks["mobile_overflow_390"]["detail"] == "+210px"
    assert checks["broken_links"]["detail"] == "1 rotti su 2 controllati"
