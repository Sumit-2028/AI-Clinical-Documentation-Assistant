from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .clinical_event import SourceTextSpan
from .enums import InputModality


class PhysicianApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physician_id: str = Field(min_length=1)
    approved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    action: str = Field(min_length=1)


class ProvenanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_document_id: UUID
    source_event_id: UUID
    actor_id: str | None = Field(default=None, min_length=1, max_length=255)
    source_text_span: SourceTextSpan
    input_modality: InputModality
    source_language: str = Field(min_length=1, max_length=20)
    confidence: float = Field(ge=0.0, le=1.0)
    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    physician_approval: PhysicianApproval | None = None
