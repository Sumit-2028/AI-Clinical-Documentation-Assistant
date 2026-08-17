from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .conflict import ConflictRecord
from .enums import TrustTier
from .provenance import ProvenanceRecord


class MemoryContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    concept_thread_id: UUID
    normalized_concept: str
    clinical_status: str
    assertion: str
    temporal_context: str
    original_text: str
    trust_tier: TrustTier
    provenance: ProvenanceRecord


class VerifiedContext(BaseModel):
    conditions: list[MemoryContextItem] = Field(default_factory=list)
    medications: list[MemoryContextItem] = Field(default_factory=list)
    allergies: list[MemoryContextItem] = Field(default_factory=list)
    procedures: list[MemoryContextItem] = Field(default_factory=list)
    lab_trends: list[MemoryContextItem] = Field(default_factory=list)
    significant_events: list[MemoryContextItem] = Field(default_factory=list)


class RetrievedContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verified_context: VerifiedContext
    unverified_information: list[MemoryContextItem] = Field(default_factory=list)
    conflicts: list[ConflictRecord] = Field(default_factory=list)


class MemoryRetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: UUID
    encounter_id: UUID
    query_concepts: list[str] = Field(default_factory=list)
