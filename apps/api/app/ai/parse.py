from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.ai.schema import AIAnalysisResult

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_ai_output(raw: str) -> AIAnalysisResult:
    cleaned = _FENCE.sub("", raw.strip()).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI output is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("AI output must be a JSON object.")
    try:
        return AIAnalysisResult.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"AI output does not match schema: {exc}") from exc
