"""Notifications service."""

from __future__ import annotations
from typing import TYPE_CHECKING
from uuid import UUID

from backend.src.notifications.adapters.email import EmailTemplateRenderer
from backend.src.notifications.adapters.stub_sender import StubEmailSender
from backend.src.notifications.domain.model import EmailRecipient
from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
from backend.src.shared.config import get_settings
from backend.src.subscriptions.adapters.read_model import (
    get_subscribers_with_allocation as read_model_get_subscribers,
    get_followers_without_allocation as read_model_get_followers,
)

if TYPE_CHECKING:
    from backend.src.publishing.domain.model import Post
    from backend.src.identity.domain.model import User
    from backend.src.subscriptions.domain.model import Subscription


class NotificationService:
    """Service for sending post publication notifications."""

    def __init__(self, sender: StubEmailSender | None = None) -> None:
        self._sender = sender or StubEmailSender()
        self._renderer = EmailTemplateRenderer()
        self._settings = get_settings()

    def send_post_published_notifications(
        self,
        post: "Post",
        writer: "User",
        subscribers_with_allocation: list[tuple["User", "Subscription"]],
        followers_without_allocation: list["User"],
    ) -> None:
        """Send post published notifications to two groups."""
        # Group 1: Subscribers with allocation - full post
        allocation_recipients = [
            EmailRecipient(
                user_id=user.id,
                email=user.email,
                has_allocation=True,
                writer_id=writer.id,
            )
            for user, _ in subscribers_with_allocation
        ]

        if allocation_recipients:
            subject, html = self._renderer.render_post_published_full(
                recipient=allocation_recipients[0],  # Template uses first for rendering
                post_title=post.title,
                post_preview=post.preview_content,
                post_full=post.subscriber_content,
                writer_name=writer.email,  # Use email as name for now
            )
            self._sender.send_batch(
                allocation_recipients,
                "post_published_full",
                {
                    "subject": subject,
                    "html": html,
                    "post_title": post.title,
                    "post_full": post.subscriber_content,
                    "writer_name": writer.email,
                },
            )

        # Group 2: Followers without allocation - preview + upsell
        preview_recipients = [
            EmailRecipient(
                user_id=user.id,
                email=user.email,
                has_allocation=False,
                writer_id=writer.id,
            )
            for user in followers_without_allocation
        ]

        if preview_recipients:
            subscribe_url = f"{self._settings.api_prefix}/subscriptions/subscribe"
            subject, html = self._renderer.render_post_published_preview(
                recipient=preview_recipients[0],
                post_title=post.title,
                post_preview=post.preview_content,
                writer_name=writer.email,
                subscribe_url=subscribe_url,
            )
            self._sender.send_batch(
                preview_recipients,
                "post_published_preview",
                {
                    "subject": subject,
                    "html": html,
                    "post_title": post.title,
                    "post_preview": post.preview_content,
                    "writer_name": writer.email,
                    "subscribe_url": subscribe_url,
                },
            )


def get_subscribers_with_allocation(
    post_writer_id: UUID,
) -> list[tuple["User", "Subscription"]]:
    """Get all users with active allocation to a writer using read model."""
    with SqlAlchemyUnitOfWork() as uow:
        return read_model_get_subscribers(uow.session, post_writer_id)


def get_followers_without_allocation(post_writer_id: UUID) -> list["User"]:
    """Get users following a writer but without allocation using read model."""
    with SqlAlchemyUnitOfWork() as uow:
        return read_model_get_followers(uow.session, post_writer_id)
