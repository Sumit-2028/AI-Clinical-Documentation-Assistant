"""backend foundation

Revision ID: 20260817_0001
Revises:
Create Date: 2026-08-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260817_0001"
down_revision = None
branch_labels = None
depends_on = None


uuid_type = postgresql.UUID(as_uuid=True)
jsonb_type = postgresql.JSONB(astext_type=sa.Text())


def uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        uuid_type,
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    ]


def add_column_if_missing(table_name: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    existing_columns = {
        existing_column["name"]
        for existing_column in inspector.get_columns(table_name)
    }

    if column.name not in existing_columns:
        op.add_column(table_name, column)


def ensure_users_timestamps() -> None:
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table("users"):
        return

    add_column_if_missing(
        "users",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    add_column_if_missing(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        uuid_pk(),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.String(length=50),
            nullable=False,
            server_default="physician",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        *timestamps(),
        if_not_exists=True,
    )
    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        unique=True,
        if_not_exists=True,
    )
    ensure_users_timestamps()

    op.create_table(
        "patients",
        uuid_pk(),
        sa.Column("external_patient_ref", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        *timestamps(),
    )
    op.create_index(
        "ix_patients_external_patient_ref",
        "patients",
        ["external_patient_ref"],
        unique=True,
    )

    op.create_table(
        "encounters",
        uuid_pk(),
        sa.Column(
            "patient_id",
            uuid_type,
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("encounter_type", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="active",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_encounters_patient_id", "encounters", ["patient_id"])

    op.create_table(
        "documents",
        uuid_pk(),
        sa.Column(
            "patient_id",
            uuid_type,
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "encounter_id",
            uuid_type,
            sa.ForeignKey("encounters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("input_modality", sa.String(length=50), nullable=False),
        sa.Column("source_language", sa.String(length=20), nullable=True),
        sa.Column("storage_uri", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="received",
        ),
        *timestamps(),
    )
    op.create_index("ix_documents_patient_id", "documents", ["patient_id"])
    op.create_index("ix_documents_encounter_id", "documents", ["encounter_id"])

    op.create_table(
        "processing_jobs",
        uuid_pk(),
        sa.Column(
            "document_id",
            uuid_type,
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("step", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        *timestamps(),
    )
    op.create_index(
        "ix_processing_jobs_document_id",
        "processing_jobs",
        ["document_id"],
    )

    op.create_table(
        "extraction_results",
        uuid_pk(),
        sa.Column(
            "document_id",
            uuid_type,
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "field_payload",
            jsonb_type,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "requires_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        *timestamps(),
    )
    op.create_index(
        "ix_extraction_results_document_id",
        "extraction_results",
        ["document_id"],
    )

    op.create_table(
        "clinical_events",
        uuid_pk(),
        sa.Column(
            "patient_id",
            uuid_type,
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "encounter_id",
            uuid_type,
            sa.ForeignKey("encounters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_document_id",
            uuid_type,
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "event_payload",
            jsonb_type,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "validation_status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_clinical_events_patient_id", "clinical_events", ["patient_id"])
    op.create_index(
        "ix_clinical_events_encounter_id",
        "clinical_events",
        ["encounter_id"],
    )
    op.create_index(
        "ix_clinical_events_source_document_id",
        "clinical_events",
        ["source_document_id"],
    )

    op.create_table(
        "patient_memory",
        uuid_pk(),
        sa.Column(
            "patient_id",
            uuid_type,
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "encounter_id",
            uuid_type,
            sa.ForeignKey("encounters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "clinical_event_id",
            uuid_type,
            sa.ForeignKey("clinical_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("concept_thread_id", uuid_type, nullable=True),
        sa.Column(
            "memory_payload",
            jsonb_type,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "trust_tier",
            sa.String(length=20),
            nullable=False,
            server_default="3",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_patient_memory_patient_id", "patient_memory", ["patient_id"])
    op.create_index("ix_patient_memory_encounter_id", "patient_memory", ["encounter_id"])
    op.create_index(
        "ix_patient_memory_clinical_event_id",
        "patient_memory",
        ["clinical_event_id"],
    )
    op.create_index(
        "ix_patient_memory_concept_thread_id",
        "patient_memory",
        ["concept_thread_id"],
    )

    op.create_table(
        "conflicts",
        uuid_pk(),
        sa.Column(
            "patient_id",
            uuid_type,
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="unresolved",
        ),
        sa.Column("risk_level", sa.String(length=50), nullable=True),
        sa.Column(
            "conflict_payload",
            jsonb_type,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_conflicts_patient_id", "conflicts", ["patient_id"])

    op.create_table(
        "generated_documents",
        uuid_pk(),
        sa.Column(
            "patient_id",
            uuid_type,
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "encounter_id",
            uuid_type,
            sa.ForeignKey("encounters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "content",
            jsonb_type,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
    )
    op.create_index(
        "ix_generated_documents_patient_id",
        "generated_documents",
        ["patient_id"],
    )
    op.create_index(
        "ix_generated_documents_encounter_id",
        "generated_documents",
        ["encounter_id"],
    )

    op.create_table(
        "audit_logs",
        uuid_pk(),
        sa.Column(
            "actor_user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=True),
        sa.Column("entity_id", uuid_type, nullable=True),
        sa.Column(
            "metadata",
            jsonb_type,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_generated_documents_encounter_id", table_name="generated_documents")
    op.drop_index("ix_generated_documents_patient_id", table_name="generated_documents")
    op.drop_table("generated_documents")

    op.drop_index("ix_conflicts_patient_id", table_name="conflicts")
    op.drop_table("conflicts")

    op.drop_index("ix_patient_memory_concept_thread_id", table_name="patient_memory")
    op.drop_index("ix_patient_memory_clinical_event_id", table_name="patient_memory")
    op.drop_index("ix_patient_memory_encounter_id", table_name="patient_memory")
    op.drop_index("ix_patient_memory_patient_id", table_name="patient_memory")
    op.drop_table("patient_memory")

    op.drop_index("ix_clinical_events_source_document_id", table_name="clinical_events")
    op.drop_index("ix_clinical_events_encounter_id", table_name="clinical_events")
    op.drop_index("ix_clinical_events_patient_id", table_name="clinical_events")
    op.drop_table("clinical_events")

    op.drop_index("ix_extraction_results_document_id", table_name="extraction_results")
    op.drop_table("extraction_results")

    op.drop_index("ix_processing_jobs_document_id", table_name="processing_jobs")
    op.drop_table("processing_jobs")

    op.drop_index("ix_documents_encounter_id", table_name="documents")
    op.drop_index("ix_documents_patient_id", table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_encounters_patient_id", table_name="encounters")
    op.drop_table("encounters")

    op.drop_index("ix_patients_external_patient_ref", table_name="patients")
    op.drop_table("patients")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
