from __future__ import annotations

from typing import Protocol

from app.ai.schema import AIAnalysisResult
from app.config import Settings


class AIProvider(Protocol):
    name: str

    def analyze(self, user_payload: dict) -> AIAnalysisResult:
        """Run qualitative analysis. Raise on provider/transport/parse failure."""


class NullAIProvider:
    name = "null"

    def analyze(self, user_payload: dict) -> AIAnalysisResult:
        raise RuntimeError("AI provider is not configured.")


def get_ai_provider(settings: Settings) -> AIProvider | None:
    if not settings.openai_api_key.strip():
        return None
    from app.ai.openai_provider import OpenAICompatibleProvider

    return OpenAICompatibleProvider(settings)
