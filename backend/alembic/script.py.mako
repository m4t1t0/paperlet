"""Migration script template."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = None
depends_on = None


def upgrade() -> None:
    ${upgrade_ops if upgrade_ops else "pass"}


def downgrade() -> None:
    ${downgrade_ops if downgrade_ops else "pass"}