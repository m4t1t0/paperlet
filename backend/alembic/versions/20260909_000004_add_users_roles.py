"""Add users.roles JSON column, drop obsolete user_roles table."""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Roles are stored as JSON array on users (see identity/adapters/orm.py).
    # user_roles table from 0001 was never used by the code.
    op.add_column(
        "users",
        sa.Column("roles", sa.Text, nullable=False, server_default="[]"),
    )
    op.drop_table("user_roles")


def downgrade() -> None:
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(20), primary_key=True),
    )
    op.drop_column("users", "roles")
