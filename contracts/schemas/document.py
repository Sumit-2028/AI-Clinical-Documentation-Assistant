from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .clinical_event import ClinicalEvent
from .enums import DocumentStatus, DocumentType, ReviewAction, TrustTier
from .memory import MemoryWriteRequest
from .retrieval import RetrievedContext


class DocumentSections(BaseModel):
    """Shared section envelope for SOAP and discharge documents."""

    model_config = ConfigDict(extra="forbid")

    subjective: str | None = None
    objective: str | None = None
    assessment: str | None = None
    plan: str | None = None
    patient_identification: str | None = None
    reason_for_encounter: str | None = None
    medications: str | None = None
    allergies: str | None = None
    procedures: str | None = None
    relevant_history: str | None = None
    follow_up: str | None = None


class DocumentReviewFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    section: str | None = None
    source_event_ids: list[UUID] = Field(default_factory=list)


class DocumentProvenanceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: str = Field(min_length=1)
    generated_text: str = Field(min_length=1)
    source_event_ids: list[UUID] = Field(default_factory=list)
    source_document_ids: list[UUID] = Field(default_factory=list)
    source_kind: str = Field(min_length=1)
    trust_tier: TrustTier | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    is_inferred: bool = False


class ValidationFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    section: str | None = None
    source_event_ids: list[UUID] = Field(default_factory=list)


class DocumentValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    failures: list[ValidationFailure] = Field(default_factory=list)
    auto_regeneration_attempts: int = Field(default=0, ge=0)


class GeneratedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID = Field(default_factory=uuid4)
    patient_id: UUID
    encounter_id: UUID
    document_type: DocumentType
    status: DocumentStatus = DocumentStatus.DRAFT
    sections: DocumentSections
    flags_for_physician_review: list[DocumentReviewFlag] = Field(default_factory=list)
    provenance_map: list[DocumentProvenanceEntry] = Field(default_factory=list)
    validation_result: DocumentValidationResult
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    finalized_at: datetime | None = None
    generator: str = Field(default="deterministic_mock", min_length=1)


class GenerateDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: UUID
    encounter_id: UUID
    document_type: DocumentType
    current_consultation_events: list[ClinicalEvent] = Field(min_length=1)
    retrieved_context: RetrievedContext
    physician_instructions: str | None = None


class FinalizeDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ReviewAction
    physician_id: str = Field(min_length=1, max_length=255)
    edited_sections: DocumentSections | None = None
    regenerate_notes: str | None = None


class DocumentReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    status: DocumentStatus
    finalized_at: datetime | None = None
    memory_write_payload: MemoryWriteRequest | None = None
    document: GeneratedDocument | None = None


__all__ = [
    "DocumentProvenanceEntry",
    "DocumentReviewFlag",
    "DocumentReviewResponse",
    "DocumentSections",
    "DocumentValidationResult",
    "FinalizeDocumentRequest",
    "GeneratedDocument",
    "GenerateDocumentRequest",
    "ValidationFailure",
]
