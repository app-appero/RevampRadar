from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SenderLink:
    label: str
    url: str


@dataclass(frozen=True)
class SenderProfileView:
    display_name: str
    intro: str
    website_url: str
    freelancer_links: tuple[SenderLink, ...]
    social_links: tuple[SenderLink, ...]


DEFAULT_SENDER = SenderProfileView(
    display_name="Luca Bianchi",
    intro=(
        "Sono uno sviluppatore web freelance: aiuto piccole attività a sistemare "
        "sito, mobile e prenotazioni, così i clienti vi trovano e vi scrivono."
    ),
    website_url="https://www.lucabianchi.dev",
    freelancer_links=(
        SenderLink(label="Upwork", url="https://www.upwork.com/freelancers/~esempio-luca"),
        SenderLink(label="Fiverr", url="https://www.fiverr.com/lucabianchi_esempio"),
    ),
    social_links=(
        SenderLink(label="LinkedIn", url="https://www.linkedin.com/in/luca-bianchi-esempio"),
        SenderLink(label="Instagram", url="https://www.instagram.com/lucabianchi.dev"),
    ),
)


def links_from_payload(raw: list | None) -> tuple[SenderLink, ...]:
    items: list[SenderLink] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        url = str(item.get("url") or "").strip()
        if label and url:
            items.append(SenderLink(label=label, url=url))
    return tuple(items)


def links_to_payload(links: tuple[SenderLink, ...]) -> list[dict]:
    return [{"label": item.label, "url": item.url} for item in links]


def format_signature(sender: SenderProfileView) -> str:
    lines = [sender.display_name]
    if sender.website_url:
        lines.append(sender.website_url)
    freelancer = _format_link_block("Piattaforme", sender.freelancer_links)
    socials = _format_link_block("Social", sender.social_links)
    if freelancer:
        lines.append("")
        lines.append(freelancer)
    if socials:
        lines.append("")
        lines.append(socials)
    return "\n".join(lines).strip()


def email_leaks_price(body: str, range_min: int, range_max: int) -> bool:
    text = body.lower()
    if str(range_min) in body and str(range_max) in body:
        return True
    markers = ("iva esclusa", "€", " eur", "preventivo", "range è")
    return any(marker in text for marker in markers)


def email_proposes_time_slot(body: str) -> bool:
    """Vero se l'email fissa una durata/orario per una chiamata (l'AI non deve farlo)."""
    text = body.lower()
    markers = (
        "10 minuti", "15 minuti", "20 minuti", "30 minuti",
        "un quarto d'ora", "quarto d'ora", "mezz'ora", "mezzora",
        "dieci minuti", "quindici minuti", "venti minuti", "trenta minuti",
    )
    return any(marker in text for marker in markers)


def ensure_signature(body: str, sender: SenderProfileView) -> str:
    if sender.website_url and sender.website_url in body:
        return body.rstrip()
    return body.rstrip() + "\n\n" + format_signature(sender)


def _format_link_block(title: str, links: tuple[SenderLink, ...]) -> str:
    if not links:
        return ""
    rows = "\n".join(f"{item.label}: {item.url}" for item in links)
    return f"{title}:\n{rows}"
