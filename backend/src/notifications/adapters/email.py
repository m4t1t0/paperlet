"""Notification sender interface."""

from __future__ import annotations
from typing import Protocol

from backend.src.notifications.domain.model import EmailRecipient, SendResult


class NotificationSender(Protocol):
    """Protocol for notification senders."""

    def send_batch(
        self,
        recipients: list[EmailRecipient],
        template: str,
        context: dict,
    ) -> list[SendResult]:
        """Send a batch of emails."""
        ...


class EmailTemplateRenderer:
    """Render email templates."""

    @staticmethod
    def render_post_published_full(
        recipient: EmailRecipient,
        post_title: str,
        post_preview: str,
        post_full: str,
        writer_name: str,
    ) -> tuple[str, str]:
        """Render full post email for allocated readers."""
        subject = f"New post from {writer_name}: {post_title}"
        html = f"""
        <html>
        <body>
            <h1>{post_title}</h1>
            <p>By {writer_name}</p>
            <hr>
            <div>{post_full}</div>
        </body>
        </html>
        """
        return subject, html

    @staticmethod
    def render_post_published_preview(
        recipient: EmailRecipient,
        post_title: str,
        post_preview: str,
        writer_name: str,
        subscribe_url: str,
    ) -> tuple[str, str]:
        """Render preview email for non-allocated readers."""
        subject = f"New post from {writer_name}: {post_title} (preview)"
        html = f"""
        <html>
        <body>
            <h1>{post_title}</h1>
            <p>By {writer_name}</p>
            <hr>
            <div>{post_preview}</div>
            <hr>
            <p><a href="{subscribe_url}">Subscribe to read the full post</a></p>
        </body>
        </html>
        """
        return subject, html
