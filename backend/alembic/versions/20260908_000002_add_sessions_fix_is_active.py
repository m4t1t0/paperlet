"""Add sessions table and fix is_active type."""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix is_active column type from String to Boolean
    op.alter_column(
        "users",
        "is_active",
        existing_type=sa.String(10),
        type_=sa.Boolean(),
        postgresql_using="is_active::boolean",
        nullable=False,
        server_default=sa.text("true"),
    )

    # Sessions table
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("refresh_token_hash", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("revoked_at", sa.DateTime, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sessions")
    op.alter_column(
        "users",
        "is_active",
        existing_type=sa.Boolean(),
        type_=sa.String(10),
        nullable=False,
        server_default="true",
    )
