"""Publishing service layer."""
from __future__ import annotations
from typing import Optional
from uuid import UUID

from backend.src.publishing.adapters.repository import PostRepository
from backend.src.publishing.commands import (
    CancelPostCommand,
    CreatePostCommand,
    CreateScheduledPostCommand,
    GetFeedCommand,
    GetPostCommand,
    GetWriterPostsCommand,
    PublishPostCommand,
    SchedulePostCommand,
    UpdatePostCommand,
)
from backend.src.publishing.domain.model import Post, PostStatus
from backend.src.subscriptions.adapters.repository import SubscriptionRepository
from backend.src.shared.service_layer.messagebus import CommandHandler, MessageBus


class PublishingService:
    """Publishing service orchestrating post operations."""

    def __init__(
        self,
        post_repo: PostRepository,
        subscription_repo: SubscriptionRepository,
        message_bus: MessageBus,
    ) -> None:
        self._post_repo = post_repo
        self._subscription_repo = subscription_repo
        self._bus = message_bus

    def create_draft(self, command: CreatePostCommand) -> Post:
        """Create a draft post."""
        post = Post.create_draft(
            writer_id=command.writer_id,
            title=command.title,
            preview_content=command.preview_content,
            subscriber_content=command.subscriber_content,
        )
        self._post_repo.add(post)
        return post

    def create_scheduled(self, command: CreateScheduledPostCommand) -> Post:
        """Create a scheduled post."""
        post = Post.create_scheduled(
            writer_id=command.writer_id,
            title=command.title,
            preview_content=command.preview_content,
            subscriber_content=command.subscriber_content,
            scheduled_for=command.scheduled_for,
        )
        self._post_repo.add(post)
        return post

    def publish_post(self, command: PublishPostCommand) -> Post:
        """Publish a post immediately."""
        post = self._post_repo.get(command.post_id)
        if not post:
            raise ValueError("Post not found")
        if post.writer_id != command.writer_id:
            raise ValueError("Not authorized to publish this post")

        post.publish()
        # Publish domain events via message bus
        self._bus.publish_all(post.clear_events())
        return post

    def schedule_post(self, command: SchedulePostCommand) -> Post:
        """Schedule a draft post."""
        post = self._post_repo.get(command.post_id)
        if not post:
            raise ValueError("Post not found")
        if post.writer_id != command.writer_id:
            raise ValueError("Not authorized to schedule this post")

        post.schedule(command.scheduled_for)
        self._bus.publish_all(post.clear_events())
        return post

    def cancel_post(self, command: CancelPostCommand) -> Post:
        """Cancel a scheduled post."""
        post = self._post_repo.get(command.post_id)
        if not post:
            raise ValueError("Post not found")
        if post.writer_id != command.writer_id:
            raise ValueError("Not authorized to cancel this post")

        post.cancel()
        self._bus.publish_all(post.clear_events())
        return post

    def update_post(self, command: UpdatePostCommand) -> Post:
        """Update post content."""
        post = self._post_repo.get(command.post_id)
        if not post:
            raise ValueError("Post not found")
        if post.writer_id != command.writer_id:
            raise ValueError("Not authorized to update this post")

        post.update_content(
            title=command.title,
            preview_content=command.preview_content,
            subscriber_content=command.subscriber_content,
        )
        return post

    def get_post(self, command: GetPostCommand) -> dict:
        """Get post with paywall logic."""
        post = self._post_repo.get(command.post_id)
        if not post:
            raise ValueError("Post not found")

        # Check if reader has allocation to writer
        has_allocation = False
        if command.reader_id:
            subscription = self._subscription_repo.get_by_reader(command.reader_id)
            if subscription:
                sub_status = subscription.status.value if hasattr(subscription.status, 'value') else subscription.status
                if sub_status == "active":
                    has_allocation = subscription.is_writer_allocated(post.writer_id)

        return post.get_content_for_reader(has_allocation, command.reader_id)

    def get_writer_posts(self, command: GetWriterPostsCommand) -> list[Post]:
        """Get writer's posts."""
        status = PostStatus(command.status) if command.status else None
        return self._post_repo.get_by_writer(command.writer_id, status)

    def get_feed(self, command: GetFeedCommand) -> dict:
        """Get reader's feed of posts from allocated writers."""
        subscription = self._subscription_repo.get_by_reader(command.reader_id)
        if not subscription:
            return {"posts": [], "next_cursor": None}
        sub_status = subscription.status.value if hasattr(subscription.status, 'value') else subscription.status
        if sub_status != "active":
            return {"posts": [], "next_cursor": None}

        writer_ids = list(subscription.allocated_writer_ids)
        if not writer_ids:
            return {"posts": [], "next_cursor": None}

        posts = self._post_repo.get_published_for_feed(writer_ids, command.limit, command.cursor)

        # Check if there are more posts
        has_more = len(posts) > command.limit
        if has_more:
            posts = posts[:command.limit]

        # Build response with paywall applied
        post_data = []
        for post in posts:
            has_allocation = subscription.is_writer_allocated(post.writer_id)
            post_data.append(post.get_content_for_reader(has_allocation, command.reader_id))

        next_cursor = None
        if has_more and posts:
            next_cursor = posts[-1].published_at.isoformat() if posts[-1].published_at else None

        return {"posts": post_data, "next_cursor": next_cursor}


class CreatePostHandler(CommandHandler[CreatePostCommand, Post]):
    """Handler for creating draft posts."""

    def __init__(self, service: PublishingService) -> None:
        self._service = service

    def handle(self, command: CreatePostCommand) -> Post:
        return self._service.create_draft(command)


class CreateScheduledPostHandler(CommandHandler[CreateScheduledPostCommand, Post]):
    """Handler for creating scheduled posts."""

    def __init__(self, service: PublishingService) -> None:
        self._service = service

    def handle(self, command: CreateScheduledPostCommand) -> Post:
        return self._service.create_scheduled(command)


class PublishPostHandler(CommandHandler[PublishPostCommand, Post]):
    """Handler for publishing posts."""

    def __init__(self, service: PublishingService) -> None:
        self._service = service

    def handle(self, command: PublishPostCommand) -> Post:
        return self._service.publish_post(command)


class SchedulePostHandler(CommandHandler[SchedulePostCommand, Post]):
    """Handler for scheduling posts."""

    def __init__(self, service: PublishingService) -> None:
        self._service = service

    def handle(self, command: SchedulePostCommand) -> Post:
        return self._service.schedule_post(command)


class CancelPostHandler(CommandHandler[CancelPostCommand, Post]):
    """Handler for cancelling posts."""

    def __init__(self, service: PublishingService) -> None:
        self._service = service

    def handle(self, command: CancelPostCommand) -> Post:
        return self._service.cancel_post(command)


class UpdatePostHandler(CommandHandler[UpdatePostCommand, Post]):
    """Handler for updating posts."""

    def __init__(self, service: PublishingService) -> None:
        self._service = service

    def handle(self, command: UpdatePostCommand) -> Post:
        return self._service.update_post(command)


class GetPostHandler(CommandHandler[GetPostCommand, dict]):
    """Handler for getting posts."""

    def __init__(self, service: PublishingService) -> None:
        self._service = service

    def handle(self, command: GetPostCommand) -> dict:
        return self._service.get_post(command)


class GetWriterPostsHandler(CommandHandler[GetWriterPostsCommand, list[Post]]):
    """Handler for getting writer's posts."""

    def __init__(self, service: PublishingService) -> None:
        self._service = service

    def handle(self, command: GetWriterPostsCommand) -> list[Post]:
        return self._service.get_writer_posts(command)


class GetFeedHandler(CommandHandler[GetFeedCommand, dict]):
    """Handler for getting reader feed."""

    def __init__(self, service: PublishingService) -> None:
        self._service = service

    def handle(self, command: GetFeedCommand) -> dict:
        return self._service.get_feed(command)