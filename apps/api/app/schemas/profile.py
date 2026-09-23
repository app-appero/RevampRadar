from datetime import datetime

from pydantic import BaseModel, Field


class ProfileLink(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    url: str = Field(min_length=1, max_length=2048)


class SenderProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    intro: str = Field(min_length=1, max_length=2000)
    website_url: str = Field(min_length=1, max_length=2048)
    freelancer_links: list[ProfileLink] = Field(default_factory=list)
    social_links: list[ProfileLink] = Field(default_factory=list)


class SenderProfileResponse(SenderProfileUpdate):
    updated_at: datetime


class EmailTemplatesUpdate(BaseModel):
    refactor_body: str | None = Field(default=None, max_length=8000)
    greenfield_body: str | None = Field(default=None, max_length=8000)


class EmailTemplatesResponse(BaseModel):
    refactor_body: str | None
    greenfield_body: str | None
    refactor_default: str
    greenfield_default: str
    refactor_tokens: list[str]
    greenfield_tokens: list[str]
    updated_at: datetime


class AiCredentialsUpdate(BaseModel):
    provider: str | None = Field(default=None, max_length=16)
    anthropic_api_key: str | None = Field(default=None, max_length=500)
    openai_api_key: str | None = Field(default=None, max_length=500)


class AiCredentialsResponse(BaseModel):
    provider: str
    anthropic_api_key: str | None
    openai_api_key: str | None
    ai_available: bool
    updated_at: datetime
