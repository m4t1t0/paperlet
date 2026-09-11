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
    Column("first_name", String(120), nullable=True),
    Column("last_name", String(120), nullable=True),
    Column("avatar_url", Text, nullable=True),
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
    from sqlalchemy import event as sa_event
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
            # Persisted JSON column; domain `roles` set is translated in repository.
            # `_roles_persisted` is intentionally not a domain field (pure domain).
            "_roles_persisted": users_table.c.roles,
        },
    )
    mapper_registry.map_imperatively(Session, sessions_table)

    def _sync_roles(mapper, connection, target) -> None:
        import json

        roles = target.__dict__.get("roles") or set()
        try:
            # Instrumented setattr (not __dict__) so flush picks up the change.
            target._roles_persisted = json.dumps([r.value for r in roles])
        except Exception:
            target._roles_persisted = "[]"

    def _sync_roles_on_flush(session, flush_context, instances) -> None:
        # `roles` is domain-only (unmapped set), so mutating it alone marks
        # nothing dirty. Sync mapped `_roles_persisted` on every flush so
        # add_role/remove_role persist without domain touching persistence.
        import json

        for obj in list(session.new) + list(session.dirty):
            if isinstance(obj, User):
                roles = obj.__dict__.get("roles") or set()
                try:
                    obj._roles_persisted = json.dumps([r.value for r in roles])  # type: ignore[attr-defined]
                except Exception:
                    obj._roles_persisted = "[]"  # type: ignore[attr-defined]

    try:
        sa_event.listen(User, "before_insert", _sync_roles)
        sa_event.listen(User, "before_update", _sync_roles)
        from sqlalchemy.orm import Session as _SASession

        sa_event.listen(_SASession, "before_flush", _sync_roles_on_flush)
    except Exception:
        pass  # Listeners already registered (session-scoped start_mappers)


def create_tables(engine) -> None:
    """Create all tables."""
    metadata.create_all(engine)


def drop_tables(engine) -> None:
    """Drop all tables."""
    metadata.drop_all(engine)
