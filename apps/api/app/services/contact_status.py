"""Stato di contatto per indirizzo email.

Serve a intercettare le bozze esterne (es. Aruba) intestate ad aziende già contattate prima
di inviarle una seconda volta. Sola lettura: non modifica nulla e non invia nulla.

Un'email è collegata a un'azienda se compare come email dell'azienda, come destinatario di
un'attività o nel testo di una nota/attività. L'azienda risulta già contattata se:
- lo stato CRM è contacted o successivo (replied, meeting, proposal, won);
- c'è un invio registrato (email_sent, dm_sent, concept_sent o un'attività email svolta);
- ha un tag di invio (segmento «inviato»/«inviata», es. lotto2-20261116-inviato) o uno dei
  tag passati nella richiesta.
La data è quella dell'ultimo contatto registrato (attività, cambio stato o data nel tag).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.models.entities import Activity, Company, Opportunity, OpportunityNote, OpportunityTag

CONTACTED_STATUSES = frozenset({"contacted", "replied", "meeting", "proposal", "won"})
OUTREACH_TYPES = frozenset({"email_sent", "dm_sent", "concept_sent"})
MAX_EMAILS = 500

_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_STATUS_TO = re.compile(r"→\s*(" + "|".join(sorted(CONTACTED_STATUSES)) + r")\b")
_TAG_DATE = re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)")
_SENT_WORDS = frozenset({"inviato", "inviata", "inviati", "inviate"})


@dataclass
class _Evidence:
    reasons: list[str] = field(default_factory=list)
    moments: list[tuple[date, datetime | None, str]] = field(default_factory=list)

    def add_moment(self, day: date | None, moment: datetime | None, source: str) -> None:
        if day is not None:
            self.moments.append((day, moment, source))

    def latest(self) -> tuple[date | None, datetime | None, str | None]:
        if not self.moments:
            return None, None, None
        # Ultimo giorno; a parità di giorno conta chi ha anche l'orario.
        day, moment, source = max(self.moments, key=lambda item: (item[0], item[1] is not None, item[1] or 0))
        return day, moment, source


def normalize_lookup_email(raw: str) -> str | None:
    """Estrae l'indirizzo da "Nome <a@b.it>", "mailto:a@b.it" ecc., in minuscolo."""
    match = _EMAIL.search((raw or "").strip())
    return match.group(0).lower().strip(".") if match else None


def is_sent_tag(name: str, extra_tags: set[str] | frozenset[str] = frozenset()) -> bool:
    normalized = " ".join(name.strip().lower().split())
    if normalized in extra_tags:
        return True
    segments = [item for item in re.split(r"[-_\s]+", normalized) if item]
    for index, segment in enumerate(segments):
        if segment in _SENT_WORDS and (index == 0 or segments[index - 1] != "non"):
            return True
    return False


def _tag_date(name: str) -> date | None:
    match = _TAG_DATE.search(name)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _mentions(text: str | None, email: str) -> bool:
    if not text:
        return False
    pattern = r"(?<![\w.+%-])" + re.escape(email) + r"(?!\.?[\w-])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _like(email: str) -> str:
    escaped = email.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _linked_opportunities(session: Session, email: str) -> dict[UUID, set[str]]:
    """Opportunità collegate all'email, con il motivo del collegamento."""
    pattern = _like(email)
    linked: dict[UUID, set[str]] = {}

    companies = (
        session.query(Company.id, Company.email)
        .filter(func.lower(Company.email).like(pattern, escape="\\"))
        .all()
    )
    company_ids = [company_id for company_id, value in companies if _mentions(value, email)]
    if company_ids:
        for opportunity_id, in session.query(Opportunity.id).filter(Opportunity.company_id.in_(company_ids)):
            linked.setdefault(opportunity_id, set()).add("company_email")

    activities = (
        session.query(Activity.opportunity_id, Activity.recipient, Activity.note)
        .filter(
            or_(
                func.lower(Activity.recipient).like(pattern, escape="\\"),
                func.lower(Activity.note).like(pattern, escape="\\"),
            )
        )
        .all()
    )
    for opportunity_id, recipient, note in activities:
        if _mentions(recipient, email):
            linked.setdefault(opportunity_id, set()).add("activity_recipient")
        elif _mentions(note, email):
            linked.setdefault(opportunity_id, set()).add("activity_note")

    notes = (
        session.query(OpportunityNote.opportunity_id, OpportunityNote.body)
        .filter(func.lower(OpportunityNote.body).like(pattern, escape="\\"))
        .all()
    )
    for opportunity_id, body in notes:
        if _mentions(body, email):
            linked.setdefault(opportunity_id, set()).add("note")
    return linked


def _evidence(opportunity: Opportunity, extra_tags: frozenset[str]) -> _Evidence:
    evidence = _Evidence()
    if opportunity.status in CONTACTED_STATUSES:
        evidence.reasons.append(f"status:{opportunity.status}")
    for link in opportunity.tag_links:
        tag = link.tag
        if tag is not None and is_sent_tag(tag.name, extra_tags):
            evidence.reasons.append(f"tag:{tag.name}")
            evidence.add_moment(_tag_date(tag.name), None, f"tag:{tag.name}")
    for activity in opportunity.activities:
        moment = _as_utc(activity.occurred_at) or _as_utc(activity.completed_at)
        day = activity.occurred_on or (moment.date() if moment else None)
        sent = activity.type in OUTREACH_TYPES or (
            activity.type == "email" and (activity.due_at is None or activity.completed_at is not None)
        )
        if sent:
            evidence.reasons.append(f"activity:{activity.type}")
            evidence.add_moment(day, moment, f"activity:{activity.type}")
        elif activity.type == "status_change" and _STATUS_TO.search(activity.note or ""):
            evidence.add_moment(day, moment, "status_change")
    # Senza alcun segnale di contatto, un cambio stato passato non basta (es. poi tornato indietro).
    if not evidence.reasons:
        evidence.moments.clear()
    return evidence


def contact_status(session: Session, emails: list[str], contacted_tags: list[str] | None = None) -> dict:
    extra_tags = frozenset(" ".join(tag.strip().lower().split()) for tag in contacted_tags or [] if tag.strip())
    results: list[dict] = []
    cache: dict[str, dict[UUID, set[str]]] = {}
    for raw in emails:
        email = normalize_lookup_email(raw)
        item = {
            "email": raw,
            "normalized_email": email,
            "valid": email is not None,
            "already_contacted": False,
            "status": None,
            "contacted_on": None,
            "contacted_at": None,
            "matches": [],
        }
        if email is None:
            results.append(item)
            continue
        if email not in cache:
            cache[email] = _linked_opportunities(session, email)
        linked = cache[email]
        opportunities = (
            session.query(Opportunity)
            .options(
                selectinload(Opportunity.company),
                selectinload(Opportunity.activities),
                selectinload(Opportunity.tag_links).selectinload(OpportunityTag.tag),
            )
            .filter(Opportunity.id.in_(list(linked)))
            .all()
            if linked
            else []
        )
        matches = []
        for opportunity in opportunities:
            evidence = _evidence(opportunity, extra_tags)
            day, moment, source = evidence.latest()
            matches.append(
                {
                    "opportunity_id": opportunity.id,
                    "company_id": opportunity.company_id,
                    "company_name": opportunity.company.name if opportunity.company else "",
                    "status": opportunity.status,
                    "already_contacted": bool(evidence.reasons),
                    "contacted_on": day,
                    "contacted_at": moment,
                    "date_source": source,
                    "evidence": list(dict.fromkeys(evidence.reasons)),
                    "matched_on": sorted(linked[opportunity.id]),
                }
            )
        # Prima le già contattate, poi per data di contatto più recente.
        matches.sort(
            key=lambda match: (
                not match["already_contacted"],
                -(match["contacted_on"].toordinal() if match["contacted_on"] else 0),
                match["company_name"].lower(),
            )
        )
        item["matches"] = matches
        if matches:
            top = matches[0]
            item["status"] = top["status"]
            item["already_contacted"] = top["already_contacted"]
            item["contacted_on"] = top["contacted_on"]
            item["contacted_at"] = top["contacted_at"]
        results.append(item)
    return {
        "checked": len(results),
        "already_contacted": sum(1 for item in results if item["already_contacted"]),
        "results": results,
    }
