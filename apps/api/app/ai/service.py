from __future__ import annotations

import logging
from typing import Any

from app.ai.prompt_v1 import PROMPT_VERSION
from app.ai.provider import get_ai_provider
from app.ai.schema import AIAnalysisResult
from app.config import Settings
from app.scanner.findings import FindingDraft

logger = logging.getLogger(__name__)

AI_CATEGORIES = {"ui", "ux", "mobile", "conversion", "copy", "trust"}


def analyze_audit(
    *,
    settings: Settings,
    url: str,
    http: dict | None,
    html: dict | None,
    seo: dict | None,
    findings: list[FindingDraft],
    screenshot_devices: list[str],
) -> tuple[AIAnalysisResult | None, dict[str, Any]]:
    meta: dict[str, Any] = {
        "status": "skipped",
        "prompt_version": PROMPT_VERSION,
        "provider": None,
        "model": None,
        "result": None,
        "error": None,
    }
    if http and http.get("ok") is False:
        meta["reason"] = "site_unreachable"
        return None, meta
    provider = get_ai_provider(settings)
    if provider is None:
        meta["reason"] = "missing_api_key"
        return None, meta

    payload = {
        "url": url,
        "screenshots_attached": False,
        "screenshots_captured": screenshot_devices,
        "http": http,
        "html": html,
        "seo": seo,
        "findings": [
            {
                "category": item.category,
                "severity": item.severity,
                "code": item.code,
                "title": item.title,
                "description": item.description,
                "evidence": item.evidence,
            }
            for item in findings
        ],
        "constraints": [
            "Gli screenshot non sono allegati: non inventare dettagli visivi.",
            "Non inventare dati aziendali non presenti nel JSON.",
        ],
    }
    meta["provider"] = provider.name
    meta["model"] = provider.model
    try:
        result = provider.analyze(payload)
    except Exception as exc:
        logger.warning("AI analysis failed: %s", exc)
        meta["status"] = "failed"
        meta["error"] = str(exc)
        return None, meta
    meta["status"] = "completed"
    meta["result"] = result.model_dump()
    return result, meta


def ai_findings(result: AIAnalysisResult) -> list[FindingDraft]:
    drafts: list[FindingDraft] = []
    for item in result.findings[:6]:
        category = item.category if item.category in AI_CATEGORIES else "ux"
        code = item.code if item.code.startswith("AI_") else f"AI_{item.code}"[:64]
        drafts.append(
            FindingDraft(
                category=category,
                severity=item.severity,
                code=code,
                title=item.title,
                description=item.description,
                evidence=f"{item.kind}: {item.evidence}",
                recommendation=item.recommendation,
                source_type="ai",
            )
        )
    return drafts
