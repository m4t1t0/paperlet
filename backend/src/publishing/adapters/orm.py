"""Publishing SQLAlchemy models."""
from __future__ import annotations
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, Table, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from backend.src.publishing.domain.model import Post, PostStatus
from backend.src.shared.database import mapper_registry, metadata


posts_table = Table(
    "posts",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid4),
    Column("writer_id", PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True),
    Column("title", String(500), nullable=False),
    Column("preview_content", Text, nullable=False),
    Column("subscriber_content", Text, nullable=False),
    Column("status", String(20), nullable=False, default=PostStatus.DRAFT.value, index=True),
    Column("scheduled_for", DateTime, nullable=True, index=True),
    Column("published_at", DateTime, nullable=True),
    Column("created_at", DateTime, default=datetime.utcnow, nullable=False),
    Column("updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False),
    Index("ix_posts_writer_status", "writer_id", "status"),
    Index("ix_posts_published_at", "published_at"),
)


def start_mappers() -> None:
    """Start SQLAlchemy mappers."""
    from sqlalchemy.orm import class_mapper
    
    # Check if already mapped
    try:
        class_mapper(Post)
        return  # Already mapped
    except Exception:
        pass  # Not mapped yet
    
    mapper_registry.map_imperatively(Post, posts_table)


def create_tables(engine) -> None:
    """Create all tables."""
    metadata.create_all(engine)


def drop_tables(engine) -> None:
    """Drop all tables."""
    metadata.drop_all(engine)