from app.scanner.findings import build_findings
from app.scanner.html import HtmlScanResult, scan_html
from app.scanner.http import HttpScanResult
from app.scanner.seo import SeoScanResult

SAMPLE_HTML = """
<html lang="it">
  <head>
    <title>Hotel Esempio</title>
    <meta name="description" content="Camere e ristorante">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="canonical" href="https://example.com/">
    <script type="application/ld+json">{"@type":"Hotel"}</script>
  </head>
  <body>
    <h1>Hotel Esempio</h1>
    <a href="/contatti">Contattaci</a>
  </body>
</html>
"""


def test_html_extracts_core_fields() -> None:
    result = scan_html(SAMPLE_HTML, "https://example.com/")
    assert result.title == "Hotel Esempio"
    assert result.h1 == ["Hotel Esempio"]
    assert result.viewport is not None
    assert result.cta_texts == ["Contattaci"]
    assert result.structured_data_count == 1


def test_403_status_is_flagged_as_possible_block_not_high_severity() -> None:
    http_result = HttpScanResult(
        ok=True,
        final_url="https://example.com",
        status_code=403,
        https=True,
        content_type="text/html",
        html="<html><body>Access denied</body></html>",
    )
    findings = build_findings(http_result, HtmlScanResult(), SeoScanResult(robots_found=True, sitemap_found=True))
    status_finding = next(item for item in findings if item.code == "HTTP_ERROR_STATUS")
    assert status_finding.severity == "medium"
    assert "blocco anti-bot" in status_finding.description


def test_500_status_stays_critical() -> None:
    http_result = HttpScanResult(
        ok=True,
        final_url="https://example.com",
        status_code=500,
        https=True,
        content_type="text/html",
        html="<html><body>error</body></html>",
    )
    findings = build_findings(http_result, HtmlScanResult(), SeoScanResult(robots_found=True, sitemap_found=True))
    status_finding = next(item for item in findings if item.code == "HTTP_ERROR_STATUS")
    assert status_finding.severity == "critical"


def test_findings_for_weak_page() -> None:
    http_result = HttpScanResult(
        ok=True,
        final_url="http://example.com",
        status_code=200,
        https=False,
        response_time_ms=2500,
        content_type="text/html",
        html="<html><body>ciao</body></html>",
    )
    html_result = HtmlScanResult()
    seo_result = SeoScanResult(robots_found=False, sitemap_found=False)
    codes = {item.code for item in build_findings(http_result, html_result, seo_result)}
    assert "HTTP_NO_HTTPS" in codes
    assert "HTML_MISSING_TITLE" in codes
    assert "HTML_MISSING_H1" in codes
    assert "SEO_NO_ROBOTS" in codes
