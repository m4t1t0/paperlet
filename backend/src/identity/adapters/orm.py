"""Identity SQLAlchemy models."""

from __future__ import annotations
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, Table, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from backend.src.identity.domain.model import User, Session
from backend.src.shared.database import metadata


users_table = Table(
    "users",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    Column("email", String(255), unique=True, nullable=False, index=True),
    Column("password_hash", Text, nullable=False),
    Column("created_at", DateTime, default=datetime.utcnow, nullable=False),
    Column(
        "updated_at",
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    ),
    Column("is_active", Boolean, default=True, nullable=False),
    Column("roles", Text, default="[]", nullable=False),  # JSON array of role strings
)

sessions_table = Table(
    "sessions",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    Column("user_id", PG_UUID(as_uuid=True), nullable=False, index=True),
    Column("refresh_token_hash", Text, nullable=False),
    Column("expires_at", DateTime, nullable=False),
    Column("revoked_at", DateTime, nullable=True),
    Column("user_agent", Text, nullable=True),
    Column("ip", String(45), nullable=True),
    Column("created_at", DateTime, default=datetime.utcnow, nullable=False),
)


def start_mappers() -> None:
    """Start SQLAlchemy mappers."""
    from backend.src.shared.database import mapper_registry
    from sqlalchemy.orm import class_mapper

    # Check if already mapped
    try:
        class_mapper(User)
        return  # Already mapped
    except Exception:
        pass  # Not mapped yet

    mapper_registry.map_imperatively(
        User,
        users_table,
        properties={
            "_roles_json": users_table.c.roles,
        },
    )
    mapper_registry.map_imperatively(Session, sessions_table)


def create_tables(engine) -> None:
    """Create all tables."""
    metadata.create_all(engine)


def drop_tables(engine) -> None:
    """Drop all tables."""
    metadata.drop_all(engine)
