import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


def uuid_pk_column():
    return Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    id = uuid_pk_column()
    external_patient_ref = Column(String(255), unique=True, nullable=True)
    display_name = Column(String(255), nullable=True)


class Encounter(Base, TimestampMixin):
    __tablename__ = "encounters"

    id = uuid_pk_column()
    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    encounter_type = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default="active")
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)


class DocumentRecord(Base, TimestampMixin):
    __tablename__ = "documents"

    id = uuid_pk_column()
    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    encounter_id = Column(
        UUID(as_uuid=True),
        ForeignKey("encounters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    input_modality = Column(String(50), nullable=False)
    source_language = Column(String(20), nullable=True)
    storage_uri = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="received")


class ProcessingJob(Base, TimestampMixin):
    __tablename__ = "processing_jobs"

    id = uuid_pk_column()
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    step = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="queued")
    error_message = Column(Text, nullable=True)


class ExtractionResult(Base, TimestampMixin):
    __tablename__ = "extraction_results"

    id = uuid_pk_column()
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_payload = Column(JSONB, nullable=False, default=dict)
    confidence = Column(Float, nullable=True)
    requires_review = Column(Boolean, nullable=False, default=False)


class ClinicalEventRecord(Base):
    __tablename__ = "clinical_events"

    id = uuid_pk_column()
    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    encounter_id = Column(
        UUID(as_uuid=True),
        ForeignKey("encounters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_payload = Column(JSONB, nullable=False, default=dict)
    validation_status = Column(String(50), nullable=False, default="pending")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PatientMemoryRecord(Base):
    __tablename__ = "patient_memory"

    id = uuid_pk_column()
    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    encounter_id = Column(
        UUID(as_uuid=True),
        ForeignKey("encounters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    clinical_event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clinical_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    concept_thread_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    memory_payload = Column(JSONB, nullable=False, default=dict)
    trust_tier = Column(String(20), nullable=False, default="3")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ConflictRecord(Base, TimestampMixin):
    __tablename__ = "conflicts"

    id = uuid_pk_column()
    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(50), nullable=False, default="unresolved")
    risk_level = Column(String(50), nullable=True)
    conflict_payload = Column(JSONB, nullable=False, default=dict)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class GeneratedDocumentRecord(Base, TimestampMixin):
    __tablename__ = "generated_documents"

    id = uuid_pk_column()
    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    encounter_id = Column(
        UUID(as_uuid=True),
        ForeignKey("encounters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_type = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default="draft")
    content = Column(JSONB, nullable=False, default=dict)
    generated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finalized_at = Column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = uuid_pk_column()
    actor_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
