"""Publishing commands."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from backend.src.shared.service_layer.messagebus import Command


@dataclass(frozen=True)
class CreatePostCommand(Command):
    """Command to create a draft post."""
    writer_id: UUID
    title: str
    preview_content: str
    subscriber_content: str


@dataclass(frozen=True)
class CreateScheduledPostCommand(Command):
    """Command to create a scheduled post."""
    writer_id: UUID
    title: str
    preview_content: str
    subscriber_content: str
    scheduled_for: datetime


@dataclass(frozen=True)
class PublishPostCommand(Command):
    """Command to publish a post."""
    writer_id: UUID
    post_id: UUID


@dataclass(frozen=True)
class SchedulePostCommand(Command):
    """Command to schedule a draft post."""
    writer_id: UUID
    post_id: UUID
    scheduled_for: datetime


@dataclass(frozen=True)
class CancelPostCommand(Command):
    """Command to cancel a scheduled post."""
    writer_id: UUID
    post_id: UUID


@dataclass(frozen=True)
class UpdatePostCommand(Command):
    """Command to update post content."""
    writer_id: UUID
    post_id: UUID
    title: Optional[str] = None
    preview_content: Optional[str] = None
    subscriber_content: Optional[str] = None


@dataclass(frozen=True)
class GetPostCommand(Command):
    """Command to get a post."""
    post_id: UUID
    reader_id: Optional[UUID] = None


@dataclass(frozen=True)
class GetWriterPostsCommand(Command):
    """Command to get writer's posts."""
    writer_id: UUID
    status: Optional[str] = None


@dataclass(frozen=True)
class GetFeedCommand(Command):
    """Command to get reader's feed."""
    reader_id: UUID
    limit: int = 20
    cursor: Optional[str] = None