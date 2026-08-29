from __future__ import annotations

from collections.abc import Sequence

from app.scoring.constants import clamp_score
from app.scoring.types import BusinessScoreDraft, ScoreFinding, has_code


def compute_business_score(
    findings: Sequence[ScoreFinding],
    http: dict | None,
    html: dict | None,
    seo: dict | None,
) -> BusinessScoreDraft:
    http = http or {}
    html = html or {}
    seo = seo or {}
    positive: list[str] = []
    negative: list[str] = []

    if http.get("ok") is False:
        return BusinessScoreDraft(
            score=10,
            confidence=0.15,
            explanation=(
                "Business Score preliminare 10/100: il sito non è raggiungibile. "
                "Senza discovery (M3) non ci sono recensioni, settore o segnali di attività reale."
            ),
            positive_factors=positive,
            negative_factors=["sito non raggiungibile"],
        )

    score = 42
    if http.get("https"):
        score += 8
        positive.append("HTTPS attivo (investimento minimo sul digitale)")
    else:
        score -= 10
        negative.append("HTTPS assente")

    analytics = html.get("analytics") or []
    if analytics:
        score += 12
        positive.append("analytics/tag manager rilevati")
    else:
        score -= 4
        negative.append("nessun analytics evidente")

    if seo.get("sitemap_found"):
        score += 6
        positive.append("sitemap presente")
    else:
        negative.append("sitemap assente")

    if (html.get("structured_data_count") or 0) > 0:
        score += 6
        positive.append("dati strutturati presenti")

    technologies = html.get("technologies") or []
    if technologies:
        score += 5
        positive.append(f"stack rilevato: {', '.join(technologies[:3])}")

    if html.get("cta_texts"):
        score += 8
        positive.append("CTA commerciali visibili")
    else:
        score -= 4
        negative.append("CTA deboli o assenti")

    if has_code(findings, "SEO_NOINDEX"):
        score -= 14
        negative.append("pagina marcata noindex")

    score = clamp_score(score)
    return BusinessScoreDraft(
        score=score,
        confidence=0.28,
        explanation=(
            f"Business Score preliminare {score}/100 calcolato solo dal sito. "
            "Mancano rating, recensioni, settore e dimensione aziendale (arriveranno con la discovery)."
        ),
        positive_factors=positive,
        negative_factors=negative,
    )
