"""add stable numeric public patient identifiers

Revision ID: 20260818_0004
Revises: 20260818_0003
"""

from alembic import op
import sqlalchemy as sa


revision = "20260818_0004"
down_revision = "20260818_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column("public_patient_id", sa.Integer(), nullable=True),
    )
    # Existing rows receive deterministic, unique values. New rows are
    # allocated by the application and protected by the unique index below.
    op.execute(
        """
        WITH numbered AS (
            SELECT id, (1000000 + ROW_NUMBER() OVER (ORDER BY id))::integer AS public_id
            FROM patients
        )
        UPDATE patients AS p
        SET public_patient_id = numbered.public_id
        FROM numbered
        WHERE p.id = numbered.id
        """
    )
    op.alter_column("patients", "public_patient_id", nullable=False)
    op.create_index(
        "ix_patients_public_patient_id",
        "patients",
        ["public_patient_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_patients_public_patient_id", table_name="patients")
    op.drop_column("patients", "public_patient_id")
