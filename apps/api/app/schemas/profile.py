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
