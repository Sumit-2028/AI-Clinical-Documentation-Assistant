from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PatientCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=2, max_length=255)


class PatientAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physician_id: UUID


class PatientResponse(BaseModel):
    patient_id: str
    display_name: str | None = None
    user_id: str | None = None


class PatientAssignmentResponse(BaseModel):
    patient_id: str
    physician_id: str
    status: str
