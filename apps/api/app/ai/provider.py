from __future__ import annotations

from typing import Protocol

from app.ai.schema import AIAnalysisResult
from app.config import Settings


class AIProvider(Protocol):
    name: str
    model: str

    def analyze(self, user_payload: dict) -> AIAnalysisResult:
        """Run qualitative analysis. Raise on provider/transport/parse failure."""

    def complete_json(self, system: str, user: str, temperature: float = 0.2) -> str:
        """Return assistant text expected to be a JSON object."""


def get_ai_provider(settings: Settings) -> AIProvider | None:
    choice = (settings.ai_provider or "claude").strip().lower()
    if choice in {"claude", "anthropic"}:
        if not settings.anthropic_api_key.strip():
            return None
        from app.ai.claude_provider import ClaudeProvider

        return ClaudeProvider(settings)
    if choice in {"openai", "openai-compatible"}:
        if not settings.openai_api_key.strip():
            return None
        from app.ai.openai_provider import OpenAICompatibleProvider

        return OpenAICompatibleProvider(settings)
    return None
