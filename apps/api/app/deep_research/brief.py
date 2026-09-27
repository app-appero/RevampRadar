"""Costruzione del Company Brief: assembla solo dati realmente raccolti.

Nessuna invenzione: ogni sezione deriva da pagine crawlate, presenza digitale
osservata, segnali aziendali con fonte, o finding di audit già persistiti.
La sintesi testuale (what_it_does / homepage_direction) puo' opzionalmente
essere riscritta dall'AI (vedi service.py), sempre a partire dagli stessi fatti.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.deep_research.crawler import ResearchPage
from app.models.entities import BusinessSignal, Company

_VALUE_CHECKS: tuple[tuple[str, re.Pattern], ...] = (
    ("Certificazioni", re.compile(r"iso\s?9001|iso\s?14001|certificaz\w*", re.IGNORECASE)),
    ("Riconoscimenti/premi", re.compile(r"premio|award|riconosciment\w*", re.IGNORECASE)),
    (
        "Storia/anzianità dichiarata",
        re.compile(r"\bdal\s+(19\d{2}|20\d{2})\b|\bsince\s+(19\d{2}|20\d{2})\b", re.IGNORECASE),
    ),
    (
        "Produzione/artigianalità",
        re.compile(r"artigian\w*|fatto a mano|produzione propria|made in italy", re.IGNORECASE),
    ),
    (
        "Elementi di fiducia (garanzie, spedizione, pagamento)",
        re.compile(r"garanzia|reso gratuito|pagamento sicuro|spedizione gratuita", re.IGNORECASE),
    ),
    ("Recensioni/testimonianze", re.compile(r"recension\w*|testimonianz\w*", re.IGNORECASE)),
)


def extract_value_elements(pages: list[ResearchPage]) -> list[dict]:
    found: list[dict] = []
    for label, pattern in _VALUE_CHECKS:
        for page in pages:
            match = pattern.search(page.text_excerpt)
            if match:
                start = max(match.start() - 40, 0)
                end = min(match.end() + 60, len(page.text_excerpt))
                found.append(
                    {
                        "label": label,
                        "evidence": page.text_excerpt[start:end].strip(),
                        "source": page.url,
                    }
                )
                break
    return found


def summarize_business_signals(signals: list[BusinessSignal]) -> dict:
    by_key: dict[str, list[BusinessSignal]] = {}
    for signal in signals:
        by_key.setdefault(signal.key, []).append(signal)

    def latest(key: str) -> BusinessSignal | None:
        rows = by_key.get(key) or []
        if not rows:
            return None
        return sorted(rows, key=lambda item: item.period or "", reverse=True)[0]

    revenue_rows = sorted(by_key.get("revenue", []), key=lambda item: item.period or "", reverse=True)

    return {
        "revenue_available": bool(revenue_rows),
        "revenue_latest": _signal_value(revenue_rows[0]) if revenue_rows else None,
        "revenue_history": [_signal_value(row) for row in revenue_rows],
        "revenue_trend": _signal_value(latest("revenue_trend")),
        "employees": _signal_value(latest("employees")),
        "founding_year": _signal_value(latest("founding_year")),
        "legal_form": _signal_value(latest("legal_form")),
    }


def _signal_value(signal: BusinessSignal | None) -> dict | None:
    if signal is None:
        return None
    return {
        "value": signal.value,
        "unit": signal.unit,
        "period": signal.period or None,
        "source": signal.source,
        "confidence": signal.confidence,
        "is_manual": signal.is_manual,
    }


def build_company_brief(
    *,
    company: Company,
    pages: list[ResearchPage],
    digital_presence: dict,
    business_signals: list[BusinessSignal],
    audit_findings: list[dict],
    ai_text: dict | None,
) -> dict:
    value_elements = extract_value_elements(pages)
    signals_summary = summarize_business_signals(business_signals)

    what_it_does_source = "deterministic"
    what_it_does = None
    if ai_text and ai_text.get("what_it_does"):
        what_it_does = ai_text["what_it_does"]
        what_it_does_source = "ai"
    elif pages:
        fragments = [page.title for page in pages if page.title]
        fragments += [page.text_excerpt[:220] for page in pages if page.text_excerpt]
        what_it_does = " ".join(fragments[:2]) or None

    homepage_direction_source = "deterministic"
    homepage_direction = None
    if ai_text and ai_text.get("homepage_direction"):
        homepage_direction = ai_text["homepage_direction"]
        homepage_direction_source = "ai"
    else:
        problem_titles = [item["title"] for item in audit_findings[:2]]
        if problem_titles:
            homepage_direction = (
                "Migliorare " + " e ".join(problem_titles).lower()
                + ", valorizzando i punti di forza reali individuati."
            )

    missing: list[str] = []
    if not signals_summary["revenue_available"]:
        missing.append("Fatturato")
    if not signals_summary["employees"]:
        missing.append("Numero dipendenti")
    if not signals_summary["founding_year"]:
        missing.append("Anno di fondazione")
    if not pages:
        missing.append("Pagine aziendali (chi siamo/servizi/contatti) non raggiunte")
    if not audit_findings:
        missing.append("Nessun audit tecnico completato per questo sito")

    return {
        "version": "brief-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "company": {"name": company.name, "category": company.category, "city": company.city},
        "what_it_does": what_it_does,
        "what_it_does_source": what_it_does_source,
        "value_elements": value_elements,
        "digital_presence": digital_presence,
        "business_signals": signals_summary,
        "website_problems": [item["title"] for item in audit_findings],
        "homepage_direction": homepage_direction,
        "homepage_direction_source": homepage_direction_source,
        "missing_information": missing,
        "pages_researched": [{"kind": page.kind, "url": page.url, "title": page.title} for page in pages],
    }
