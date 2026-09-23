from __future__ import annotations

from dataclasses import dataclass

from app.scoring.constants import clamp_score

FORMULA_VERSION = "1.0.0"

GROWTH_WEIGHTS = {
    "category_fit": 0.30,
    "competition_gap": 0.35,
    "contactability": 0.15,
    "reputation_signal": 0.20,
}

# Quanto una categoria dipende dalla scoperta online (ricerca, mappe, social) per
# portare nuovi clienti. Euristica basata su osservazione, non su un modello allenato.
_CATEGORY_WEIGHTS: dict[str, int] = {
    "hotel": 90, "b&b": 90, "bed and breakfast": 90, "affittacamere": 88, "agriturismo": 85,
    "ristorante": 82, "pizzeria": 78, "trattoria": 78, "bar": 65, "pasticceria": 68,
    "parrucchiere": 75, "barbiere": 72, "estetista": 78, "centro estetico": 78, "spa": 80,
    "palestra": 75, "fitness": 75, "personal trainer": 78,
    "dentista": 80, "studio dentistico": 80, "medico": 70, "fisioterapista": 75,
    "avvocato": 72, "commercialista": 68, "notaio": 60, "studio legale": 72,
    "fotografo": 80, "wedding": 85, "matrimoni": 82, "eventi": 78,
    "immobiliare": 78, "agenzia immobiliare": 78,
    "autofficina": 55, "gommista": 55, "elettricista": 50, "idraulico": 50, "fabbro": 48,
    "negozio": 65, "abbigliamento": 70, "boutique": 72, "gioielleria": 68, "arredamento": 68,
    "scuola guida": 65, "autoscuola": 65, "asilo": 60, "veterinario": 72,
}
_DEFAULT_CATEGORY_WEIGHT = 55

_BOOKING_KEYWORDS = (
    "hotel", "b&b", "bed and breakfast", "affittacamere", "agriturismo", "ristorante",
    "pizzeria", "trattoria", "parrucchiere", "barbiere", "estetista", "centro estetico",
    "spa", "palestra", "fitness", "dentista", "studio dentistico", "fisioterapista",
    "veterinario",
)
_CATALOG_KEYWORDS = ("negozio", "abbigliamento", "boutique", "gioielleria", "arredamento")


@dataclass(frozen=True)
class GrowthScoreDraft:
    score: int
    priority: str
    confidence: float
    explanation: str
    top_reasons: list[str]
    positive_factors: list[str]
    negative_factors: list[str]
    recommended_service: str
    components: dict
    peer_sample_size: int
    formula_version: str = FORMULA_VERSION


def compute_growth_score(
    *,
    name: str,
    category: str | None,
    city: str | None,
    phone: str | None,
    email: str | None,
    rating: float | None,
    peer_total: int,
    peer_with_website: int,
) -> GrowthScoreDraft:
    category_fit = _category_fit(category)
    competition_gap = _competition_gap(peer_total, peer_with_website)
    contactability = _contactability(phone, email)
    reputation_known = rating is not None
    reputation = _reputation_signal(rating) if reputation_known else 50

    components = {
        "category_fit": category_fit,
        "competition_gap": competition_gap,
        "contactability": contactability,
        "reputation_signal": reputation,
    }
    raw = sum(components[key] * weight for key, weight in GROWTH_WEIGHTS.items())
    score = clamp_score(raw)
    priority = _priority(score)
    service = _recommended_service(category)

    positive: list[str] = []
    negative: list[str] = []
    reasons: list[str] = []

    if peer_total > 0:
        peer_ratio_pct = round(100 * peer_with_website / peer_total)
        # Il confronto riguarda solo le attività già presenti nel database di RevampRadar
        # (discovery precedenti), non un dato di mercato o di settore verificato altrove.
        if competition_gap >= 60:
            reasons.append(
                f"{peer_with_website} attività su {peer_total} simili già trovate da RevampRadar nella "
                f"stessa zona ({peer_ratio_pct}%) hanno già un sito: {name} rischia di essere meno "
                "visibile di loro a chi cerca online."
            )
            positive.append(
                f"gap competitivo netto tra le attività già trovate: {peer_ratio_pct}% "
                f"({peer_with_website}/{peer_total}) ha un sito"
            )
        elif competition_gap <= 25:
            negative.append(
                f"anche le {peer_total} attività simili già trovate nella zona sono poco digitalizzate "
                f"({peer_ratio_pct}% con sito)"
            )
    else:
        reasons.append("Nessun competitor comparabile trovato nella stessa zona: stima basata solo sulla categoria.")

    if category_fit >= 75:
        reasons.append(
            f"la categoria \"{category or 'attività'}\" si affida molto alla scoperta online "
            "(ricerca, mappe, social)."
        )
        positive.append("categoria ad alta dipendenza digitale per l'acquisizione clienti")
    elif category_fit <= 55:
        negative.append("categoria meno dipendente dal digitale per acquisire clienti")

    if contactability >= 100:
        positive.append("telefono ed email disponibili: contatto diretto già possibile")
    elif contactability == 0:
        negative.append("nessun contatto diretto noto (telefono/email mancanti)")

    if reputation_known and reputation >= 70:
        positive.append("segnali di reputazione locale positivi")
        reasons.append(
            "i segnali di reputazione (recensioni/valutazione) sono già buoni: "
            "un sito capitalizzerebbe la fiducia esistente."
        )
    elif reputation_known and reputation <= 30:
        negative.append("segnali di reputazione deboli o scarsi")

    if not reasons:
        reasons.append(f"Stima basata su categoria e contattabilità: punteggio {score}/100.")

    confidence = 0.35
    if peer_total >= 5:
        confidence += 0.15
    elif peer_total >= 1:
        confidence += 0.05
    if phone or email:
        confidence += 0.1
    if rating is not None:
        confidence += 0.1
    confidence = round(min(0.75, confidence), 2)

    explanation = (
        f"Growth Potential {score}/100 ({priority}): stima euristica (non un sito da analizzare) basata su "
        f"categoria, concorrenza locale con sito e contattabilità. Servizio indicato: {service}."
    )

    return GrowthScoreDraft(
        score=score,
        priority=priority,
        confidence=confidence,
        explanation=explanation,
        top_reasons=reasons[:5],
        positive_factors=positive[:6],
        negative_factors=negative[:6],
        recommended_service=service,
        components={**components, "weights": dict(GROWTH_WEIGHTS)},
        peer_sample_size=peer_total,
    )


def _category_fit(category: str | None) -> int:
    text = (category or "").strip().lower()
    if not text:
        return _DEFAULT_CATEGORY_WEIGHT
    for keyword, weight in _CATEGORY_WEIGHTS.items():
        if keyword in text:
            return weight
    return _DEFAULT_CATEGORY_WEIGHT


def _competition_gap(peer_total: int, peer_with_website: int) -> int:
    if peer_total <= 0:
        return 50
    ratio = peer_with_website / peer_total
    return clamp_score(ratio * 100)


def _contactability(phone: str | None, email: str | None) -> int:
    if phone and email:
        return 100
    if phone or email:
        return 55
    return 0


def _reputation_signal(rating: float | None) -> int | None:
    if rating is None:
        return None
    try:
        value = float(rating)
    except (TypeError, ValueError):
        return None
    return clamp_score((value / 5.0) * 100)


def _priority(score: int) -> str:
    if score >= 75:
        return "VERY_HIGH"
    if score >= 60:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def _recommended_service(category: str | None) -> str:
    text = (category or "").strip().lower()
    if any(keyword in text for keyword in _BOOKING_KEYWORDS):
        return "Creazione sito vetrina con prenotazione online"
    if any(keyword in text for keyword in _CATALOG_KEYWORDS):
        return "Creazione sito vetrina con catalogo prodotti"
    return "Creazione sito vetrina con scheda attività e contatti"


def rating_from_osm_tags(extra: dict | None) -> float | None:
    if not extra:
        return None
    tags = extra.get("osm_tags")
    if not isinstance(tags, dict):
        return None
    for key in ("stars", "rating"):
        value = tags.get(key)
        if value is None:
            continue
        try:
            return float(str(value).replace(",", "."))
        except ValueError:
            continue
    return None
