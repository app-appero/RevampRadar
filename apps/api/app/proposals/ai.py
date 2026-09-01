from __future__ import annotations

import json
import logging

from app.ai.parse import parse_json_object
from app.ai.provider import get_ai_provider
from app.config import Settings
from app.proposals.builder import ProposalDraft
from app.proposals.prompt_v1 import SYSTEM_PROMPT
from app.proposals.sender import SenderProfileView, email_leaks_price, ensure_signature

logger = logging.getLogger(__name__)


def polish_proposal(
    settings: Settings,
    draft: ProposalDraft,
    facts: dict,
    sender: SenderProfileView,
) -> ProposalDraft | None:
    provider = get_ai_provider(settings)
    if provider is None:
        return None
    payload = {
        "facts": facts,
        "draft": {
            "summary": draft.summary,
            "strategy": draft.strategy,
            "email_subject": draft.email_subject,
            "email_body": draft.email_body,
            "brief": draft.brief,
            "recommended_service": draft.recommended_service,
            "range_min": draft.range_min,
            "range_max": draft.range_max,
            "priority_problems": draft.priority_problems,
        },
        "constraints": [
            "Non inventare dati aziendali assenti dai facts.",
            "Non modificare range o servizio consigliato.",
            "Non inserire prezzi in email_body o email_subject.",
            "Conserva presentazione e firma del mittente.",
        ],
    }
    try:
        content = provider.complete_json(
            SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
            temperature=0.3,
        )
        parsed = parse_json_object(content)
    except Exception as exc:
        logger.warning("Proposal AI polish failed: %s", exc)
        return None
    email_body = str(parsed.get("email_body") or draft.email_body)
    if email_leaks_price(email_body, draft.range_min, draft.range_max):
        email_body = draft.email_body
    email_body = ensure_signature(email_body, sender)
    return ProposalDraft(
        summary=str(parsed.get("summary") or draft.summary),
        priority_problems=draft.priority_problems,
        recommended_service=draft.recommended_service,
        strategy=str(parsed.get("strategy") or draft.strategy),
        email_subject=str(parsed.get("email_subject") or draft.email_subject)[:255],
        email_body=email_body,
        brief=str(parsed.get("brief") or draft.brief),
        range_min=draft.range_min,
        range_max=draft.range_max,
        currency=draft.currency,
        range_note=draft.range_note,
    )
