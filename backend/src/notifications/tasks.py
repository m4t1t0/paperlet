"""Celery tasks for notifications."""

from __future__ import annotations
from celery import Celery
from uuid import UUID

from backend.src.shared.config import get_settings
from backend.src.notifications.service import (
    get_subscribers_with_allocation,
    get_followers_without_allocation,
)

settings = get_settings()

celery_app = Celery(
    "paperlet_notifications",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=60,  # 1 minute
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=3600,  # 1 hour max
    retry_jitter=True,
)
def send_post_published_emails(self, post_id: str) -> dict:
    """Send post published emails in batches."""
    from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
    from backend.src.identity.adapters.sqlalchemy_repository import (
        SqlAlchemyUserRepository,
    )
    from backend.src.publishing.adapters.sqlalchemy_repository import (
        SqlAlchemyPostRepository,
    )
    from backend.src.notifications.service import NotificationService
    from backend.src.notifications.adapters.stub_sender import StubEmailSender

    post_uuid = UUID(post_id)

    with SqlAlchemyUnitOfWork() as uow:
        post_repo = SqlAlchemyPostRepository(uow.session)
        post = post_repo.get(post_uuid)
        if not post:
            return {"status": "error", "message": "Post not found"}

        if post.status.value != "published":
            return {"status": "skipped", "message": "Post not published"}

        user_repo = SqlAlchemyUserRepository(uow.session)
        writer = user_repo.get(post.writer_id)
        if not writer:
            return {"status": "error", "message": "Writer not found"}

        # Get subscribers and followers from read models
        subscribers = get_subscribers_with_allocation(post.writer_id)
        followers = get_followers_without_allocation(post.writer_id)

        sender = StubEmailSender()
        service = NotificationService(sender)

        service.send_post_published_notifications(
            post=post,
            writer=writer,
            subscribers_with_allocation=subscribers,
            followers_without_allocation=followers,
        )

        return {
            "status": "sent",
            "post_id": str(post_id),
            "subscribers_notified": len(subscribers),
            "followers_notified": len(followers),
            "emails_logged": len(sender.sent_emails),
        }


@celery_app.task
def process_scheduled_posts() -> dict:
    """Process posts scheduled for publishing now."""
    from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
    from backend.src.publishing.adapters.sqlalchemy_repository import (
        SqlAlchemyPostRepository,
    )
    from backend.src.shared.service_layer.messagebus import MessageBus

    with SqlAlchemyUnitOfWork() as uow:
        post_repo = SqlAlchemyPostRepository(uow.session)
        scheduled_posts = post_repo.get_scheduled_for_publishing()

        results = []
        for post in scheduled_posts:
            post.publish()
            uow.commit()
            # Publish domain event
            bus = MessageBus()
            bus.publish_all(post.events)
            # Trigger email task
            send_post_published_emails.delay(str(post.id))
            results.append(str(post.id))

        return {"status": "processed", "published_posts": results}
