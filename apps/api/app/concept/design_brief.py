"""Design Brief di default: stile/palette/tipografia derivati dalla categoria aziendale
e, quando disponibile, dal colore di brand realmente dichiarato dal sito (meta
theme-color). Nessuna palette casuale se un'identità è già riconoscibile.
"""

from __future__ import annotations

import re

from app.models.entities import Company

_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")

_GROUP_KEYWORDS: dict[str, tuple[str, ...]] = {
    "hospitality": (
        "hotel", "b&b", "bed and breakfast", "affittacamere", "agriturismo",
        "ristorante", "pizzeria", "trattoria", "bar", "pasticceria",
    ),
    "wellness": (
        "parrucchiere", "barbiere", "estetista", "centro estetico", "spa",
        "palestra", "fitness", "personal trainer",
    ),
    "professional": (
        "dentista", "studio dentistico", "medico", "fisioterapista", "avvocato",
        "commercialista", "notaio", "studio legale", "veterinario",
    ),
    "trade": ("autofficina", "gommista", "elettricista", "idraulico", "fabbro", "scuola guida", "autoscuola"),
    "retail": ("negozio", "abbigliamento", "boutique", "gioielleria", "arredamento"),
    "creative": ("fotografo", "wedding", "matrimoni", "eventi", "immobiliare", "agenzia immobiliare"),
}

_GROUP_TOKENS: dict[str, dict] = {
    "hospitality": {
        "style": "caldo e accogliente",
        "palette": [
            {"role": "primary", "hex": "#B5502D"},
            {"role": "secondary", "hex": "#2E2A25"},
            {"role": "accent", "hex": "#D9A441"},
            {"role": "background", "hex": "#FBF7F1"},
            {"role": "text", "hex": "#2E2A25"},
        ],
        "typography": "titoli serif eleganti, testo sans-serif leggibile",
        "tone_of_voice": "caloroso, ospitale, diretto",
        "spacing": "generoso",
        "border_radius": "morbido (12-16px)",
        "image_treatment": "fotografie a piena larghezza di ambienti e dettagli",
        "primary_cta": "Prenota ora",
        "hero_layout": "banner",
    },
    "wellness": {
        "style": "pulito e rilassante",
        "palette": [
            {"role": "primary", "hex": "#7C9885"},
            {"role": "secondary", "hex": "#2F3B32"},
            {"role": "accent", "hex": "#E8C4A2"},
            {"role": "background", "hex": "#F7F9F6"},
            {"role": "text", "hex": "#2F3B32"},
        ],
        "typography": "sans-serif arrotondato, dimensioni ampie",
        "tone_of_voice": "rassicurante, professionale, gentile",
        "spacing": "ampio",
        "border_radius": "arrotondato (16-20px)",
        "image_treatment": "fotografie luminose, dettagli del servizio",
        "primary_cta": "Prenota un appuntamento",
        "hero_layout": "split",
    },
    "professional": {
        "style": "sobrio e autorevole",
        "palette": [
            {"role": "primary", "hex": "#1F3A5F"},
            {"role": "secondary", "hex": "#0D1B2A"},
            {"role": "accent", "hex": "#A8763E"},
            {"role": "background", "hex": "#F5F6F8"},
            {"role": "text", "hex": "#0D1B2A"},
        ],
        "typography": "serif per i titoli, sans-serif per il corpo",
        "tone_of_voice": "professionale, chiaro, competente",
        "spacing": "regolare",
        "border_radius": "minimo (4-8px)",
        "image_treatment": "ritratti professionali, ambienti studio",
        "primary_cta": "Richiedi una consulenza",
        "hero_layout": "centered",
    },
    "trade": {
        "style": "concreto ed essenziale",
        "palette": [
            {"role": "primary", "hex": "#C6541D"},
            {"role": "secondary", "hex": "#1E1E1E"},
            {"role": "accent", "hex": "#F2B705"},
            {"role": "background", "hex": "#FAFAFA"},
            {"role": "text", "hex": "#1E1E1E"},
        ],
        "typography": "sans-serif bold, alta leggibilità",
        "tone_of_voice": "diretto, pratico, affidabile",
        "spacing": "compatto",
        "border_radius": "minimo (4-6px)",
        "image_treatment": "foto di interventi/lavori reali quando disponibili",
        "primary_cta": "Richiedi un preventivo",
        "hero_layout": "split-reverse",
    },
    "retail": {
        "style": "moderno e curato",
        "palette": [
            {"role": "primary", "hex": "#1A1A1A"},
            {"role": "secondary", "hex": "#F5F0E8"},
            {"role": "accent", "hex": "#C08552"},
            {"role": "background", "hex": "#FFFFFF"},
            {"role": "text", "hex": "#1A1A1A"},
        ],
        "typography": "sans-serif minimale, ampio spazio bianco",
        "tone_of_voice": "curato, aspirazionale ma concreto",
        "spacing": "ampio",
        "border_radius": "minimo (2-6px)",
        "image_treatment": "prodotto in primo piano, sfondo neutro",
        "primary_cta": "Scopri la collezione",
        "hero_layout": "split",
    },
    "creative": {
        "style": "distintivo ed espressivo",
        "palette": [
            {"role": "primary", "hex": "#111111"},
            {"role": "secondary", "hex": "#EAE6DF"},
            {"role": "accent", "hex": "#D1495B"},
            {"role": "background", "hex": "#FFFFFF"},
            {"role": "text", "hex": "#111111"},
        ],
        "typography": "titoli display, corpo sans-serif",
        "tone_of_voice": "personale, evocativo",
        "spacing": "ampio",
        "border_radius": "nessuno (0-4px)",
        "image_treatment": "galleria fotografica protagonista",
        "primary_cta": "Guarda il portfolio",
        "hero_layout": "banner",
    },
    "default": {
        "style": "neutro e professionale",
        "palette": [
            {"role": "primary", "hex": "#2563EB"},
            {"role": "secondary", "hex": "#1E293B"},
            {"role": "accent", "hex": "#F59E0B"},
            {"role": "background", "hex": "#F8FAFC"},
            {"role": "text", "hex": "#1E293B"},
        ],
        "typography": "sans-serif moderno",
        "tone_of_voice": "chiaro, professionale",
        "spacing": "regolare",
        "border_radius": "moderato (8-12px)",
        "image_treatment": "fotografie reali quando disponibili, placeholder altrimenti",
        "primary_cta": "Contattaci",
        "hero_layout": "centered",
    },
}


FONT_STACKS: dict[str, tuple[str, str]] = {
    "hospitality": ("Georgia, 'Times New Roman', serif", "'Segoe UI', system-ui, sans-serif"),
    "wellness": ("'Trebuchet MS', system-ui, sans-serif", "system-ui, sans-serif"),
    "professional": ("Georgia, serif", "Arial, system-ui, sans-serif"),
    "trade": ("Arial, system-ui, sans-serif", "Arial, system-ui, sans-serif"),
    "retail": ("'Helvetica Neue', Arial, sans-serif", "'Helvetica Neue', Arial, sans-serif"),
    "creative": ("Georgia, serif", "system-ui, sans-serif"),
    "default": ("system-ui, sans-serif", "system-ui, sans-serif"),
}


def hero_layout_for_group(group: str) -> str:
    """Variante strutturale dell'hero (banner/split/split-reverse/centered) per gruppo
    categoria: non e' modificabile a mano come il resto del Design Brief, perche' e' una
    scelta di struttura della pagina, non di stile.
    """
    return _GROUP_TOKENS.get(group, _GROUP_TOKENS["default"])["hero_layout"]


def category_group(category: str | None) -> str:
    if not category:
        return "default"
    lowered = category.lower()
    for group, keywords in _GROUP_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return group
    return "default"


def build_default_design_brief(company: Company, theme_color: str | None = None) -> dict:
    tokens = _GROUP_TOKENS[category_group(company.category)]
    palette = [dict(item) for item in tokens["palette"]]
    if theme_color and _HEX_RE.match(theme_color.strip()):
        palette[0] = {"role": "primary", "hex": _normalize_hex(theme_color)}
    return {
        "style": tokens["style"],
        "palette": palette,
        "typography": tokens["typography"],
        "tone_of_voice": tokens["tone_of_voice"],
        "spacing": tokens["spacing"],
        "border_radius": tokens["border_radius"],
        "image_treatment": tokens["image_treatment"],
        "primary_cta": tokens["primary_cta"],
    }


def _normalize_hex(value: str) -> str:
    value = value.strip()
    if not value.startswith("#"):
        value = f"#{value}"
    return value.upper()
