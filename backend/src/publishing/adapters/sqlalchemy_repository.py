"""SQLAlchemy Post repository implementation."""

from __future__ import annotations
from datetime import datetime
from typing import Any, Optional, cast
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.src.publishing.adapters.repository import PostRepository
from backend.src.publishing.domain.model import Post, PostStatus


class SqlAlchemyPostRepository(PostRepository):
    """SQLAlchemy implementation of PostRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, post: Post) -> None:
        self._session.add(post)

    def get(self, post_id: UUID) -> Optional[Post]:
        return self._session.get(Post, post_id)

    def get_by_writer(
        self, writer_id: UUID, status: Optional[PostStatus] = None
    ) -> list[Post]:
        # NOTE: `cast(Any, ...)` unwraps SQLAlchemy-instrumented attributes,
        # which mypy (without the SQLAlchemy plugin) sees as plain values.
        query = self._session.query(Post).filter_by(writer_id=writer_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(desc(cast(Any, Post.created_at))).all()

    def get_published_for_feed(
        self, writer_ids: list[UUID], limit: int = 20, cursor: Optional[str] = None
    ) -> list[Post]:
        query = (
            self._session.query(Post)
            .filter(cast(Any, Post.writer_id).in_(writer_ids))
            .filter_by(status=PostStatus.PUBLISHED)
            .order_by(desc(cast(Any, Post.published_at)))
        )
        if cursor:
            try:
                cursor_dt = datetime.fromisoformat(cursor)
                query = query.filter(cast(Any, Post.published_at) < cursor_dt)
            except ValueError:
                pass
        return query.limit(limit + 1).all()  # +1 to check if more exist

    def get_scheduled_for_publishing(self) -> list[Post]:
        now = datetime.utcnow()
        return (
            self._session.query(Post)
            .filter_by(status=PostStatus.SCHEDULED)
            .filter(cast(Any, Post.scheduled_for) <= now)
            .all()
        )
