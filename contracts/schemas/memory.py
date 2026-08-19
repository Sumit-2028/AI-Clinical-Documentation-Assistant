from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .clinical_event import ClinicalEvent, SourceTextSpan
from .enums import (
    MemorySource,
    ReviewedStatus,
    ThreadMatchConfidence,
    ThreadMatchMethod,
    TrustTier,
)
from .provenance import ProvenanceRecord


class MemoryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    patient_id: UUID
    encounter_id: UUID
    source: MemorySource
    source_event_id: UUID
    concept_thread_id: UUID
    normalized_concept: str = Field(min_length=1)
    snomed_ct_id: str | None = None
    entity_type: str = Field(min_length=1)
    clinical_domain: str = Field(min_length=1)
    original_text: str = Field(min_length=1)
    processed_text: str = Field(min_length=1)
    assertion: str = Field(min_length=1)
    clinical_status: str = Field(min_length=1)
    temporal_context: str = Field(min_length=1)
    temporal_date: date | None = None
    trust_tier: TrustTier
    current_trust_tier: TrustTier
    reviewed_status: ReviewedStatus = ReviewedStatus.UNREVIEWED
    provenance: ProvenanceRecord
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class MemoryWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: UUID | str
    encounter_id: UUID
    source: MemorySource
    clinical_events: list[ClinicalEvent] = Field(min_length=1)
    actor_id: str | None = Field(default=None, min_length=1, max_length=255)


class WrittenMemoryEvent(BaseModel):
    event_id: UUID
    concept_thread_id: UUID
    trust_tier: TrustTier
    thread_match_confidence: ThreadMatchConfidence
    thread_match_method: ThreadMatchMethod
    is_new_thread: bool


class RejectedMemoryEvent(BaseModel):
    event_id: UUID
    reason: str = Field(min_length=1)


class MemoryWriteResponse(BaseModel):
    written_events: list[WrittenMemoryEvent]
    conflicts_detected: list[UUID]
    rejected_events: list[RejectedMemoryEvent]


class MemoryEventHistory(BaseModel):
    patient_id: UUID
    events: list[MemoryEvent]


class ConceptThreadState(BaseModel):
    concept_thread_id: UUID
    patient_id: UUID
    normalized_concept: str
    snomed_ct_id: str | None = None
    clinical_domain: str
    current_status: str
    current_trust_tier: TrustTier
    latest_event_id: UUID
    event_count: int = Field(ge=1)
    updated_at: datetime


class CurrentPatientState(BaseModel):
    patient_id: UUID
    concept_threads: list[ConceptThreadState]


class TierReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physician_id: str = Field(min_length=1, max_length=255)


class TierReviewResponse(BaseModel):
    event_id: UUID
    new_trust_tier: TrustTier
    trust_tier_change_event_id: UUID
    reviewed_status: ReviewedStatus | None = None
