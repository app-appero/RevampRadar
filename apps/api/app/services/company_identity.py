"""Aziende già presenti con lo stesso profilo Instagram, dominio del sito o email.

Usato da POST /companies (409 con l'id esistente) e dall'import di handle Instagram: un
duplicato per questi identificativi non deve generare una seconda scheda.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import Text, cast, func, or_
from sqlalchemy.orm import Session, selectinload

from app.discovery.normalize import is_shared_host
from app.models.entities import Company, Website
from app.services.crm_service import _like_escape, company_domains, normalize_domain
from app.services.instagram import effective_instagram_handle


@dataclass
class IdentityMatch:
    company: Company
    reasons: list[str] = field(default_factory=list)


def find_identity_duplicates(
    session: Session,
    *,
    instagram_handle: str | None = None,
    website_url: str | None = None,
    email: str | None = None,
) -> list[IdentityMatch]:
    """Aziende con lo stesso handle IG, dominio (o URL esatto su host condivisi) o email."""
    found: dict[object, IdentityMatch] = {}

    def add(company: Company, reason: str) -> None:
        match = found.setdefault(company.id, IdentityMatch(company=company))
        if reason not in match.reasons:
            match.reasons.append(reason)

    if instagram_handle:
        handle = instagram_handle.lower()
        rows = (
            session.query(Company)
            .filter(
                or_(
                    Company.instagram_handle == handle,
                    func.lower(cast(Company.extra, Text)).like(f"%{_like_escape(handle)}%", escape="\\"),
                )
            )
            .all()
        )
        for company in rows:
            if effective_instagram_handle(company) == handle:
                add(company, "instagram_handle")

    domain = normalize_domain(website_url)
    if domain:
        if is_shared_host(domain):
            # Pagina social o sito gratuito: conta solo la stessa pagina, non il dominio.
            target = url_key(website_url)
            rows = (
                session.query(Company)
                .options(selectinload(Company.websites))
                .filter(
                    or_(
                        func.lower(Company.website_url).like(f"%{_like_escape(target)}%", escape="\\"),
                        Company.websites.any(
                            func.lower(Website.normalized_url).like(f"%{_like_escape(target)}%", escape="\\")
                        ),
                    )
                )
                .all()
            )
            for company in rows:
                keys = {url_key(company.website_url)} | {url_key(site.normalized_url) for site in company.websites}
                if target in keys:
                    add(company, "website_url")
        else:
            rows = (
                session.query(Company)
                .options(selectinload(Company.websites))
                .filter(
                    or_(
                        Company.websites.any(func.lower(Website.domain).in_([domain, f"www.{domain}"])),
                        func.lower(Company.website_url).like(f"%{_like_escape(domain)}%", escape="\\"),
                    )
                )
                .all()
            )
            for company in rows:
                if domain in company_domains(company):
                    add(company, "domain")

    if email:
        for company in session.query(Company).filter(func.lower(Company.email) == email.strip().lower()):
            add(company, "email")

    return sorted(found.values(), key=lambda item: (item.company.created_at, str(item.company.id)))


def url_key(value: str | None) -> str:
    """URL confrontabile: senza schema, www., query, frammento e barra finale."""
    text = (value or "").strip().lower().split("#")[0].split("?")[0]
    text = text.split("://", 1)[-1].removeprefix("www.")
    return text.rstrip("/")


def describe(reasons: list[str]) -> str:
    labels = {
        "instagram_handle": "stesso profilo Instagram",
        "domain": "stesso dominio del sito",
        "website_url": "stessa pagina web",
        "email": "stessa email",
    }
    return ", ".join(labels.get(item, item) for item in reasons)
