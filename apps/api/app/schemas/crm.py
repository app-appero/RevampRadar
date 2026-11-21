from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

CRM_STATUSES = (
    "discovered",
    "analyzed",
    "qualified",
    "shortlisted",
    "to_contact",
    "contacted",
    "replied",
    "meeting",
    "proposal",
    "won",
    "lost",
    "uncontactable",
    "not_now",
)

ACTIVITY_TYPES = ("note", "status_change", "call", "email", "meeting", "other")

# Canale con cui proporsi all'azienda (campo esplicito, prima solo tag tipo canale-ig-proposto).
PROPOSED_CHANNELS = ("email", "instagram", "facebook", "whatsapp", "phone", "visit", "other")
CHANNEL_ALIASES = {
    "ig": "instagram", "insta": "instagram", "mail": "email", "e-mail": "email", "fb": "facebook",
    "wa": "whatsapp", "telefono": "phone", "tel": "phone", "visita": "visit", "di persona": "visit", "altro": "other",
}
OBSERVED_ISSUE_MAX = 1000


def normalize_channel(value: str | None) -> str | None:
    """None/vuoto → None; alias (ig, mail, telefono…) → valore canonico; ValueError se sconosciuto."""
    text = " ".join((value or "").strip().lower().split())
    if not text:
        return None
    text = CHANNEL_ALIASES.get(text, text)
    if text not in PROPOSED_CHANNELS:
        raise ValueError(f"Canale proposto non valido: {value}. Ammessi: {', '.join(PROPOSED_CHANNELS)}.")
    return text

SCHEDULED_ACTIVITY_TYPES = ("call", "email", "meeting", "other")


class TagResponse(BaseModel):
    id: UUID
    name: str


class NoteResponse(BaseModel):
    id: UUID
    body: str
    created_at: datetime


class ActivityResponse(BaseModel):
    id: UUID
    type: str
    note: str | None
    occurred_at: datetime | None
    occurred_on: date | None = None
    due_at: datetime | None
    completed_at: datetime | None
    channel: str | None = None
    sender: str | None = None
    recipient: str | None = None
    batch_id: str | None = None
    external_ref: str | None = None
    created_at: datetime


class AgendaItemResponse(BaseModel):
    id: UUID
    opportunity_id: UUID
    company_id: UUID
    company_name: str
    type: str
    note: str | None
    due_at: datetime
    created_at: datetime
    is_overdue: bool


class AgendaHistoryItemResponse(BaseModel):
    id: UUID
    opportunity_id: UUID
    company_id: UUID
    company_name: str
    type: str
    note: str | None
    due_at: datetime
    completed_at: datetime
    created_at: datetime


class OpportunitySummary(BaseModel):
    id: UUID
    company_id: UUID
    company_name: str
    category: str | None
    city: str | None
    region: str | None
    website_url: str | None
    domain: str | None
    places_checked_at: datetime | None = None
    has_email: bool = False
    has_phone: bool = False
    status: str
    is_favorite: bool
    tags: list[TagResponse]
    website_score: int | None = None
    opportunity_score: int | None = None
    priority: str | None = None
    latest_audit_id: UUID | None = None
    has_website: bool = True
    growth_score: int | None = None
    growth_priority: str | None = None
    segment: str = "refactor"
    proposed_channel: str | None = Field(
        default=None, description="Canale con cui proporsi: " + ", ".join(PROPOSED_CHANNELS)
    )
    observed_issue: str | None = Field(default=None, description="Difetto visto sul sito o sul profilo.")
    instagram_handle: str | None = None
    instagram_last_post_at: date | None = None
    updated_at: datetime


class OpportunityDetail(OpportunitySummary):
    notes: list[NoteResponse]
    activities: list[ActivityResponse]


class DashboardCounts(BaseModel):
    discovered: int = 0
    analyzed: int = 0
    qualified: int = 0
    shortlisted: int = 0
    to_contact: int = 0
    contacted: int = 0
    replied: int = 0
    meeting: int = 0
    proposal: int = 0
    won: int = 0
    lost: int = 0
    uncontactable: int = 0


class DashboardResponse(BaseModel):
    total: int
    favorites: int
    shortlisted: int
    high_priority: int
    to_contact: int
    counts: DashboardCounts


class UpdateOpportunityRequest(BaseModel):
    status: str | None = None
    is_favorite: bool | None = None
    proposed_channel: str | None = Field(
        default=None,
        description=f"{', '.join(PROPOSED_CHANNELS)} (anche ig, mail, telefono). Assente = invariato, null = cancella.",
    )
    observed_issue: str | None = Field(
        default=None, max_length=OBSERVED_ISSUE_MAX, description="Difetto visto. Assente = invariato, null = cancella."
    )


_NOTE_FIELD_ALIASES = ("content", "text", "note")


class CreateNoteRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"body": "Richiamare lunedì dopo le 10."}]})

    body: str = Field(
        min_length=1,
        max_length=4000,
        description="Testo della nota (obbligatorio, 1-4000 caratteri). Unico nome di campo accettato.",
    )

    @model_validator(mode="before")
    @classmethod
    def explain_wrong_field(cls, data):
        # Errore frequente dei client: {"content": ...}. Il 422 generico ("body: Field required")
        # non diceva quale campo usare.
        if isinstance(data, dict) and "body" not in data:
            wrong = next((name for name in _NOTE_FIELD_ALIASES if name in data), None)
            if wrong is not None:
                raise ValueError(
                    f"Campo «{wrong}» non valido: il testo della nota va inviato nel campo «body», "
                    'es. {"body": "Richiamare lunedì"}.'
                )
        return data


class CreateTagRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class CreateActivityRequest(BaseModel):
    type: str
    note: str | None = Field(default=None, max_length=2000)
    occurred_at: datetime | None = None
    due_at: datetime | None = None

    @model_validator(mode="after")
    def validate_timing(self):
        if self.due_at is not None and self.occurred_at is not None:
            raise ValueError("Specificare solo occurred_at o due_at, non entrambi.")
        return self


class ContactStatusRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "emails": ["info@esempio.it", "Ottica <ottica@esempio.it>"],
                    "contacted_tags": ["lotto2-20261116-inviato"],
                }
            ]
        }
    )

    emails: list[str] = Field(
        min_length=1,
        max_length=500,
        description="Indirizzi da controllare (accetta anche «Nome <email>» e «mailto:»).",
    )
    contacted_tags: list[str] = Field(
        default_factory=list,
        max_length=50,
        description=(
            "Tag aggiuntivi che indicano un invio già fatto. I tag con il segmento "
            "«inviato/inviata» (es. lotto2-20261116-inviato) sono già riconosciuti."
        ),
    )


class ContactStatusMatch(BaseModel):
    opportunity_id: UUID
    company_id: UUID
    company_name: str
    status: str
    already_contacted: bool
    contacted_on: date | None = Field(default=None, description="Data dell'ultimo contatto registrato.")
    contacted_at: datetime | None = Field(default=None, description="Orario, se registrato.")
    date_source: str | None = None
    evidence: list[str] = Field(default_factory=list, description="Es. status:contacted, tag:…, activity:email_sent.")
    matched_on: list[str] = Field(
        default_factory=list,
        description="Dove compare l'email: company_email, activity_recipient, activity_note, note.",
    )


class ContactStatusItem(BaseModel):
    email: str
    normalized_email: str | None
    valid: bool
    already_contacted: bool
    status: str | None = None
    contacted_on: date | None = None
    contacted_at: datetime | None = None
    matches: list[ContactStatusMatch] = Field(default_factory=list)


class ContactStatusResponse(BaseModel):
    checked: int
    already_contacted: int
    results: list[ContactStatusItem]
