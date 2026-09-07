"""SQLAlchemy Post repository implementation."""
from __future__ import annotations
from typing import Optional
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

    def get_by_writer(self, writer_id: UUID, status: Optional[PostStatus] = None) -> list[Post]:
        query = self._session.query(Post).filter(Post.writer_id == writer_id)
        if status:
            query = query.filter(Post.status == status)
        return query.order_by(desc(Post.created_at)).all()

    def get_published_for_feed(self, writer_ids: list[UUID], limit: int = 20, cursor: Optional[str] = None) -> list[Post]:
        query = (
            self._session.query(Post)
            .filter(Post.writer_id.in_(writer_ids))
            .filter(Post.status == PostStatus.PUBLISHED)
            .order_by(desc(Post.published_at))
        )
        if cursor:
            try:
                cursor_dt = datetime.fromisoformat(cursor)
                query = query.filter(Post.published_at < cursor_dt)
            except ValueError:
                pass
        return query.limit(limit + 1).all()  # +1 to check if more exist

    def get_scheduled_for_publishing(self) -> list[Post]:
        from datetime import datetime
        now = datetime.utcnow()
        return (
            self._session.query(Post)
            .filter(Post.status == PostStatus.SCHEDULED)
            .filter(Post.scheduled_for <= now)
            .all()
        )