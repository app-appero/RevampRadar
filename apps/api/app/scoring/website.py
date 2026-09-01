from __future__ import annotations

from collections.abc import Sequence

from app.ai.schema import AIAnalysisResult
from app.scoring.constants import SEVERITY_PENALTY, WEBSITE_WEIGHTS, clamp_score
from app.scoring.types import ScoreFinding, WebsiteScoreDraft, findings_in


def compute_website_score(
    findings: Sequence[ScoreFinding],
    http: dict | None,
    html: dict | None,
    seo: dict | None,
    performance: dict | None,
    ai: AIAnalysisResult | None = None,
) -> WebsiteScoreDraft:
    http = http or {}
    html = html or {}
    seo = seo or {}
    performance = performance or {}

    if http.get("ok") is False:
        return WebsiteScoreDraft(
            overall_score=8,
            technical_score=8,
            performance_score=0,
            ui_score=None,
            ux_score=0,
            mobile_score=0,
            conversion_score=0,
            seo_score=0,
            trust_score=0,
            explanation="Sito non raggiungibile: Website Score 8/100. I controlli on-page non sono applicabili.",
            components={
                "scores": {"technical": 8, "unreachable": True},
                "weights": dict(WEBSITE_WEIGHTS),
                "ai_used": False,
            },
        )

    technical = _from_findings(findings, "http", "html", "tracking", "browser")
    performance_score = _performance_score(findings, http, performance)
    mobile = _mobile_score(findings, html, ai)
    seo_score = _from_findings(findings, "seo")
    conversion = _conversion_score(findings, html, ai)
    trust = _trust_score(findings, http, html, ai)
    ux = _ux_score(html, ai)
    ui = ai.ui_score if ai and ai.ui_score is not None else None

    parts = {
        "technical": technical,
        "performance": performance_score,
        "mobile": mobile,
        "seo": seo_score,
        "conversion": conversion,
        "ux": ux,
        "trust": trust,
    }
    if ui is not None:
        parts["ui"] = ui

    overall = _weighted_overall(parts)
    explanation = _explain(overall, parts, ui)

    return WebsiteScoreDraft(
        overall_score=overall,
        technical_score=technical,
        performance_score=performance_score,
        ui_score=ui,
        ux_score=ux,
        mobile_score=mobile,
        conversion_score=conversion,
        seo_score=seo_score,
        trust_score=trust,
        explanation=explanation,
        components={
            "scores": {**parts, "ui": ui},
            "weights": dict(WEBSITE_WEIGHTS),
            "ai_used": ai is not None,
        },
    )


def _from_findings(findings: Sequence[ScoreFinding], *categories: str) -> int:
    score = 100
    for item in findings_in(findings, *categories):
        score -= SEVERITY_PENALTY.get(item.severity, 0)
    return clamp_score(score)


def _performance_score(findings: Sequence[ScoreFinding], http: dict, performance: dict) -> int:
    score = _from_findings(findings, "performance")
    ttfb = http.get("response_time_ms")
    if isinstance(ttfb, int) and ttfb > 1500:
        score -= 8 if ttfb < 3000 else 16
    pagespeed = performance.get("pagespeed") if isinstance(performance.get("pagespeed"), dict) else None
    lighthouse = None
    if pagespeed and pagespeed.get("ok") is not False:
        lighthouse = pagespeed.get("lighthouseResult", {}).get("categories", {}).get("performance", {}).get("score")
        if lighthouse is None:
            lighthouse = pagespeed.get("performance_score", pagespeed.get("performance"))
    if isinstance(lighthouse, float) and 0 <= lighthouse <= 1:
        score = clamp_score(0.6 * score + 0.4 * (lighthouse * 100))
    elif isinstance(lighthouse, int) and 0 <= lighthouse <= 100:
        score = clamp_score(0.6 * score + 0.4 * lighthouse)
    return clamp_score(score)


def _mobile_score(findings: Sequence[ScoreFinding], html: dict, ai: AIAnalysisResult | None) -> int:
    score = _from_findings(findings, "mobile")
    if not html.get("viewport"):
        score = min(score, 45)
    if ai and ai.mobile_usability_score is not None:
        score = clamp_score(0.55 * score + 0.45 * ai.mobile_usability_score)
    return score


def _conversion_score(findings: Sequence[ScoreFinding], html: dict, ai: AIAnalysisResult | None) -> int:
    score = _from_findings(findings, "conversion")
    cta = html.get("cta_texts") or []
    if not cta:
        score = min(score, 55)
    ai_conv = None
    if ai:
        values = [item for item in (ai.conversion_score, ai.copy_score) if item is not None]
        if values:
            ai_conv = sum(values) / len(values)
    if ai_conv is not None:
        score = clamp_score(0.55 * score + 0.45 * ai_conv)
    return score


def _trust_score(findings: Sequence[ScoreFinding], http: dict, html: dict, ai: AIAnalysisResult | None) -> int:
    score = 55
    if http.get("https"):
        score += 18
    else:
        score -= 20
    if html.get("favicon"):
        score += 6
    if (html.get("structured_data_count") or 0) > 0:
        score += 10
    if html.get("lang"):
        score += 4
    if any(item.category == "trust" for item in findings):
        for item in findings_in(findings, "trust"):
            score -= SEVERITY_PENALTY.get(item.severity, 0)
    if ai and ai.trust_score is not None:
        score = 0.6 * score + 0.4 * ai.trust_score
    return clamp_score(score)


def _ux_score(html: dict, ai: AIAnalysisResult | None) -> int:
    score = 78
    if not html.get("viewport"):
        score -= 18
    h1 = html.get("h1") or []
    if not h1:
        score -= 14
    elif len(h1) > 1:
        score -= 4
    if not (html.get("cta_texts") or []):
        score -= 12
    if not html.get("lang"):
        score -= 4
    if ai and ai.ux_score is not None:
        score = 0.4 * score + 0.6 * ai.ux_score
    return clamp_score(score)


def _weighted_overall(parts: dict[str, int]) -> int:
    available = {key: weight for key, weight in WEBSITE_WEIGHTS.items() if key in parts}
    total_weight = sum(available.values()) or 1.0
    value = sum(parts[key] * (weight / total_weight) for key, weight in available.items())
    return clamp_score(value)


def _explain(overall: int, parts: dict[str, int], ui: int | None) -> str:
    weakest = sorted(parts.items(), key=lambda item: item[1])[:2]
    names = {
        "technical": "tecnica",
        "performance": "performance",
        "mobile": "mobile",
        "seo": "SEO",
        "conversion": "conversione",
        "ux": "UX strutturale",
        "trust": "trust",
    }
    weak_text = ", ".join(f"{names.get(key, key)} ({value})" for key, value in weakest)
    ui_note = " UI visiva non valutata (AI assente o senza evidenza)." if ui is None else f" UI visiva {ui}."
    return f"Website Score {overall}/100. Aree più deboli: {weak_text}.{ui_note}"
