import pytest

from app.config import Settings
from app.services.ai_settings import (
    effective_settings,
    is_ai_available,
    key_preview,
    update_ai_credentials,
)


def test_key_preview_masks_value() -> None:
    assert key_preview("sk-ant-1234567890") == "••••7890"
    assert key_preview(None) is None
    assert key_preview("") is None


def test_effective_settings_overrides_env_with_db_credentials(db_session) -> None:
    base = Settings(ai_provider="claude", anthropic_api_key="", openai_api_key="")
    assert is_ai_available(db_session, base) is False

    update_ai_credentials(db_session, provider="claude", anthropic_api_key="sk-ant-test", openai_api_key=None)

    resolved = effective_settings(db_session, base)
    assert resolved.anthropic_api_key == "sk-ant-test"
    assert is_ai_available(db_session, base) is True


def test_switching_provider_without_its_key_is_not_available(db_session) -> None:
    base = Settings(anthropic_api_key="", openai_api_key="")
    update_ai_credentials(db_session, provider="claude", anthropic_api_key="sk-ant-test", openai_api_key=None)
    assert is_ai_available(db_session, base) is True

    update_ai_credentials(db_session, provider="openai", anthropic_api_key=None, openai_api_key=None)
    assert is_ai_available(db_session, base) is False


def test_update_ai_credentials_rejects_invalid_provider(db_session) -> None:
    with pytest.raises(ValueError):
        update_ai_credentials(db_session, provider="gemini", anthropic_api_key=None, openai_api_key=None)


def test_empty_string_clears_a_stored_key(db_session) -> None:
    update_ai_credentials(db_session, provider="claude", anthropic_api_key="sk-ant-test", openai_api_key=None)
    row = update_ai_credentials(db_session, provider=None, anthropic_api_key="", openai_api_key=None)
    assert row.anthropic_api_key is None


def test_ai_credentials_api_roundtrip(client) -> None:
    first = client.get("/settings/ai")
    assert first.status_code == 200
    assert first.json()["has_anthropic_key"] is False
    assert first.json()["ai_available"] is False

    updated = client.put(
        "/settings/ai",
        json={"provider": "claude", "anthropic_api_key": "sk-ant-abcd1234"},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["has_anthropic_key"] is True
    assert body["anthropic_key_preview"] == "••••1234"
    assert body["ai_available"] is True

    switched = client.put("/settings/ai", json={"provider": "openai"})
    assert switched.status_code == 200
    assert switched.json()["ai_available"] is False

    invalid = client.put("/settings/ai", json={"provider": "not-a-provider"})
    assert invalid.status_code == 422
