"""Publishing commands."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from backend.src.shared.domain.value_objects import PostId, ReaderId, WriterId
from backend.src.shared.service_layer.messagebus import Command


@dataclass(frozen=True)
class CreatePostCommand(Command):
    """Command to create a draft post."""

    writer_id: WriterId
    title: str
    preview_content: str
    subscriber_content: str


@dataclass(frozen=True)
class CreateScheduledPostCommand(Command):
    """Command to create a scheduled post."""

    writer_id: WriterId
    title: str
    preview_content: str
    subscriber_content: str
    scheduled_for: datetime


@dataclass(frozen=True)
class PublishPostCommand(Command):
    """Command to publish a post."""

    writer_id: WriterId
    post_id: PostId


@dataclass(frozen=True)
class SchedulePostCommand(Command):
    """Command to schedule a draft post."""

    writer_id: WriterId
    post_id: PostId
    scheduled_for: datetime


@dataclass(frozen=True)
class CancelPostCommand(Command):
    """Command to cancel a scheduled post."""

    writer_id: WriterId
    post_id: PostId


@dataclass(frozen=True)
class UpdatePostCommand(Command):
    """Command to update post content."""

    writer_id: WriterId
    post_id: PostId
    title: Optional[str] = None
    preview_content: Optional[str] = None
    subscriber_content: Optional[str] = None


@dataclass(frozen=True)
class GetPostCommand(Command):
    """Command to get a post."""

    post_id: PostId
    reader_id: Optional[ReaderId] = None


@dataclass(frozen=True)
class GetWriterPostsCommand(Command):
    """Command to get writer's posts."""

    writer_id: WriterId
    status: Optional[str] = None


@dataclass(frozen=True)
class GetFeedCommand(Command):
    """Command to get reader's feed."""

    reader_id: ReaderId
    limit: int = 20
    cursor: Optional[str] = None
