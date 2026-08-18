"""add patient identity and physician assignments

Revision ID: 20260818_0002
Revises: 20260817_0001
Create Date: 2026-08-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260818_0002"
down_revision = "20260817_0001"
branch_labels = None
depends_on = None


uuid_type = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column(
            "user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_patients_user_id", "patients", ["user_id"], unique=True)

    op.create_table(
        "patient_assignments",
        sa.Column(
            "id",
            uuid_type,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "physician_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "patient_id",
            uuid_type,
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assigned_by_user_id",
            uuid_type,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="active",
        ),
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
        sa.UniqueConstraint(
            "physician_id",
            "patient_id",
            name="uq_patient_assignments_physician_patient",
        ),
    )
    op.create_index(
        "ix_patient_assignments_physician_id",
        "patient_assignments",
        ["physician_id"],
    )
    op.create_index(
        "ix_patient_assignments_patient_id",
        "patient_assignments",
        ["patient_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_patient_assignments_patient_id", table_name="patient_assignments")
    op.drop_index("ix_patient_assignments_physician_id", table_name="patient_assignments")
    op.drop_table("patient_assignments")
    op.drop_index("ix_patients_user_id", table_name="patients")
    op.drop_column("patients", "user_id")
