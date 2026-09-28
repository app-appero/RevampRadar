from app.concept.restyle import RestyleResult, restyle_html
from app.models.entities import Company


def _make_company(**kwargs) -> Company:
    defaults = dict(
        name="Trattoria Del Borgo", category="ristorante", city="Foggia", source="manual", status="discovered"
    )
    defaults.update(kwargs)
    return Company(**defaults)


_SAMPLE_HTML = """<!doctype html>
<html>
<head>
  <title>Vecchio titolo</title>
  <link rel="stylesheet" href="/old-theme.css">
  <style>body { color: red; }</style>
</head>
<body onload="track()">
  <script>alert('tracking');</script>
  <!-- un commento -->
  <header>
    <img src="/logo.png" alt="logo">
    <button onclick="doSomething()">Prenota</button>
  </header>
  <h1>Trattoria Del Borgo</h1>
  <p>Piatti della tradizione pugliese dal 1998.</p>
  <img src="foto.jpg" alt="sala">
  <a href="/menu.html">Il nostro menu</a>
</body>
</html>"""


def test_restyle_removes_scripts_and_original_styles() -> None:
    company = _make_company()
    design_brief = {"palette": [], "border_radius": None, "spacing": None}
    result = restyle_html(_SAMPLE_HTML, "https://esempio.test", design_brief, company)
    assert result.ok
    assert "alert('tracking')" not in result.html
    assert "<script" not in result.html
    assert "color: red" not in result.html
    assert "old-theme.css" not in result.html
    assert "un commento" not in result.html


def test_restyle_strips_inline_event_handlers() -> None:
    company = _make_company()
    design_brief = {"palette": []}
    result = restyle_html(_SAMPLE_HTML, "https://esempio.test", design_brief, company)
    assert "onload" not in result.html
    assert "onclick" not in result.html
    assert "track()" not in result.html
    assert "doSomething()" not in result.html


def test_restyle_resolves_relative_urls_to_absolute() -> None:
    company = _make_company()
    design_brief = {"palette": []}
    result = restyle_html(_SAMPLE_HTML, "https://esempio.test/sub/", design_brief, company)
    assert "https://esempio.test/logo.png" in result.html
    assert "https://esempio.test/sub/foto.jpg" in result.html
    assert "https://esempio.test/menu.html" in result.html


def test_restyle_preserves_real_content_verbatim() -> None:
    company = _make_company()
    design_brief = {"palette": []}
    result = restyle_html(_SAMPLE_HTML, "https://esempio.test", design_brief, company)
    assert "Piatti della tradizione pugliese dal 1998." in result.html
    assert "Il nostro menu" in result.html
    assert "Prenota" in result.html


def test_restyle_injects_badge_and_new_stylesheet_link() -> None:
    company = _make_company()
    design_brief = {"palette": []}
    result = restyle_html(_SAMPLE_HTML, "https://esempio.test", design_brief, company)
    assert "revampradar-concept-badge" in result.html
    assert "Concept dimostrativo" in result.html
    assert 'href="styles.css"' in result.html
    assert "Trattoria Del Borgo — Concept homepage (dimostrativo)" in result.html


def test_restyle_css_uses_design_brief_palette() -> None:
    company = _make_company()
    design_brief = {
        "palette": [
            {"role": "primary", "hex": "#123456"},
            {"role": "text", "hex": "#abcdef"},
        ],
        "border_radius": "moderato (8-12px)",
        "spacing": "ampio",
    }
    result = restyle_html(_SAMPLE_HTML, "https://esempio.test", design_brief, company)
    assert "#123456" in result.css
    assert "#abcdef" in result.css
    assert "--radius: 10px" in result.css
    assert "--spacing: 32px" in result.css


def test_restyle_srcset_resolves_each_candidate() -> None:
    html = """<!doctype html><html><body>
    <img srcset="a.jpg 1x, /b.jpg 2x" src="a.jpg">
    </body></html>"""
    company = _make_company()
    result = restyle_html(html, "https://esempio.test/dir/", {"palette": []}, company)
    assert "https://esempio.test/dir/a.jpg 1x" in result.html
    assert "https://esempio.test/b.jpg 2x" in result.html


def test_restyle_result_is_dataclass_with_expected_fields() -> None:
    result = RestyleResult(ok=True, html="<html></html>", css="", source_url="https://x.test")
    assert result.error is None
