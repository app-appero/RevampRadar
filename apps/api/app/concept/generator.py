"""Generatore deterministico del Concept Homepage HTML/CSS.

Usa solo i dati realmente raccolti (Company Brief + Design Brief). Dove un
contenuto manca, usa copy neutro marcato internamente come placeholder (vedi
PLACEHOLDER_MARK) invece di inventare specifiche. Le uniche immagini incluse
sono quelle reali gia' trovate dal crawler (URL assoluto, mai scaricate o
alterate) su hero/chi-siamo/galleria; quando mancano si usa un blocco
decorativo neutro. Il layout strutturale (hero a banner/split/centrato)
varia per categoria aziendale, non solo palette e tipografia.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape

from app.concept.design_brief import FONT_STACKS, category_group, hero_layout_for_group
from app.models.entities import Company

PLACEHOLDER_MARK = "contenuto di esempio · da confermare"

_SIGNAL_LABELS: dict[str, str] = {
    "revenue_latest": "Fatturato",
    "employees": "Dipendenti",
    "founding_year": "Anno di fondazione",
    "legal_form": "Forma societaria",
    "revenue_trend": "Andamento fatturato",
}


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
    hero_layout = hero_layout_for_group(group)

    what_it_does = _clean_text(brief.get("what_it_does"))
    homepage_direction = _clean_text(brief.get("homepage_direction"))
    value_elements = brief.get("value_elements") or []
    findings_pages = brief.get("pages_researched") or []
    page_texts = {page.get("kind"): page.get("text_excerpt") for page in findings_pages}
    page_items = {page.get("kind"): page.get("items") or [] for page in findings_pages}
    digital_presence = (brief.get("digital_presence") or {}).get("channels") or {}
    found_channels = {name: item for name, item in digital_presence.items() if item.get("found")}
    business_signals = brief.get("business_signals") or {}

    services_kind = "prodotti" if group == "retail" else "servizi"
    services_items = page_items.get(services_kind) or []
    services_text = page_texts.get(services_kind) or page_texts.get("prodotti") or page_texts.get("servizi")

    chi_siamo_page = next((page for page in findings_pages if page.get("kind") == "chi_siamo"), None)
    all_images = [image for page in findings_pages for image in (page.get("images") or []) if image.get("url")]
    used_image_urls: set[str] = set()
    hero_image = _pick_image(findings_pages, ("homepage", "chi_siamo"), used_image_urls)
    about_image = _pick_image(findings_pages, ("chi_siamo", "homepage"), used_image_urls)
    gallery_images = [image for image in all_images if image["url"] not in used_image_urls]

    nav_items: list[tuple[str, str]] = [("Chi siamo", "#chi-siamo")]
    nav_items.append(("Servizi" if services_kind == "servizi" else "Prodotti", f"#{services_kind}"))
    if any(business_signals.get(key) for key in _SIGNAL_LABELS):
        nav_items.append(("Numeri", "#numeri"))
        sections.append("numbers")
    if value_elements:
        nav_items.append(("Punti di forza", "#punti-di-forza"))
        sections.append("strengths")
    nav_items.append(("Contatti", "#contatti"))
    sections += ["value_proposition", services_kind]
    if found_channels:
        sections.append("digital_presence")
    if len(gallery_images) >= 3:
        sections.append("gallery")
    sections += ["cta", "footer"]

    header_html = _build_header(company, design_brief, nav_items)
    hero_html = _build_hero(company, what_it_does, design_brief, hero_layout, hero_image)
    about_html = _build_about(chi_siamo_page, about_image) if chi_siamo_page else ""
    value_prop_html = _build_value_proposition(homepage_direction)
    numbers_html = _build_numbers(business_signals) if "numbers" in sections else ""
    services_html = _build_services(services_kind, services_text, services_items)
    strengths_html = _build_strengths(value_elements) if value_elements else ""
    presence_html = _build_presence(found_channels) if found_channels else ""
    gallery_html = _build_gallery(gallery_images) if "gallery" in sections else ""
    contact_html = _build_contact(company, design_brief)
    footer_html = _build_footer(company)

    body = "\n".join(
        part
        for part in [
            header_html,
            hero_html,
            about_html,
            value_prop_html,
            numbers_html,
            services_html,
            strengths_html,
            presence_html,
            gallery_html,
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


def _pick_image(
    findings_pages: list[dict], preferred_kinds: tuple[str, ...], used: set[str]
) -> dict | None:
    """Prima immagine reale disponibile tra le kind preferite (nell'ordine), non ancora
    usata altrove nella pagina. Nessuna immagine viene scaricata o alterata: solo
    referenziata con il suo URL reale, gia' risolto in assoluto dal crawler.
    """
    by_kind = {page.get("kind"): page for page in findings_pages}
    for kind in preferred_kinds:
        page = by_kind.get(kind)
        if not page:
            continue
        for image in page.get("images") or []:
            url = image.get("url")
            if url and url not in used:
                used.add(url)
                return image
    return None


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


def _build_hero(
    company: Company, what_it_does: str | None, design_brief: dict, layout: str, image: dict | None
) -> str:
    subtitle = what_it_does or (
        f"{escape(company.category)} · {escape(company.city)}"
        if company.category and company.city
        else PLACEHOLDER_MARK
    )
    cta = escape(design_brief.get("primary_cta") or "Contattaci")
    text_block = f"""<h1>{escape(company.name)}</h1>
    <p class="hero-subtitle">{escape(subtitle) if what_it_does else subtitle}</p>
    <a class="btn btn-primary" href="#contatti">{cta}</a>"""

    if layout == "banner":
        style = (
            f' style="background-image: linear-gradient(rgba(0,0,0,.5), rgba(0,0,0,.5)), '
            f'url(\'{escape(image["url"])}\')"'
            if image
            else ""
        )
        return f"""<section class="hero hero--banner" id="chi-siamo"{style}>
  <div class="container hero-inner">
    {text_block}
  </div>
</section>"""

    if layout in ("split", "split-reverse"):
        media = (
            f'<img src="{escape(image["url"])}" alt="{escape(image.get("alt") or company.name)}" loading="lazy" />'
            if image
            else '<div class="hero-media-placeholder" aria-hidden="true"></div>'
        )
        modifier = "hero--split-reverse" if layout == "split-reverse" else "hero--split"
        return f"""<section class="hero {modifier}" id="chi-siamo">
  <div class="container hero-inner">
    <div class="hero-text">
      {text_block}
    </div>
    <div class="hero-media">{media}</div>
  </div>
</section>"""

    return f"""<section class="hero hero--centered" id="chi-siamo">
  <div class="container hero-inner">
    {text_block}
  </div>
</section>"""


def _build_about(page: dict, image: dict | None) -> str:
    text = (page.get("text_excerpt") or "").strip()
    if not text:
        return ""
    media = (
        f'<img src="{escape(image["url"])}" alt="{escape(image.get("alt") or "")}" loading="lazy" />'
        if image
        else ""
    )
    media_block = f'<div class="about-media">{media}</div>' if media else ""
    return f"""<section class="about">
  <div class="container about-inner">
    <div class="about-text">
      <h2>Chi siamo</h2>
      <p>{escape(text[:600])}</p>
    </div>
    {media_block}
  </div>
</section>"""


def _build_numbers(business_signals: dict) -> str:
    cards = []
    for key, label in _SIGNAL_LABELS.items():
        signal = business_signals.get(key)
        if not signal or not signal.get("value"):
            continue
        value = escape(str(signal["value"]))
        unit = escape(str(signal["unit"])) if signal.get("unit") else ""
        period = f' ({escape(str(signal["period"]))})' if signal.get("period") else ""
        source_text = escape(str(signal.get("source") or "n/d"))
        provenance = "dato inserito manualmente" if signal.get("is_manual") else f"fonte: {source_text}"
        cards.append(
            f'<div class="stat-card"><span class="stat-value">{value}{f" {unit}" if unit else ""}</span>'
            f'<span class="stat-label">{escape(label)}{period}</span>'
            f'<span class="stat-provenance">{provenance}</span></div>'
        )
    if not cards:
        return ""
    return f"""<section class="numbers" id="numeri">
  <div class="container">
    <h2>In cifre</h2>
    <div class="stats-grid">{"".join(cards)}</div>
  </div>
</section>"""


def _build_gallery(images: list[dict]) -> str:
    figures = "".join(
        f'<figure><img src="{escape(image["url"])}" alt="{escape(image.get("alt") or "")}" loading="lazy" /></figure>'
        for image in images[:4]
    )
    return f"""<section class="gallery">
  <div class="container">
    <div class="gallery-grid">{figures}</div>
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


def _build_services(kind: str, text: str | None, items: list[dict] | None) -> str:
    title = "Servizi" if kind == "servizi" else "Prodotti"
    singular = "Servizio" if kind == "servizi" else "Prodotto"
    real_items = [item for item in (items or []) if item.get("heading")]
    if real_items:
        cards = "".join(
            f'<div class="service-card"><h3>{escape(str(item.get("heading", "")))}</h3>'
            + (f'<p>{escape(str(item.get("text", ""))[:280])}</p>' if item.get("text") else "")
            + "</div>"
            for item in real_items[:6]
        )
        body = f'<div class="services-grid">{cards}</div>'
    elif text:
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
    cards = []
    for item in value_elements:
        label = escape(str(item.get("label", "")))
        evidence = str(item.get("evidence") or "").strip()
        quote = f'<p class="strength-evidence">"{escape(evidence[:180])}"</p>' if evidence else ""
        cards.append(f'<div class="strength-card"><h3>{label}</h3>{quote}</div>')
    return f"""<section class="strengths" id="punti-di-forza">
  <div class="container">
    <h2>Punti di forza</h2>
    <div class="strengths-grid">{"".join(cards)}</div>
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
    radius = radius_px(design_brief.get("border_radius"))
    spacing = spacing_px(design_brief.get("spacing"))

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

.hero--banner {{
  background-size: cover;
  background-position: center;
  color: #fff;
  min-height: 420px;
  display: flex;
  align-items: center;
}}
.hero--banner .hero-subtitle {{ color: #fff; opacity: .92; }}
.hero--banner .hero-inner {{ width: 100%; }}

.hero--split .hero-inner,
.hero--split-reverse .hero-inner {{
  display: flex;
  align-items: center;
  gap: calc(var(--spacing) * 2);
  text-align: left;
}}
.hero--split-reverse .hero-inner {{ flex-direction: row-reverse; }}
.hero--split .hero-text, .hero--split-reverse .hero-text {{ flex: 1; }}
.hero--split .hero-media, .hero--split-reverse .hero-media {{ flex: 1; }}
.hero--split .hero-subtitle, .hero--split-reverse .hero-subtitle {{ margin-left: 0; }}
.hero-media img {{ width: 100%; border-radius: var(--radius); display: block; }}
.hero-media-placeholder {{
  width: 100%;
  aspect-ratio: 4 / 3;
  border-radius: var(--radius);
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  opacity: .18;
}}

.hero--centered {{ text-align: center; }}

section {{ padding: calc(var(--spacing) * 2) 0; }}
section h2 {{ font-size: 28px; margin-bottom: var(--spacing); }}

.about-inner {{ display: flex; align-items: center; gap: calc(var(--spacing) * 2); }}
.about-text {{ flex: 1; }}
.about-media {{ flex: 1; }}
.about-media img {{ width: 100%; border-radius: var(--radius); display: block; }}
@media (max-width: 720px) {{ .about-inner {{ flex-direction: column; }} }}

.numbers {{ background: var(--color-secondary); color: #fff; }}
.numbers h2 {{ color: #fff; }}
.stats-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--spacing);
}}
.stat-card {{ display: flex; flex-direction: column; gap: 4px; }}
.stat-value {{ font-family: var(--font-heading); font-size: 32px; font-weight: 700; }}
.stat-label {{ font-size: 14px; opacity: .85; }}
.stat-provenance {{ font-size: 11px; text-transform: uppercase; letter-spacing: .04em; opacity: .55; }}

.gallery-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing);
}}
.gallery-grid figure {{ margin: 0; }}
.gallery-grid img {{
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: cover;
  border-radius: var(--radius);
  display: block;
}}

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

.services-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--spacing);
}}
.service-card {{
  background: #fff;
  border-radius: var(--radius);
  padding: var(--spacing);
  box-shadow: 0 1px 2px rgba(0,0,0,.04);
}}
.service-card h3 {{ margin: 0 0 8px; font-size: 18px; }}
.service-card p {{ margin: 0; font-size: 14px; opacity: .8; }}

.strengths {{ background: var(--color-background); }}
.strengths-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--spacing);
}}
.strength-card {{
  background: #fff;
  border-radius: var(--radius);
  padding: var(--spacing);
  border-left: 4px solid var(--color-accent);
}}
.strength-card h3 {{ margin: 0 0 6px; font-size: 16px; }}
.strength-evidence {{ margin: 0; font-size: 13px; opacity: .75; font-style: italic; }}

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


def radius_px(label: str | None) -> int:
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


def spacing_px(label: str | None) -> int:
    mapping = {"compatto": 16, "regolare": 24, "ampio": 32, "generoso": 40}
    return mapping.get(label or "", 24)
