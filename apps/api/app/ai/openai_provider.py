from __future__ import annotations

import json
from urllib.parse import urljoin

import httpx

from app.ai.parse import parse_ai_output
from app.ai.prompt_v1 import SYSTEM_PROMPT
from app.ai.schema import AIAnalysisResult
from app.config import Settings


class OpenAICompatibleProvider:
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def model(self) -> str:
        return self._settings.openai_model

    def analyze(self, user_payload: dict) -> AIAnalysisResult:
        content = self.complete_json(
            SYSTEM_PROMPT,
            json.dumps(user_payload, ensure_ascii=False),
            temperature=0.2,
        )
        return parse_ai_output(content)

    def complete_json(self, system: str, user: str, temperature: float = 0.2) -> str:
        base = self._settings.openai_base_url.rstrip("/") + "/"
        url = urljoin(base, "chat/completions")
        body = {
            "model": self._settings.openai_model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(
            connect=15.0,
            read=self._settings.openai_timeout_seconds,
            write=30.0,
            pool=10.0,
        )
        with httpx.Client(timeout=timeout) as client:
            try:
                response = client.post(url, json=body, headers=headers)
            except httpx.HTTPError as exc:
                raise RuntimeError(f"AI provider request failed: {exc}") from exc
            if response.status_code == 400 and "response_format" in (response.text or "").lower():
                body.pop("response_format", None)
                response = client.post(url, json=body, headers=headers)
            if response.status_code >= 400:
                raise RuntimeError(f"AI provider HTTP {response.status_code}: {response.text[:500]}")
            payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("AI provider returned an unexpected payload.") from exc
        if not content:
            raise RuntimeError("AI provider returned empty content.")
        return content
