"""Add user profile fields (first/last name, avatar)."""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(120), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
