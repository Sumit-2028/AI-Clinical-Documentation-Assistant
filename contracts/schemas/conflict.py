from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .enums import ConflictResolutionAction, ConflictStatus


class ConflictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_id: UUID = Field(default_factory=uuid4)
    patient_id: UUID
    concept_thread_id: UUID
    event_a_id: UUID
    event_b_id: UUID
    conflict_type: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    status: ConflictStatus = ConflictStatus.UNRESOLVED
    resolution_action: ConflictResolutionAction | None = None
    physician_id: str | None = None
    resolved_event_id: UUID | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    resolved_at: datetime | None = None


class ResolveConflictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution_action: ConflictResolutionAction
    physician_id: str = Field(min_length=1, max_length=255)


class ResolveConflictResponse(BaseModel):
    conflict_id: UUID
    status: ConflictStatus
    new_event_id: UUID | None = None
