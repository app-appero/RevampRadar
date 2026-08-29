from __future__ import annotations

from collections.abc import Sequence

from app.scoring.constants import OPPORTUNITY_WEIGHTS, clamp_score
from app.scoring.types import (
    BusinessScoreDraft,
    OpportunityScoreDraft,
    ScoreFinding,
    WebsiteScoreDraft,
    has_code,
)

_FIXABLE_CATEGORIES = {
    "http",
    "html",
    "seo",
    "mobile",
    "conversion",
    "performance",
    "tracking",
    "ui",
    "ux",
    "copy",
    "trust",
}

_SERVICE_RULES: list[tuple[set[str], str]] = [
    ({"HTTP_UNREACHABLE"}, "Ripristino hosting o ricostruzione del sito"),
    ({"HTTP_NO_HTTPS"}, "Messa in sicurezza HTTPS e sistemazione tecnica"),
    ({"HTML_MISSING_VIEWPORT", "HTML_WEAK_CTA"}, "Redesign mobile e ottimizzazione conversioni"),
    ({"HTML_WEAK_CTA"}, "Ottimizzazione conversioni e CTA"),
    ({"HTML_MISSING_VIEWPORT"}, "Adeguamento mobile / restyling responsive"),
    ({"SEO_NOINDEX"}, "Sblocco indicizzazione e SEO tecnico"),
    ({"HTML_MISSING_TITLE", "SEO_MISSING_DESCRIPTION", "HTML_MISSING_H1"}, "SEO tecnico e contenuti di landing"),
]


def compute_opportunity_score(
    website: WebsiteScoreDraft,
    business: BusinessScoreDraft,
    findings: Sequence[ScoreFinding],
    html: dict | None,
    seo: dict | None,
) -> OpportunityScoreDraft:
    html = html or {}
    seo = seo or {}
    website_gap = 100 - website.overall_score
    solvable = _solvable_problems(findings, website.overall_score)
    conversion_opp = _conversion_opportunity(findings, html)
    digital = _digital_activity(html, seo)

    components = {
        "website_gap": website_gap,
        "business_potential": business.score,
        "solvable_problems": solvable,
        "conversion_opportunity": conversion_opp,
        "digital_activity": digital,
    }
    raw = sum(components[key] * weight for key, weight in OPPORTUNITY_WEIGHTS.items())
    opportunity = clamp_score(raw)
    priority = _priority(opportunity)
    service = recommended_service(findings, website.overall_score)
    top_reasons = _top_reasons(website, business, findings, components)
    positive = list(business.positive_factors)
    negative = list(business.negative_factors)
    if website_gap >= 40:
        positive.append(f"ampio margine di miglioramento del sito (gap {website_gap})")
    elif website.overall_score >= 80:
        negative.append("sito già relativamente solido: meno urgenza di restyling")
    if conversion_opp >= 70:
        positive.append("problemi di conversione risolvibili con intervento mirato")
    if digital <= 35:
        negative.append("poca attività digitale misurabile dal sito")

    confidence = round(min(0.72, 0.45 + business.confidence), 2)
    explanation = (
        f"Opportunity Score {opportunity}/100 ({priority}): il sito vale {website.overall_score}/100, "
        f"il potenziale commerciale preliminare {business.score}/100. "
        f"Servizio consigliato: {service}."
    )
    return OpportunityScoreDraft(
        website_score=website.overall_score,
        business_score=business.score,
        opportunity_score=opportunity,
        confidence=confidence,
        priority=priority,
        recommended_service=service,
        explanation=explanation,
        top_reasons=top_reasons[:5],
        positive_factors=positive[:6],
        negative_factors=negative[:6],
        components={**components, "weights": dict(OPPORTUNITY_WEIGHTS)},
    )


def recommended_service(findings: Sequence[ScoreFinding], website_overall: int) -> str:
    codes = {item.code for item in findings}
    for needed, label in _SERVICE_RULES:
        if needed <= codes:
            return label
    if website_overall < 45:
        return "Restyling sito e miglioramento della presenza digitale"
    if website_overall < 70:
        return "Ottimizzazione mirata (SEO, UX, conversioni) sul sito esistente"
    return "Interventi puntuali di manutenzione e miglioramento continuo"


def _solvable_problems(findings: Sequence[ScoreFinding], website_overall: int) -> int:
    if has_code(findings, "HTTP_UNREACHABLE"):
        return 35
    score = 15
    for item in findings:
        if item.category not in _FIXABLE_CATEGORIES:
            continue
        if item.severity == "critical":
            score += 28
        elif item.severity == "high":
            score += 16
        elif item.severity == "medium":
            score += 8
    score = max(score, 100 - website_overall)
    return clamp_score(score)


def _conversion_opportunity(findings: Sequence[ScoreFinding], html: dict) -> int:
    if has_code(findings, "HTML_WEAK_CTA"):
        return 85
    if has_code(findings, "HTML_MISSING_VIEWPORT"):
        return 72
    if any(item.category == "conversion" for item in findings):
        return 68
    if html.get("cta_texts"):
        return 32
    return 50


def _digital_activity(html: dict, seo: dict) -> int:
    score = 18
    if html.get("analytics"):
        score += 24
    if seo.get("sitemap_found"):
        score += 14
    if (html.get("structured_data_count") or 0) > 0:
        score += 12
    if html.get("technologies"):
        score += 10
    links = html.get("internal_links") or []
    if len(links) >= 8:
        score += 10
    elif links:
        score += 4
    if html.get("cta_texts"):
        score += 8
    return clamp_score(score)


def _priority(score: int) -> str:
    if score >= 75:
        return "VERY_HIGH"
    if score >= 60:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def _top_reasons(
    website: WebsiteScoreDraft,
    business: BusinessScoreDraft,
    findings: Sequence[ScoreFinding],
    components: dict[str, int],
) -> list[str]:
    reasons: list[str] = []
    if components["website_gap"] >= 40:
        reasons.append(f"Il sito è debole ({website.overall_score}/100): c'è spazio per un intervento.")
    ranked = sorted(
        [item for item in findings if item.severity in {"critical", "high", "medium"}],
        key=lambda item: {"critical": 0, "high": 1, "medium": 2}[item.severity],
    )
    for item in ranked[:3]:
        reasons.append(item.title)
    if business.score < 35:
        reasons.append("Segnali commerciali deboli o assenti: l'azienda potrebbe avere poco potenziale.")
    elif business.score >= 55:
        reasons.append("Il sito mostra segnali di attività digitale utili a un progetto a pagamento.")
    if not reasons:
        reasons.append(website.explanation)
    return reasons
