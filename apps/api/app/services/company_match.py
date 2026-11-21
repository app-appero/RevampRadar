"""Possibili duplicati di un'azienda, con punteggio: nome, Instagram, dominio, email, telefono.

Pensato per chi aggiunge candidate trovate fuori dall'app: una sola chiamata invece di scaricare
tutta la pipeline. Gli identificativi (handle, dominio, email, telefono) si confrontano esatti dopo
la normalizzazione, mai come sottostringhe: «cenere» non deve combaciare con gargidicenere.com.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session, selectinload

from app.discovery.normalize import is_shared_host
from app.discovery.osm import _INDUSTRY_TAGS
from app.discovery.province import fold
from app.models.entities import Company
from app.services.company_identity import url_key
from app.services.contact_status import normalize_lookup_email
from app.services.crm_service import company_domains, normalize_domain
from app.services.instagram import effective_instagram_handle, normalize_instagram_handle

_LEGAL_FORMS = re.compile(
    r"\b(?:s\s*\.?\s*r\s*\.?\s*l\s*\.?\s*s?|s\s*\.?\s*p\s*\.?\s*a|s\s*\.?\s*n\s*\.?\s*c|s\s*\.?\s*a\s*\.?\s*s"
    r"|s\s*\.?\s*a\s*\.?\s*p\s*\.?\s*a|s\s*\.?\s*c\s*\.?\s*a\s*\.?\s*r\s*\.?\s*l|soc(?:ieta)?\.?\s*coop(?:erativa)?"
    r"|cooperativa|societa|ditta|ltd|gmbh)\b\.?",
    re.IGNORECASE,
)
_AND_COMPANY = re.compile(r"(?:&|\be)\s*c\s*\.?(?=\s|$)", re.IGNORECASE)
_NON_WORD = re.compile(r"[^0-9a-z]+")
_STOPWORDS = frozenset(
    "di d da dal del della dello dei degli delle il lo la le i gli l e ed a al alla allo ai agli alle "
    "in con per su the of and c".split()
)
# Parole di settore: comuni a molte attività, pesano poco nel confronto dei nomi.
_EXTRA_GENERIC = (
    "bar caffe cafe bistrot ristorante trattoria osteria pizzeria hotel albergo agriturismo masseria b b bb "
    "studio centro casa salone negozio laboratorio officina azienda agricola gelateria pasticceria panificio "
    "forno macelleria fioreria fiori parrucchiere parrucchieri acconciature barber shop estetica beauty "
    "tappezzeria arredamenti arredamento ottica farmacia ferramenta falegnameria vivaio garden market "
    "boutique atelier store snack ristoro locanda residence camere"
).split()


def _generic_tokens() -> frozenset[str]:
    words: set[str] = set(_EXTRA_GENERIC)
    for key in _INDUSTRY_TAGS:
        words.update(name_tokens(key, keep_generic=True))
    return frozenset(words)


def normalize_name(name: str | None) -> str:
    """Nome confrontabile: senza accenti, maiuscole, punteggiatura, forma giuridica e articoli."""
    return " ".join(name_tokens(name, keep_generic=True))


def name_tokens(name: str | None, *, keep_generic: bool = False) -> list[str]:
    text = fold(name).replace("’", "'")
    text = _LEGAL_FORMS.sub(" ", text)
    text = _AND_COMPANY.sub(" ", text)
    tokens = [token for token in _NON_WORD.sub(" ", text).split() if token not in _STOPWORDS]
    if not keep_generic:
        tokens = [token for token in tokens if token not in GENERIC_TOKENS]
    return tokens


def compact(text: str | None) -> str:
    """Solo lettere e cifre: per confrontare un nome con un handle o un dominio."""
    return _NON_WORD.sub("", fold(text))


def normalize_phone_it(raw: str | None) -> str | None:
    """«+39 0363 111111», «0039-349 5776033» → numero nazionale «0363111111», «3495776033»."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0039"):
        digits = digits[4:]
    elif digits.startswith("39") and len(digits) >= 11:
        digits = digits[2:]
    return digits if len(digits) >= 6 else None


def domain_label(domain: str | None) -> str:
    """«www.tappezzeriaprandelli.com» → «tappezzeriaprandelli» (nome del sito senza estensione)."""
    host = (domain or "").lower().removeprefix("www.")
    parts = [part for part in host.split(".") if part]
    return compact(parts[0]) if len(parts) >= 2 else ""


GENERIC_TOKENS = _generic_tokens()


@dataclass
class MatchQuery:
    name: str | None = None
    instagram: str | None = None
    domain: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None


@dataclass
class Candidate:
    company: Company
    score: int = 0
    reasons: list[dict] = field(default_factory=list)


def _token_weight(token: str) -> float:
    return 0.2 if token in GENERIC_TOKENS else 1.0


def name_similarity(left: str | None, right: str | None) -> float:
    """0-1. Media fra Jaccard pesata e contenimento; 0 senza almeno una parola distintiva comune."""
    a = set(name_tokens(left, keep_generic=True))
    b = set(name_tokens(right, keep_generic=True))
    shared = a & b
    if not any(token not in GENERIC_TOKENS for token in shared):
        return 0.0
    weight = lambda tokens: sum(_token_weight(token) for token in tokens)  # noqa: E731
    union = weight(a | b)
    smaller = min(weight(a), weight(b))
    jaccard = weight(shared) / union if union else 0.0
    containment = weight(shared) / smaller if smaller else 0.0
    return round((jaccard + containment) / 2, 3)


def find_matches(session: Session, query: MatchQuery, *, limit: int = 10, min_score: int = 50) -> list[Candidate]:
    handle = None
    if query.instagram:
        try:
            handle = normalize_instagram_handle(query.instagram)
        except ValueError:
            handle = None
    email = normalize_lookup_email(query.email or "") if query.email else None
    phone = normalize_phone_it(query.phone)
    domain = normalize_domain(query.domain)
    shared_page = url_key(query.domain) if domain and is_shared_host(domain) else None
    name = (query.name or "").strip() or None
    name_norm = normalize_name(name)
    name_compact = compact(" ".join(name_tokens(name, keep_generic=True))) if name else ""
    city = fold(query.city) if query.city else ""

    results: list[Candidate] = []
    for company in session.query(Company).options(selectinload(Company.websites), selectinload(Company.opportunity)):
        their_handle = effective_instagram_handle(company)
        their_domains = company_domains(company)
        their_compact = compact(" ".join(name_tokens(company.name, keep_generic=True)))

        # Identificativi esatti: valgono a prescindere dalla città.
        signals: list[tuple[int, str, str]] = []
        if handle and their_handle == handle:
            signals.append((100, "instagram_handle", handle))
        if email and (company.email or "").strip().lower() == email:
            signals.append((90, "email", email))
        if domain and not shared_page and domain in their_domains:
            signals.append((90, "domain", domain))
        if shared_page:
            pages = {url_key(company.website_url)} | {url_key(site.normalized_url) for site in company.websites}
            if shared_page in pages:
                signals.append((90, "website_url", shared_page))
        if phone and normalize_phone_it(company.phone) == phone:
            signals.append((75, "phone", phone))
        if handle and len(handle) >= 6 and compact(handle) == their_compact:
            signals.append((85, "instagram_matches_name", company.name))
        if domain and not shared_page and len(domain_label(domain)) >= 6 and domain_label(domain) == their_compact:
            signals.append((80, "domain_matches_name", company.name))

        # Nome: confronto con nome, handle e nome del sito dell'azienda; la città lo corregge.
        name_signals: list[tuple[int, str, str]] = []
        if name:
            if name_tokens(name) and name_norm == normalize_name(company.name):
                name_signals.append((70, "name_exact", company.name))
            if len(name_compact) >= 6 and their_handle and compact(their_handle) == name_compact:
                name_signals.append((85, "name_matches_instagram", their_handle))
            labels = {domain_label(item) for item in their_domains if not is_shared_host(item)}
            if len(name_compact) >= 6 and name_compact in labels:
                name_signals.append((80, "name_matches_domain", name_compact))
            similarity = name_similarity(name, company.name)
            if similarity >= 0.5:
                name_signals.append((int(40 + 30 * similarity), "name_similar", f"{similarity:.2f}"))

        if not signals and not name_signals:
            continue
        best_name = max((item[0] for item in name_signals), default=0)
        if city and name_signals and not signals:
            their_city = fold(company.city)
            if their_city == city:
                best_name += 10
                name_signals.append((10, "same_city", company.city or ""))
            elif their_city:
                best_name -= 25
                name_signals.append((-25, "other_city", company.city or ""))
        scores = [item[0] for item in signals] + ([best_name] if name_signals else [])
        # Prove indipendenti: ogni identificativo diverso, più il nome contato una volta sola.
        independent = len({code for _, code, _ in signals}) + (1 if best_name > 0 and name_signals else 0)
        score = max(0, min(100, max(scores) + 5 * max(0, independent - 1)))
        if score >= min_score:
            reasons = [
                {"signal": code, "detail": detail, "points": points} for points, code, detail in signals + name_signals
            ]
            results.append(Candidate(company=company, score=score, reasons=reasons))
    results.sort(key=lambda item: (-item.score, fold(item.company.name)))
    return results[:limit]


def normalized_query(query: MatchQuery) -> dict[str, str | None]:
    """Come sono stati letti i dati della richiesta: utile per capire un mancato riscontro."""
    try:
        handle = normalize_instagram_handle(query.instagram) if query.instagram else None
    except ValueError:
        handle = None
    return {
        "name": normalize_name(query.name) or None,
        "instagram": handle,
        "domain": normalize_domain(query.domain),
        "email": normalize_lookup_email(query.email or "") if query.email else None,
        "phone": normalize_phone_it(query.phone),
        "city": fold(query.city) or None,
    }


def strength(score: int) -> str:
    return "strong" if score >= 85 else "probable" if score >= 65 else "weak"
