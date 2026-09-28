from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PaletteColor(BaseModel):
    role: str = Field(min_length=1, max_length=32)
    hex: str = Field(min_length=1, max_length=16)


class DesignBriefUpdate(BaseModel):
    style: str | None = Field(default=None, max_length=64)
    palette: list[PaletteColor] | None = None
    typography: str | None = Field(default=None, max_length=255)
    tone_of_voice: str | None = Field(default=None, max_length=255)
    spacing: str | None = Field(default=None, max_length=32)
    border_radius: str | None = Field(default=None, max_length=32)
    image_treatment: str | None = Field(default=None, max_length=255)
    primary_cta: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=2000)


class DesignBriefResponse(BaseModel):
    style: str | None
    palette: list[PaletteColor] | None
    typography: str | None
    tone_of_voice: str | None
    spacing: str | None
    border_radius: str | None
    image_treatment: str | None
    primary_cta: str | None
    notes: str | None
    source: str
    updated_at: datetime


class ConceptSummary(BaseModel):
    id: UUID
    version: int
    status: str
    is_current: bool
    source: str
    generator_version: str
    sections: list[str] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    open_url: str
