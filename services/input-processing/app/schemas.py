from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from contracts.schemas import Step1Output


class MultilingualDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: UUID
    encounter_id: UUID
    text_input: str = Field(min_length=1)
    source_language: str = Field(min_length=2, max_length=20)


class HumanVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: UUID
    verified_text: str = Field(min_length=1)
    reviewer_id: str = Field(min_length=1, max_length=255)
    approved: bool


class DocumentSourceResponse(BaseModel):
    """Short-lived link to a document's original uploaded bytes.

    Service-local on purpose.  The frozen Step 1 contract forbids extra fields,
    so storage location is exposed through this separate response rather than
    by widening Step1Output.
    """

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    download_url: str
    expires_at: datetime
    content_type: str
    size_bytes: int


__all__ = [
    "DocumentSourceResponse",
    "HumanVerificationRequest",
    "MultilingualDocumentRequest",
    "Step1Output",
]
