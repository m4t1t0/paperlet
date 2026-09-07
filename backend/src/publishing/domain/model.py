"""Publishing domain model."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import reconstructor

from backend.src.shared.domain.events import AggregateRoot, DomainEvent


class PostStatus(str, Enum):
    """Post status."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    CANCELLED = "cancelled"


class PostPublished(DomainEvent):
    """Event emitted when a post is published."""
    post_id: UUID
    writer_id: UUID
    published_at: datetime


class PostScheduled(DomainEvent):
    """Event emitted when a post is scheduled."""
    post_id: UUID
    writer_id: UUID
    scheduled_for: datetime


class PostCancelled(DomainEvent):
    """Event emitted when a scheduled post is cancelled."""
    post_id: UUID
    writer_id: UUID


@dataclass
class Post(AggregateRoot):
    """Post aggregate - newsletter with preview and subscriber content."""
    id: UUID = field(default_factory=uuid4)
    writer_id: UUID = field(default_factory=uuid4)
    title: str = ""
    preview_content: str = ""
    subscriber_content: str = ""
    status: PostStatus = PostStatus.DRAFT
    scheduled_for: Optional[datetime] = None
    published_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    _events: list = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        super().__init__()

    @reconstructor
    def _init_on_load(self) -> None:
        """Initialize _events when loaded from database."""
        super().__init__()

    @classmethod
    def create_draft(
        cls,
        writer_id: UUID,
        title: str,
        preview_content: str,
        subscriber_content: str,
    ) -> Post:
        """Create a new draft post."""
        post = cls(
            writer_id=writer_id,
            title=title.strip(),
            preview_content=preview_content,
            subscriber_content=subscriber_content,
            status=PostStatus.DRAFT,
        )
        return post

    @classmethod
    def create_scheduled(
        cls,
        writer_id: UUID,
        title: str,
        preview_content: str,
        subscriber_content: str,
        scheduled_for: datetime,
    ) -> Post:
        """Create a new scheduled post."""
        if scheduled_for <= datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")

        post = cls(
            writer_id=writer_id,
            title=title.strip(),
            preview_content=preview_content,
            subscriber_content=subscriber_content,
            status=PostStatus.SCHEDULED,
            scheduled_for=scheduled_for,
        )
        post.add_event(PostScheduled(
            aggregate_id=post.id,
            aggregate_type="Post",
            post_id=post.id,
            writer_id=writer_id,
            scheduled_for=scheduled_for,
        ))
        return post

    def publish(self) -> None:
        """Publish the post immediately."""
        if self.status == PostStatus.PUBLISHED:
            raise ValueError("Post already published")

        if self.status == PostStatus.CANCELLED:
            raise ValueError("Cannot publish cancelled post")

        self.status = PostStatus.PUBLISHED
        self.published_at = datetime.utcnow()
        self.updated_at = self.published_at

        self.add_event(PostPublished(
            aggregate_id=self.id,
            aggregate_type="Post",
            post_id=self.id,
            writer_id=self.writer_id,
            published_at=self.published_at,
        ))

    def schedule(self, scheduled_for: datetime) -> None:
        """Schedule the post for future publication."""
        if self.status == PostStatus.PUBLISHED:
            raise ValueError("Cannot schedule already published post")

        if scheduled_for <= datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")

        self.status = PostStatus.SCHEDULED
        self.scheduled_for = scheduled_for
        self.updated_at = datetime.utcnow()

        self.add_event(PostScheduled(
            aggregate_id=self.id,
            aggregate_type="Post",
            post_id=self.id,
            writer_id=self.writer_id,
            scheduled_for=scheduled_for,
        ))

    def cancel(self) -> None:
        """Cancel a scheduled post."""
        if self.status not in (PostStatus.DRAFT, PostStatus.SCHEDULED):
            raise ValueError("Can only cancel draft or scheduled posts")

        self.status = PostStatus.CANCELLED
        self.updated_at = datetime.utcnow()

        self.add_event(PostCancelled(
            aggregate_id=self.id,
            aggregate_type="Post",
            post_id=self.id,
            writer_id=self.writer_id,
        ))

    def update_content(
        self,
        title: Optional[str] = None,
        preview_content: Optional[str] = None,
        subscriber_content: Optional[str] = None,
    ) -> None:
        """Update post content (only for draft/scheduled)."""
        if self.status == PostStatus.PUBLISHED:
            raise ValueError("Cannot update published post")

        if self.status == PostStatus.CANCELLED:
            raise ValueError("Cannot update cancelled post")

        if title is not None:
            self.title = title.strip()
        if preview_content is not None:
            self.preview_content = preview_content
        if subscriber_content is not None:
            self.subscriber_content = subscriber_content
        self.updated_at = datetime.utcnow()

    def get_content_for_reader(self, has_allocation: bool, reader_id: UUID | None = None) -> dict:
        """Get post content based on reader's allocation status."""
        # Handle both enum and string status (from DB)
        status_value = self.status.value if hasattr(self.status, 'value') else self.status
        # Writers can see their own subscriber content
        is_writer = reader_id is not None and reader_id == self.writer_id
        content = {
            "id": str(self.id),
            "writer_id": str(self.writer_id),
            "title": self.title,
            "preview_content": self.preview_content,
            "status": status_value,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "created_at": self.created_at.isoformat(),
        }
        if has_allocation or is_writer:
            content["subscriber_content"] = self.subscriber_content
            content["has_full_access"] = True
        else:
            content["subscriber_content"] = None
            content["has_full_access"] = False
        return content

    def is_scheduled_for_publishing(self) -> bool:
        """Check if post is scheduled and ready to publish."""
        return (
            self.status == PostStatus.SCHEDULED
            and self.scheduled_for is not None
            and self.scheduled_for <= datetime.utcnow()
        )