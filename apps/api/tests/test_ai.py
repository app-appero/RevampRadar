from app.ai.parse import parse_ai_output
from app.ai.provider import get_ai_provider
from app.ai.schema import AIAnalysisResult
from app.ai.service import analyze_audit
from app.config import Settings
from app.scanner.findings import FindingDraft


def test_parse_ai_output_from_fenced_json() -> None:
    raw = """```json
    {
      "ui_score": null,
      "ux_score": 61,
      "mobile_usability_score": 40,
      "conversion_score": 35,
      "copy_score": 50,
      "trust_score": 55,
      "findings": [
        {
          "category": "conversion",
          "severity": "medium",
          "code": "AI_WEAK_HIERARCHY",
          "title": "Offerta poco chiara",
          "description": "H1 e title non descrivono l'azione.",
          "evidence": "H1: Benvenuti",
          "recommendation": "Usa un H1 orientato alla conversione.",
          "kind": "observation"
        }
      ],
      "strengths": ["HTTPS già citato nei finding"],
      "weaknesses": ["CTA assenti"],
      "recommendations": ["Aggiungi un'azione primaria"],
      "confidence": 0.4,
      "notes": "Screenshot non allegati"
    }
    ```"""
    result = parse_ai_output(raw)
    assert result.ui_score is None
    assert result.ux_score == 61
    assert result.findings[0].code == "AI_WEAK_HIERARCHY"
    assert result.confidence == 0.4


def test_parse_ai_output_rejects_invalid_json() -> None:
    try:
        parse_ai_output("not-json")
    except ValueError as exc:
        assert "valid JSON" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_provider_is_none_without_api_key() -> None:
    settings = Settings(openai_api_key="")
    assert get_ai_provider(settings) is None


def test_analyze_audit_skips_when_site_unreachable() -> None:
    settings = Settings(openai_api_key="sk-test")
    result, meta = analyze_audit(
        settings=settings,
        url="https://example.com",
        http={"ok": False, "error": "timeout"},
        html=None,
        seo=None,
        findings=[],
        screenshot_devices=[],
    )
    assert result is None
    assert meta["status"] == "skipped"
    assert meta["reason"] == "site_unreachable"


def test_analyze_audit_failure_does_not_raise(monkeypatch) -> None:
    class Boom:
        name = "boom"

        def analyze(self, user_payload: dict) -> AIAnalysisResult:
            raise RuntimeError("provider down")

    monkeypatch.setattr("app.ai.service.get_ai_provider", lambda settings: Boom())
    result, meta = analyze_audit(
        settings=Settings(openai_api_key="sk-test"),
        url="https://example.com",
        http={"ok": True},
        html={"title": "Hotel"},
        seo={},
        findings=[
            FindingDraft(
                category="conversion",
                severity="medium",
                code="HTML_WEAK_CTA",
                title="CTA deboli",
                description="d",
                evidence=None,
                recommendation="r",
            )
        ],
        screenshot_devices=["desktop"],
    )
    assert result is None
    assert meta["status"] == "failed"
    assert "provider down" in meta["error"]
