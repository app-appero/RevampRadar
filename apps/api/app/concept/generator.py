"""Generatore deterministico del Concept Homepage HTML/CSS.

Usa solo i dati realmente raccolti (Company Brief + Design Brief). Dove un
contenuto manca, usa copy neutro marcato internamente come placeholder
(vedi PLACEHOLDER_MARK) invece di inventare specifiche. Nessuna immagine
viene generata o presa dagli screenshot: solo blocchi placeholder testuali.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape

from app.concept.design_brief import FONT_STACKS, category_group
from app.models.entities import Company

PLACEHOLDER_MARK = "contenuto di esempio · da confermare"


@dataclass
class ConceptOutput:
    html: str
    css: str
    sections: list[str]


def generate_concept(company: Company, brief: dict | None, design_brief: dict) -> ConceptOutput:
    brief = brief or {}
    sections: list[str] = ["header", "hero"]
    group = category_group(company.category)
    heading_font, body_font = FONT_STACKS.get(group, FONT_STACKS["default"])

    what_it_does = _clean_text(brief.get("what_it_does"))
    homepage_direction = _clean_text(brief.get("homepage_direction"))
    value_elements = brief.get("value_elements") or []
    page_texts = {
        page.get("kind"): page.get("text_excerpt")
        for page in (brief.get("website_findings") or {}).get("pages") or []
    }
    digital_presence = (brief.get("digital_presence") or {}).get("channels") or {}
    found_channels = {name: item for name, item in digital_presence.items() if item.get("found")}

    services_kind = "prodotti" if group == "retail" else "servizi"
    services_text = page_texts.get(services_kind) or page_texts.get("prodotti") or page_texts.get("servizi")

    nav_items: list[tuple[str, str]] = [("Chi siamo", "#chi-siamo")]
    nav_items.append(("Servizi" if services_kind == "servizi" else "Prodotti", f"#{services_kind}"))
    if value_elements:
        nav_items.append(("Punti di forza", "#punti-di-forza"))
        sections.append("strengths")
    nav_items.append(("Contatti", "#contatti"))
    sections += ["value_proposition", services_kind]
    if found_channels:
        sections.append("digital_presence")
    sections += ["cta", "footer"]

    header_html = _build_header(company, design_brief, nav_items)
    hero_html = _build_hero(company, what_it_does, design_brief)
    value_prop_html = _build_value_proposition(homepage_direction)
    services_html = _build_services(services_kind, services_text)
    strengths_html = _build_strengths(value_elements) if value_elements else ""
    presence_html = _build_presence(found_channels) if found_channels else ""
    contact_html = _build_contact(company, design_brief)
    footer_html = _build_footer(company)

    body = "\n".join(
        part
        for part in [
            header_html,
            hero_html,
            value_prop_html,
            services_html,
            strengths_html,
            presence_html,
            contact_html,
            footer_html,
        ]
        if part
    )

    html_doc = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{escape(company.name)} — Concept homepage (dimostrativo)</title>
<link rel="stylesheet" href="styles.css" />
</head>
<body>
<div class="concept-badge">Concept dimostrativo · non è il sito ufficiale</div>
{body}
</body>
</html>
"""
    css = _build_css(design_brief, heading_font, body_font)
    return ConceptOutput(html=html_doc, css=css, sections=sections)


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _build_nav(items: list[tuple[str, str]]) -> str:
    links = "".join(f'<a href="{href}">{escape(label)}</a>' for label, href in items)
    return f'<nav class="nav">{links}</nav>'


def _build_header(company: Company, design_brief: dict, nav_items: list[tuple[str, str]]) -> str:
    cta = escape(design_brief.get("primary_cta") or "Contattaci")
    nav_html = _build_nav(nav_items)
    return f"""<header class="site-header">
  <div class="container header-inner">
    <span class="logo">{escape(company.name)}</span>
    {nav_html}
    <a class="btn btn-primary" href="#contatti">{cta}</a>
  </div>
</header>"""


def _build_hero(company: Company, what_it_does: str | None, design_brief: dict) -> str:
    subtitle = what_it_does or (
        f"{escape(company.category)} · {escape(company.city)}"
        if company.category and company.city
        else PLACEHOLDER_MARK
    )
    cta = escape(design_brief.get("primary_cta") or "Contattaci")
    return f"""<section class="hero" id="chi-siamo">
  <div class="container hero-inner">
    <h1>{escape(company.name)}</h1>
    <p class="hero-subtitle">{escape(subtitle) if what_it_does else subtitle}</p>
    <a class="btn btn-primary" href="#contatti">{cta}</a>
  </div>
</section>"""


def _build_value_proposition(homepage_direction: str | None) -> str:
    text = homepage_direction or (
        "Una presentazione chiara di chi siete e di cosa fate, pensata per chi vi scopre "
        f"per la prima volta online. ({PLACEHOLDER_MARK})"
    )
    return f"""<section class="value-proposition">
  <div class="container">
    <p>{escape(text)}</p>
  </div>
</section>"""


def _build_services(kind: str, text: str | None) -> str:
    title = "Servizi" if kind == "servizi" else "Prodotti"
    singular = "Servizio" if kind == "servizi" else "Prodotto"
    if text:
        body = f"<p>{escape(text[:600])}</p>"
    else:
        body = (
            '<div class="placeholder-grid">'
            + "".join(
                f'<div class="placeholder-card">{singular} {i} '
                f'<span class="placeholder-tag">{PLACEHOLDER_MARK}</span></div>'
                for i in range(1, 4)
            )
            + "</div>"
        )
    return f"""<section class="services" id="{kind}">
  <div class="container">
    <h2>{title}</h2>
    {body}
  </div>
</section>"""


def _build_strengths(value_elements: list[dict]) -> str:
    items = "".join(f"<li>{escape(str(item.get('label', '')))}</li>" for item in value_elements)
    return f"""<section class="strengths" id="punti-di-forza">
  <div class="container">
    <h2>Punti di forza</h2>
    <ul class="strengths-list">{items}</ul>
  </div>
</section>"""


def _build_presence(found_channels: dict) -> str:
    def _link(name: str, item: dict) -> str:
        url = escape(str(item.get("url")))
        label = escape(name.replace("_", " ").title())
        return f'<a href="{url}" target="_blank" rel="noopener">{label}</a>'

    links = "".join(_link(name, item) for name, item in found_channels.items())
    return f"""<section class="presence">
  <div class="container">
    <h2>Ci trovi anche su</h2>
    <div class="presence-links">{links}</div>
  </div>
</section>"""


def _build_contact(company: Company, design_brief: dict) -> str:
    rows = []
    if company.phone:
        rows.append(f'<a href="tel:{escape(company.phone)}">{escape(company.phone)}</a>')
    if company.email:
        rows.append(f'<a href="mailto:{escape(company.email)}">{escape(company.email)}</a>')
    if company.city:
        rows.append(f"<span>{escape(company.city)}</span>")
    contact_block = "".join(f"<p>{row}</p>" for row in rows) or f"<p>{PLACEHOLDER_MARK}</p>"
    cta = escape(design_brief.get("primary_cta") or "Contattaci")
    return f"""<section class="contact" id="contatti">
  <div class="container">
    <h2>{cta}</h2>
    {contact_block}
  </div>
</section>"""


def _build_footer(company: Company) -> str:
    year = datetime.now().year
    return f"""<footer class="site-footer">
  <div class="container">
    <p>© {year} {escape(company.name)} — Concept dimostrativo generato da RevampRadar, non il sito ufficiale.</p>
  </div>
</footer>"""


def _build_css(design_brief: dict, heading_font: str, body_font: str) -> str:
    palette = {item["role"]: item["hex"] for item in design_brief.get("palette") or []}
    primary = palette.get("primary", "#2563EB")
    secondary = palette.get("secondary", "#1E293B")
    accent = palette.get("accent", "#F59E0B")
    background = palette.get("background", "#F8FAFC")
    text = palette.get("text", "#1E293B")
    radius = _radius_px(design_brief.get("border_radius"))
    spacing = _spacing_px(design_brief.get("spacing"))

    return f""":root {{
  --color-primary: {primary};
  --color-secondary: {secondary};
  --color-accent: {accent};
  --color-background: {background};
  --color-text: {text};
  --radius: {radius}px;
  --spacing: {spacing}px;
  --font-heading: {heading_font};
  --font-body: {body_font};
}}

* {{ box-sizing: border-box; }}

body {{
  margin: 0;
  font-family: var(--font-body);
  color: var(--color-text);
  background: var(--color-background);
  line-height: 1.6;
}}

h1, h2, h3 {{ font-family: var(--font-heading); line-height: 1.2; }}

.container {{
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 20px;
}}

.concept-badge {{
  background: var(--color-secondary);
  color: #fff;
  text-align: center;
  font-size: 12px;
  letter-spacing: .04em;
  padding: 6px 12px;
}}

.site-header {{
  background: #fff;
  border-bottom: 1px solid rgba(0,0,0,.06);
  position: sticky;
  top: 0;
  z-index: 10;
}}

.header-inner {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing);
  padding: 16px 20px;
}}

.logo {{ font-family: var(--font-heading); font-weight: 700; font-size: 20px; }}

.nav {{ display: flex; gap: 20px; }}
.nav a {{ color: var(--color-text); text-decoration: none; font-size: 14px; }}
.nav a:hover {{ color: var(--color-primary); }}

.btn {{
  display: inline-block;
  padding: 10px 22px;
  border-radius: var(--radius);
  text-decoration: none;
  font-weight: 600;
  font-size: 14px;
}}
.btn-primary {{ background: var(--color-primary); color: #fff; }}
.btn-primary:hover {{ opacity: .9; }}

.hero {{
  padding: calc(var(--spacing) * 3) 0;
  background: linear-gradient(180deg, var(--color-background), #fff);
  text-align: center;
}}
.hero h1 {{ font-size: clamp(32px, 5vw, 52px); margin: 0 0 var(--spacing); }}
.hero-subtitle {{ font-size: 18px; max-width: 640px; margin: 0 auto calc(var(--spacing) * 1.2); opacity: .85; }}

section {{ padding: calc(var(--spacing) * 2) 0; }}
section h2 {{ font-size: 28px; margin-bottom: var(--spacing); }}

.value-proposition {{ background: #fff; text-align: center; }}
.value-proposition p {{ max-width: 720px; margin: 0 auto; font-size: 18px; }}

.placeholder-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--spacing);
}}
.placeholder-card {{
  background: #fff;
  border: 1px dashed rgba(0,0,0,.15);
  border-radius: var(--radius);
  padding: var(--spacing);
}}
.placeholder-tag {{
  display: block;
  margin-top: 8px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .04em;
  opacity: .5;
}}

.strengths {{ background: var(--color-background); }}
.strengths-list {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  list-style: none;
  padding: 0;
}}
.strengths-list li {{
  background: #fff;
  border-radius: var(--radius);
  padding: 14px 18px;
  border-left: 4px solid var(--color-accent);
}}

.presence {{ text-align: center; }}
.presence-links {{ display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; }}
.presence-links a {{
  color: var(--color-primary);
  text-decoration: none;
  border: 1px solid var(--color-primary);
  border-radius: var(--radius);
  padding: 8px 16px;
  font-size: 14px;
}}

.contact {{ background: var(--color-secondary); color: #fff; text-align: center; }}
.contact h2 {{ color: #fff; }}
.contact a {{ color: #fff; }}

.site-footer {{
  background: #fff;
  border-top: 1px solid rgba(0,0,0,.06);
  padding: 20px 0;
  text-align: center;
  font-size: 13px;
  opacity: .7;
}}

@media (max-width: 720px) {{
  .nav {{ display: none; }}
  .header-inner {{ justify-content: space-between; }}
}}
"""


def _radius_px(label: str | None) -> int:
    if not label:
        return 8
    if "0-4" in label or "nessuno" in label:
        return 2
    if "2-6" in label or "4-6" in label:
        return 4
    if "4-8" in label:
        return 6
    if "8-12" in label:
        return 10
    if "12-16" in label:
        return 14
    if "16-20" in label:
        return 18
    return 8


def _spacing_px(label: str | None) -> int:
    mapping = {"compatto": 16, "regolare": 24, "ampio": 32, "generoso": 40}
    return mapping.get(label or "", 24)
