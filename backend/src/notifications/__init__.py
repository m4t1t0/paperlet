"""Notifications context exports."""
from backend.src.notifications.adapters.email import EmailRecipient, EmailTemplateRenderer, NotificationSender, SendResult
from backend.src.notifications.adapters.stub_sender import LoggingEmailSender, StubEmailSender
from backend.src.notifications.domain.model import EmailBatch, EmailRecipient
from backend.src.notifications.service import NotificationService
from backend.src.notifications.tasks import celery_app, process_scheduled_posts, send_post_published_emails

__all__ = [
    "EmailRecipient",
    "EmailTemplateRenderer",
    "NotificationSender",
    "SendResult",
    "StubEmailSender",
    "LoggingEmailSender",
    "EmailBatch",
    "NotificationService",
    "celery_app",
    "send_post_published_emails",
    "process_scheduled_posts",
]