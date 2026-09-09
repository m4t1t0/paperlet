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


@celery_app.task(bind=True, max_retries=5)
def send_post_published_emails(self, post_id: str) -> dict:
    """Single email task: fetch post via repo, branch on has_allocation.

    Retry schedule (explicit): 1m, 5m, 15m, 1h, 6h (max 5 retries).
    """
    from celery.exceptions import Retry

    from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
    from backend.src.identity.adapters.sqlalchemy_repository import (
        SqlAlchemyUserRepository,
    )
    from backend.src.publishing.adapters.sqlalchemy_repository import (
        SqlAlchemyPostRepository,
    )
    from backend.src.notifications.domain.model import EmailRecipient
    from backend.src.notifications.service import NotificationService
    from backend.src.notifications.adapters.stub_sender import StubEmailSender

    retry_delays = [60, 300, 900, 3600, 21600]  # 1m, 5m, 15m, 1h, 6h

    def _fail(exc: Exception) -> dict:
        retries = self.request.retries
        if retries < len(retry_delays):
            raise self.retry(
                exc=exc, countdown=retry_delays[retries], max_retries=5
            )
        raise exc

    try:
        post_uuid = UUID(post_id)
    except ValueError as exc:
        return {"status": "error", "message": f"Invalid post_id: {exc}"}

    try:
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

            # Fetch recipients from read models (worker fetches full post + users)
            subscribers = get_subscribers_with_allocation(post.writer_id)
            followers = get_followers_without_allocation(post.writer_id)

            recipients = [
                EmailRecipient(
                    user_id=user.id,
                    email=user.email,
                    has_allocation=True,
                    writer_id=writer.id,
                )
                for user, _ in subscribers
            ] + [
                EmailRecipient(
                    user_id=user.id,
                    email=user.email,
                    has_allocation=False,
                    writer_id=writer.id,
                )
                for user in followers
            ]

            sender = StubEmailSender()
            service = NotificationService(sender)
            service.send_for_post(post=post, writer=writer, recipients=recipients)

            return {
                "status": "sent",
                "post_id": str(post_id),
                "subscribers_notified": len(subscribers),
                "followers_notified": len(followers),
                "emails_logged": len(sender.sent_emails),
            }
    except Retry:
        raise
    except Exception as exc:  # noqa: BLE001 - retry with explicit backoff
        return _fail(exc)


@celery_app.task
def process_scheduled_posts() -> dict:
    """Beat scheduler: publish due posts, then enqueue single email task."""
    from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork
    from backend.src.publishing.adapters.sqlalchemy_repository import (
        SqlAlchemyPostRepository,
    )

    with SqlAlchemyUnitOfWork() as uow:
        post_repo = SqlAlchemyPostRepository(uow.session)
        scheduled_posts = post_repo.get_scheduled_for_publishing()

        results = []
        for post in scheduled_posts:
            post.publish()
            uow.commit()
            post.clear_events()  # consumed here; email path is the task below
            # Single email path (post_id only)
            send_post_published_emails.delay(str(post.id))
            results.append(str(post.id))

        return {"status": "processed", "published_posts": results}
