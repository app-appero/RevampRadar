from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.provider import get_ai_provider
from app.config import Settings
from app.models.entities import AiCredentials

_PROVIDERS = ("claude", "openai")


def get_or_create_ai_credentials(session: Session) -> AiCredentials:
    row = session.query(AiCredentials).order_by(AiCredentials.created_at.asc()).first()
    if row is not None:
        return row
    row = AiCredentials(provider="claude", anthropic_api_key=None, openai_api_key=None)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_ai_credentials(
    session: Session,
    *,
    provider: str | None,
    anthropic_api_key: str | None,
    openai_api_key: str | None,
) -> AiCredentials:
    row = get_or_create_ai_credentials(session)
    if provider is not None:
        value = provider.strip().lower()
        if value not in _PROVIDERS:
            raise ValueError(f"Provider non valido: {provider}")
        row.provider = value
    if anthropic_api_key is not None:
        row.anthropic_api_key = anthropic_api_key.strip() or None
    if openai_api_key is not None:
        row.openai_api_key = openai_api_key.strip() or None
    session.commit()
    session.refresh(row)
    return row


def effective_settings(session: Session, base: Settings) -> Settings:
    """Chiavi/provider salvati in Impostazioni hanno la precedenza su quelli in .env."""
    creds = get_or_create_ai_credentials(session)
    overrides: dict[str, str] = {"ai_provider": creds.provider}
    if creds.anthropic_api_key:
        overrides["anthropic_api_key"] = creds.anthropic_api_key
    if creds.openai_api_key:
        overrides["openai_api_key"] = creds.openai_api_key
    return base.model_copy(update=overrides)


def is_ai_available(session: Session, base: Settings) -> bool:
    return get_ai_provider(effective_settings(session, base)) is not None
