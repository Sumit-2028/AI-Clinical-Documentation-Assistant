from datetime import date, datetime, timezone
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import ClinicalEventValidationStatus, InputModality


class SourceTextSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.end < self.start:
            raise ValueError("Text span end must not precede its start.")
        return self


class ClinicalEvent(BaseModel):
    """Exact Step 2 -> Step 3 event contract from the backend handoff."""

    model_config = ConfigDict(extra="forbid")

    event_local_id: UUID
    original_text: str = Field(min_length=1)
    processed_text: str = Field(min_length=1)
    normalized_concept: str = Field(min_length=1)
    snomed_ct_id: str | None = None
    entity_type: str = Field(min_length=1)
    clinical_domain: str = Field(min_length=1)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    assertion: str = Field(min_length=1)
    clinical_status: str = Field(min_length=1)
    temporal_context: str = Field(min_length=1)
    temporal_date: date | None = None
    bioclinicalbert_confidence: float = Field(ge=0.0, le=1.0)
    gemini_contextualization_confidence: float = Field(ge=0.0, le=1.0)
    source_document_id: UUID
    source_text_span: SourceTextSpan
    input_modality: InputModality
    source_language: str = Field(min_length=1, max_length=20)
    translation_confidence: float = Field(ge=0.0, le=1.0)
    validation_status: ClinicalEventValidationStatus


class ClinicalEventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clinical_events: list[ClinicalEvent]
    patient_id: UUID
    encounter_id: UUID
    source_document_id: UUID
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
