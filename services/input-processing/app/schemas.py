from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from contracts.schemas import Step1Output


class MultilingualDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: UUID | str
    encounter_id: UUID
    text_input: str = Field(min_length=1)
    source_language: str = Field(min_length=2, max_length=20)


class HumanVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: UUID
    verified_text: str = Field(min_length=1)
    reviewer_id: str = Field(min_length=1, max_length=255)
    approved: bool


__all__ = [
    "HumanVerificationRequest",
    "MultilingualDocumentRequest",
    "Step1Output",
]
