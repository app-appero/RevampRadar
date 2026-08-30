from __future__ import annotations

import json
import logging
from urllib.parse import urljoin

import httpx

from app.config import Settings
from app.proposals.builder import ProposalDraft
from app.proposals.prompt_v1 import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def polish_proposal(settings: Settings, draft: ProposalDraft, facts: dict) -> ProposalDraft | None:
    if not settings.openai_api_key.strip():
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
        ],
    }
    base = settings.openai_base_url.rstrip("/") + "/"
    url = urljoin(base, "chat/completions")
    body = {
        "model": settings.openai_model,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(settings.openai_timeout_seconds)
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=body, headers=headers)
            if response.status_code == 400 and "response_format" in (response.text or "").lower():
                body.pop("response_format", None)
                response = client.post(url, json=body, headers=headers)
            if response.status_code >= 400:
                raise RuntimeError(f"AI provider HTTP {response.status_code}: {response.text[:400]}")
            content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except Exception as exc:
        logger.warning("Proposal AI polish failed: %s", exc)
        return None
    return ProposalDraft(
        summary=str(parsed.get("summary") or draft.summary),
        priority_problems=draft.priority_problems,
        recommended_service=draft.recommended_service,
        strategy=str(parsed.get("strategy") or draft.strategy),
        email_subject=str(parsed.get("email_subject") or draft.email_subject)[:255],
        email_body=str(parsed.get("email_body") or draft.email_body),
        brief=str(parsed.get("brief") or draft.brief),
        range_min=draft.range_min,
        range_max=draft.range_max,
        currency=draft.currency,
        range_note=draft.range_note,
    )
