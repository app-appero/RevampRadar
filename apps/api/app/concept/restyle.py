"""Restyling deterministico della homepage reale del sito.

A differenza del generatore "da zero" (generator.py, usato quando l'azienda
non ha un sito), questo modulo prende l'HTML vero della homepage già
raggiunta e lo ripulisce/ristilizza: stessi contenuti, stesse immagini,
stesso ordine delle sezioni — solo tipografia, colori, spaziature e CSS/JS
originali sostituiti. Nessuna invenzione di contenuti: è letteralmente la
pagina del cliente, con un vestito nuovo.

Sicurezza: script, gestori di eventi inline e il vecchio CSS vengono
rimossi prima di salvare il file, cosi' aprire il concept non esegue mai
codice arbitrario preso dal sito analizzato.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Comment

from app.concept.design_brief import FONT_STACKS, category_group
from app.concept.generator import radius_px, spacing_px
from app.config import Settings
from app.models.entities import Company
from app.scanner.http import scan_http

_URL_ATTRS: tuple[tuple[str, str], ...] = (
    ("img", "src"),
    ("img", "data-src"),
    ("img", "srcset"),
    ("source", "src"),
    ("source", "srcset"),
    ("a", "href"),
    ("link", "href"),
)

_STRUCTURAL_SELECTORS = (
    "section", "main", "article", ".container", ".wrapper", ".content",
    ".page", "#content", "#main",
)


@dataclass
class RestyleResult:
    ok: bool
    html: str | None
    css: str | None
    source_url: str | None
    error: str | None = None


def fetch_and_restyle_homepage(
    company: Company, website_url: str, design_brief: dict, settings: Settings
) -> RestyleResult:
    http_result = scan_http(website_url, settings)
    if not http_result.ok or not http_result.html:
        return RestyleResult(
            ok=False, html=None, css=None, source_url=website_url,
            error=http_result.error or "fetch_failed",
        )
    base_url = http_result.final_url or website_url
    return restyle_html(http_result.html, base_url, design_brief, company)


def restyle_html(raw_html: str, base_url: str, design_brief: dict, company: Company) -> RestyleResult:
    soup = BeautifulSoup(raw_html, "html.parser")

    for tag in soup(["script", "noscript", "style"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    for tag in soup.find_all(True):
        for attr in [key for key in tag.attrs if key.lower().startswith("on")]:
            del tag[attr]
    for link in soup.find_all("link", rel=lambda value: value and "stylesheet" in value):
        link.decompose()

    for tag_name, attr in _URL_ATTRS:
        for node in soup.find_all(tag_name):
            value = node.get(attr)
            if value:
                node[attr] = _resolve_url(value, base_url)

    if soup.head is None:
        head = soup.new_tag("head")
        if soup.html:
            soup.html.insert(0, head)
        else:
            soup.insert(0, head)
        soup_head = head
    else:
        soup_head = soup.head

    if not soup_head.find("meta", attrs={"charset": True}):
        charset_tag = soup.new_tag("meta", charset="utf-8")
        soup_head.insert(0, charset_tag)
    if not soup_head.find("meta", attrs={"name": "viewport"}):
        viewport_tag = soup.new_tag("meta")
        viewport_tag["name"] = "viewport"
        viewport_tag["content"] = "width=device-width, initial-scale=1"
        soup_head.append(viewport_tag)
    soup_head.append(soup.new_tag("link", rel="stylesheet", href="styles.css"))

    if soup.title:
        soup.title.string = f"{company.name} — Concept homepage (dimostrativo)"
    elif soup_head:
        title_tag = soup.new_tag("title")
        title_tag.string = f"{company.name} — Concept homepage (dimostrativo)"
        soup_head.append(title_tag)

    domain = urlparse(base_url).netloc
    if soup.body is not None:
        badge = soup.new_tag("div")
        badge["class"] = "revampradar-concept-badge"
        badge.string = f"Concept dimostrativo · restyling di {domain} · non è il sito ufficiale"
        soup.body.insert(0, badge)

    css = _build_restyle_css(design_brief, company)
    return RestyleResult(ok=True, html=str(soup), css=css, source_url=base_url)


def _resolve_url(value: str, base_url: str) -> str:
    if "," in value and " " in value:
        # attributo srcset: "url1 1x, url2 2x" -> risolvi ogni singolo url
        parts = []
        for chunk in value.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            pieces = chunk.split(" ", 1)
            resolved = urljoin(base_url, pieces[0])
            parts.append(resolved if len(pieces) == 1 else f"{resolved} {pieces[1]}")
        return ", ".join(parts)
    return urljoin(base_url, value)


def _build_restyle_css(design_brief: dict, company: Company) -> str:
    palette = {item["role"]: item["hex"] for item in design_brief.get("palette") or []}
    primary = palette.get("primary", "#2563EB")
    secondary = palette.get("secondary", "#1E293B")
    background = palette.get("background", "#F8FAFC")
    text = palette.get("text", "#1E293B")
    radius = radius_px(design_brief.get("border_radius"))
    spacing = spacing_px(design_brief.get("spacing"))
    group = category_group(company.category)
    heading_font, body_font = FONT_STACKS.get(group, FONT_STACKS["default"])
    structural = ", ".join(_STRUCTURAL_SELECTORS)

    return f""":root {{
  --color-primary: {primary};
  --color-secondary: {secondary};
  --color-background: {background};
  --color-text: {text};
  --radius: {radius}px;
  --spacing: {spacing}px;
  --font-heading: {heading_font};
  --font-body: {body_font};
}}

* {{ box-sizing: border-box; }}

.revampradar-concept-badge {{
  background: var(--color-secondary);
  color: #fff;
  text-align: center;
  font-size: 12px;
  letter-spacing: .04em;
  padding: 6px 12px;
}}

html {{ scroll-behavior: smooth; }}

body {{
  margin: 0;
  font-family: var(--font-body);
  color: var(--color-text);
  background: var(--color-background);
  line-height: 1.65;
}}

img, video {{
  max-width: 100%;
  height: auto;
  border-radius: var(--radius);
  display: block;
}}

h1, h2, h3, h4, h5, h6 {{
  font-family: var(--font-heading);
  line-height: 1.2;
  color: var(--color-text);
  margin: calc(var(--spacing) * 1.2) 0 calc(var(--spacing) * 0.5);
}}
h1 {{ font-size: clamp(28px, 5vw, 48px); }}
h2 {{ font-size: clamp(22px, 3.5vw, 32px); }}

p {{ max-width: 70ch; margin: 0 0 var(--spacing); }}

a {{ color: var(--color-primary); text-decoration: none; }}
a:hover {{ opacity: .8; text-decoration: underline; }}

button, input[type="submit"], input[type="button"], .btn, .button {{
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius);
  padding: 10px 22px;
  font-weight: 600;
  font-family: var(--font-body);
  cursor: pointer;
}}
button:hover, .btn:hover, .button:hover {{ opacity: .9; }}

header, nav {{ padding: 16px 24px; }}
footer {{ padding: calc(var(--spacing) * 1.5) 24px; text-align: center; font-size: 13px; opacity: .7; }}

{structural} {{
  max-width: 1080px;
  margin: 0 auto;
  padding: var(--spacing) 24px;
}}

ul, ol {{ padding-left: 1.4em; }}
"""
