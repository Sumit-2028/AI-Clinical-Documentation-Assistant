"""enforce case-insensitive user email uniqueness

Revision ID: 20260818_0003
Revises: 20260818_0002
"""

from alembic import op
import sqlalchemy as sa


revision = "20260818_0003"
down_revision = "20260818_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_users_email_lower", table_name="users")
