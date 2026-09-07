"""Identity SQLAlchemy models."""
from __future__ import annotations
from datetime import datetime
import json
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from backend.src.identity.domain.model import User, UserRole
from backend.src.shared.database import metadata


users_table = Table(
    "users",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    Column("email", String(255), unique=True, nullable=False, index=True),
    Column("password_hash", Text, nullable=False),
    Column("created_at", DateTime, default=datetime.utcnow, nullable=False),
    Column("updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False),
    Column("is_active", String(10), default="true", nullable=False),
    Column("roles", Text, default="[]", nullable=False),  # JSON array of role strings
)


def _roles_to_json(roles: set[UserRole]) -> str:
    return json.dumps([r.value for r in roles])


def _json_to_roles(json_str: str) -> set[UserRole]:
    if not json_str:
        return {UserRole.READER}
    try:
        role_values = json.loads(json_str)
        return {UserRole(r) for r in role_values}
    except (json.JSONDecodeError, ValueError):
        return {UserRole.READER}


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


def create_tables(engine) -> None:
    """Create all tables."""
    metadata.create_all(engine)


def drop_tables(engine) -> None:
    """Drop all tables."""
    metadata.drop_all(engine)