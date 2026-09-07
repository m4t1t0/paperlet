"""Publishing repository interface."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from backend.src.publishing.domain.model import Post, PostStatus


class PostRepository(ABC):
    """Abstract repository for Post aggregate."""

    @abstractmethod
    def add(self, post: Post) -> None:
        """Add a post."""
        ...

    @abstractmethod
    def get(self, post_id: UUID) -> Optional[Post]:
        """Get post by ID."""
        ...

    @abstractmethod
    def get_by_writer(self, writer_id: UUID, status: Optional[PostStatus] = None) -> list[Post]:
        """Get posts by writer."""
        ...

    @abstractmethod
    def get_published_for_feed(self, writer_ids: list[UUID], limit: int = 20, cursor: Optional[str] = None) -> list[Post]:
        """Get published posts for reader feed."""
        ...

    @abstractmethod
    def get_scheduled_for_publishing(self) -> list[Post]:
        """Get posts scheduled for publishing now."""
        ...