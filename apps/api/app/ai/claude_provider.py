from __future__ import annotations

import json
from urllib.parse import urljoin

import httpx

from app.ai.parse import parse_ai_output
from app.ai.prompt_v1 import SYSTEM_PROMPT
from app.ai.schema import AIAnalysisResult
from app.config import Settings


class ClaudeProvider:
    name = "claude"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def model(self) -> str:
        return self._settings.anthropic_model

    def analyze(self, user_payload: dict) -> AIAnalysisResult:
        content = self.complete_json(
            SYSTEM_PROMPT,
            json.dumps(user_payload, ensure_ascii=False),
            temperature=0.2,
        )
        return parse_ai_output(content)

    def complete_json(self, system: str, user: str, temperature: float = 0.2) -> str:
        base = self._settings.anthropic_base_url.rstrip("/") + "/"
        url = urljoin(base, "v1/messages")
        body = {
            "model": self._settings.anthropic_model,
            "max_tokens": 4096,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "x-api-key": self._settings.anthropic_api_key,
            "anthropic-version": self._settings.anthropic_version,
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(
            connect=15.0,
            read=self._settings.openai_timeout_seconds,
            write=30.0,
            pool=10.0,
        )
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"AI provider request failed: {exc}") from exc
        if response.status_code >= 400:
            raise RuntimeError(f"AI provider HTTP {response.status_code}: {response.text[:500]}")
        try:
            blocks = response.json().get("content") or []
        except ValueError as exc:
            raise RuntimeError("AI provider returned an unexpected payload.") from exc
        parts = [
            block.get("text", "")
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        content = "".join(parts).strip()
        if not content:
            raise RuntimeError("AI provider returned empty content.")
        return content
