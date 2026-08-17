from datetime import datetime, timezone
from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import (
    ConfidenceTier,
    InputModality,
    ProcessingStatus,
    VerificationState,
)


class DualRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    triggered: bool
    second_pass_text: str | None = None
    agreement: bool | None = None


class ExtractedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: UUID = Field(default_factory=uuid4)
    raw_text: str = Field(min_length=1)
    standardized_text: str = Field(min_length=1)
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    is_high_risk_field: bool = False
    confidence_tier: ConfidenceTier
    dual_run_result: DualRunResult = Field(default_factory=lambda: DualRunResult(triggered=False))
    requires_doctor_review_before_memory_write: bool = False


class Step1Output(BaseModel):
    """Stable Step 1 -> Step 2 contract from the backend handoff README."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    patient_id: UUID
    encounter_id: UUID
    input_modality: InputModality
    source_language: str = Field(min_length=1, max_length=20)
    extracted_fields: list[ExtractedField] = Field(default_factory=list)
    translation_confidence: float = Field(ge=0.0, le=1.0)
    original_language_text: str | None = None
    ocr_engine_used: str | None = None
    vlm_model_used: str | None = None
    processing_status: ProcessingStatus
    audit_log_id: UUID
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    verification_state: VerificationState = VerificationState.NOT_REQUIRED

    @model_validator(mode="after")
    def validate_verification_gate(self) -> Self:
        has_unverified_review_fields = any(
            field.requires_doctor_review_before_memory_write
            for field in self.extracted_fields
        )

        if self.processing_status == ProcessingStatus.COMPLETE and has_unverified_review_fields:
            raise ValueError(
                "Complete Step1Output cannot contain unverified review fields."
            )

        if (
            self.processing_status == ProcessingStatus.PENDING_HUMAN_VERIFICATION
            and not has_unverified_review_fields
            and self.verification_state == VerificationState.PENDING
        ):
            raise ValueError(
                "Pending human verification requires at least one review field."
            )

        return self
