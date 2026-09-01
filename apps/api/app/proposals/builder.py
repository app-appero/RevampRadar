from __future__ import annotations

from dataclasses import dataclass

from app.proposals.sender import DEFAULT_SENDER, SenderProfileView, format_signature

RANGE_NOTE = (
    "Stima solo per te, IVA esclusa. Non va in email né al prospect: "
    "va confermata dopo una call e uno scope chiuso."
)


@dataclass(frozen=True)
class ProposalDraft:
    summary: str
    priority_problems: list[dict]
    recommended_service: str
    strategy: str
    email_subject: str
    email_body: str
    brief: str
    range_min: int
    range_max: int
    currency: str
    range_note: str


def build_proposal_draft(
    *,
    domain: str,
    url: str,
    company_name: str | None,
    city: str | None,
    findings: list,
    website_score,
    opportunity_score,
    sender: SenderProfileView | None = None,
) -> ProposalDraft:
    name = company_name or domain
    place = f" a {city}" if city else ""
    website_overall = website_score.overall_score if website_score else None
    opportunity_value = opportunity_score.opportunity_score if opportunity_score else None
    priority = opportunity_score.priority if opportunity_score else None
    service = (
        opportunity_score.recommended_service
        if opportunity_score
        else "Intervento sul sito e sulla presenza digitale"
    )
    problems = _priority_problems(findings)
    range_min, range_max = estimate_range(service, website_overall, priority)
    summary = _summary(name, domain, website_overall, opportunity_value, priority, service, problems)
    strategy = _strategy(service, problems, website_overall)
    brief = _brief(name, url, domain, website_overall, opportunity_value, service, problems, range_min, range_max)
    email_subject = f"{name}: un'idea concreta per il sito"
    email_body = _email(name, place, domain, service, problems, sender or DEFAULT_SENDER)
    return ProposalDraft(
        summary=summary,
        priority_problems=problems,
        recommended_service=service,
        strategy=strategy,
        email_subject=email_subject[:255],
        email_body=email_body,
        brief=brief,
        range_min=range_min,
        range_max=range_max,
        currency="EUR",
        range_note=RANGE_NOTE,
    )


def estimate_range(service: str, website_overall: int | None, priority: str | None) -> tuple[int, int]:
    text = service.lower()
    if "ripristino" in text or "ricostruzione" in text:
        low, high = 6000, 16000
    elif "https" in text or "sicurezza" in text:
        low, high = 1500, 4000
    elif "redesign" in text:
        low, high = 5000, 12000
    elif "conversioni" in text and "cta" in text:
        low, high = 2500, 6000
    elif "mobile" in text or "responsive" in text:
        low, high = 3000, 8000
    elif "indicizzazione" in text or "seo tecnico" in text:
        low, high = 1500, 4500
    elif "restyling" in text:
        low, high = 4000, 10000
    elif "ottimizzazione mirata" in text:
        low, high = 2500, 6500
    elif "manutenzione" in text:
        low, high = 800, 2500
    else:
        low, high = 2500, 8000
    if website_overall is not None and website_overall < 40:
        high = int(high * 1.15)
    if priority == "VERY_HIGH":
        high = int(high * 1.1)
    return low, high


def _priority_problems(findings: list) -> list[dict]:
    ranked = sorted(
        [item for item in findings if getattr(item, "severity", "") in {"critical", "high", "medium"}],
        key=lambda item: {"critical": 0, "high": 1, "medium": 2}.get(item.severity, 9),
    )
    problems: list[dict] = []
    for item in ranked[:5]:
        problems.append(
            {
                "code": item.code,
                "severity": item.severity,
                "title": item.title,
                "recommendation": item.recommendation,
            }
        )
    return problems


def _summary(
    name: str,
    domain: str,
    website_overall: int | None,
    opportunity_value: int | None,
    priority: str | None,
    service: str,
    problems: list[dict],
) -> str:
    site_bit = f"Website Score {website_overall}/100" if website_overall is not None else "sito analizzato"
    opp_bit = ""
    if opportunity_value is not None:
        opp_bit = f", Opportunity Score {opportunity_value}/100"
        if priority:
            opp_bit += f" ({priority})"
    top = problems[0]["title"] if problems else "alcuni limiti misurabili sulla presenza digitale"
    return (
        f"{name} ({domain}) ha un {site_bit}{opp_bit}. "
        f"Il problema più evidente è: {top}. "
        f"Il servizio più coerente con i finding è: {service}."
    )


def _strategy(service: str, problems: list[dict], website_overall: int | None) -> str:
    steps = [f"Partire da {service.lower()}."]
    if problems:
        steps.append(
            "Risolvere prima i finding ad alta gravità: "
            + ", ".join(item["title"] for item in problems[:3])
            + "."
        )
    if website_overall is not None and website_overall < 50:
        steps.append("Poi sistemare base tecnica, mobile e conversioni prima di campagne o contenuti extra.")
    else:
        steps.append("Poi consolidare SEO, fiducia e percorsi di contatto senza rifare tutto il sito.")
    steps.append("Chiudere con una passata di verifica (HTTPS, title, viewport, CTA, indicizzazione).")
    return " ".join(steps)


def _brief(
    name: str,
    url: str,
    domain: str,
    website_overall: int | None,
    opportunity_value: int | None,
    service: str,
    problems: list[dict],
    range_min: int,
    range_max: int,
) -> str:
    lines = [
        f"Cliente: {name}",
        f"Sito: {url} ({domain})",
        f"Website Score: {website_overall if website_overall is not None else 'n/d'}",
        f"Opportunity Score: {opportunity_value if opportunity_value is not None else 'n/d'}",
        f"Servizio proposto: {service}",
        f"Range indicativo: EUR {range_min}–{range_max} (IVA esclusa)",
        "Problemi prioritari:",
    ]
    if problems:
        lines.extend(f"- {item['severity']}: {item['title']}" for item in problems)
    else:
        lines.append("- Nessun finding ad alta gravità; intervento di miglioramento continuo.")
    lines.append("Vincolo: non inventare dati aziendali non misurati nell'audit.")
    return "\n".join(lines)


def _email(
    name: str,
    place: str,
    domain: str,
    service: str,
    problems: list[dict],
    sender: SenderProfileView,
) -> str:
    issue = problems[0]["title"] if problems else "alcuni limiti sul sito"
    extra = ""
    if len(problems) > 1:
        extra = " Tra gli altri punti: " + "; ".join(item["title"] for item in problems[1:3]) + "."
    return (
        f"Buongiorno,\n\n"
        f"mi chiamo {sender.display_name}. {sender.intro}\n\n"
        f"Vi scrivo perché ho analizzato il sito di {name}{place} ({domain}) "
        f"e ho visto dove la presenza digitale può funzionare meglio per chi vi cerca. "
        f"Non è una vendita a freddo: è un'occhiata concreta a quello che c'è oggi. "
        f"Il punto più evidente è: {issue}.{extra}\n\n"
        f"Un intervento utile sarebbe: {service}. "
        f"Se vi interessa, vi mando un brief di una pagina e ci sentiamo 15 minuti, senza impegno.\n\n"
        f"Un saluto,\n"
        f"{format_signature(sender)}"
    )
