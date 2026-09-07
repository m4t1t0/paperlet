"""Unit tests for Post domain model."""
from __future__ import annotations
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from backend.src.publishing.domain.model import Post, PostStatus


class TestPost:
    """Tests for Post aggregate."""

    def setup_method(self) -> None:
        self.writer_id = uuid4()

    def test_create_draft(self) -> None:
        post = Post.create_draft(
            writer_id=self.writer_id,
            title="Test Post",
            preview_content="Preview",
            subscriber_content="Full content",
        )
        assert post.writer_id == self.writer_id
        assert post.title == "Test Post"
        assert post.preview_content == "Preview"
        assert post.subscriber_content == "Full content"
        assert post.status == PostStatus.DRAFT
        assert post.scheduled_for is None
        assert post.published_at is None

    def test_create_scheduled(self) -> None:
        future = datetime.utcnow() + timedelta(hours=1)
        post = Post.create_scheduled(
            writer_id=self.writer_id,
            title="Scheduled Post",
            preview_content="Preview",
            subscriber_content="Full",
            scheduled_for=future,
        )
        assert post.status == PostStatus.SCHEDULED
        assert post.scheduled_for == future
        assert len(post.events) == 1
        assert post.events[0].__class__.__name__ == "PostScheduled"

    def test_create_scheduled_fails_for_past_time(self) -> None:
        past = datetime.utcnow() - timedelta(hours=1)
        with pytest.raises(ValueError, match="future"):
            Post.create_scheduled(
                writer_id=self.writer_id,
                title="Test",
                preview_content="Preview",
                subscriber_content="Full",
                scheduled_for=past,
            )

    def test_publish_draft(self) -> None:
        post = Post.create_draft(self.writer_id, "Test", "Preview", "Full")
        post.clear_events()

        post.publish()
        assert post.status == PostStatus.PUBLISHED
        assert post.published_at is not None
        assert len(post.events) == 1
        assert post.events[0].__class__.__name__ == "PostPublished"

    def test_publish_scheduled(self) -> None:
        future = datetime.utcnow() + timedelta(hours=1)
        post = Post.create_scheduled(self.writer_id, "Test", "Preview", "Full", future)
        post.clear_events()

        post.publish()
        assert post.status == PostStatus.PUBLISHED

    def test_publish_fails_if_already_published(self) -> None:
        post = Post.create_draft(self.writer_id, "Test", "Preview", "Full")
        post.publish()
        with pytest.raises(ValueError, match="already published"):
            post.publish()

    def test_publish_fails_if_cancelled(self) -> None:
        post = Post.create_draft(self.writer_id, "Test", "Preview", "Full")
        post.cancel()
        with pytest.raises(ValueError, match="cancelled"):
            post.publish()

    def test_schedule_draft(self) -> None:
        post = Post.create_draft(self.writer_id, "Test", "Preview", "Full")
        post.clear_events()
        future = datetime.utcnow() + timedelta(hours=1)

        post.schedule(future)
        assert post.status == PostStatus.SCHEDULED
        assert post.scheduled_for == future
        assert len(post.events) == 1

    def test_schedule_fails_if_published(self) -> None:
        post = Post.create_draft(self.writer_id, "Test", "Preview", "Full")
        post.publish()
        with pytest.raises(ValueError, match="published"):
            post.schedule(datetime.utcnow() + timedelta(hours=1))

    def test_cancel_draft(self) -> None:
        post = Post.create_draft(self.writer_id, "Test", "Preview", "Full")
        post.clear_events()

        post.cancel()
        assert post.status == PostStatus.CANCELLED
        assert len(post.events) == 1
        assert post.events[0].__class__.__name__ == "PostCancelled"

    def test_cancel_scheduled(self) -> None:
        future = datetime.utcnow() + timedelta(hours=1)
        post = Post.create_scheduled(self.writer_id, "Test", "Preview", "Full", future)
        post.clear_events()

        post.cancel()
        assert post.status == PostStatus.CANCELLED

    def test_cancel_fails_if_published(self) -> None:
        post = Post.create_draft(self.writer_id, "Test", "Preview", "Full")
        post.publish()
        with pytest.raises(ValueError, match="draft or scheduled"):
            post.cancel()

    def test_update_content_draft(self) -> None:
        post = Post.create_draft(self.writer_id, "Old Title", "Old Preview", "Old Full")
        post.clear_events()

        post.update_content(title="New Title", preview_content="New Preview")
        assert post.title == "New Title"
        assert post.preview_content == "New Preview"
        assert post.subscriber_content == "Old Full"

    def test_update_content_fails_if_published(self) -> None:
        post = Post.create_draft(self.writer_id, "Test", "Preview", "Full")
        post.publish()
        with pytest.raises(ValueError, match="published"):
            post.update_content(title="New")

    def test_update_content_fails_if_cancelled(self) -> None:
        post = Post.create_draft(self.writer_id, "Test", "Preview", "Full")
        post.cancel()
        with pytest.raises(ValueError, match="cancelled"):
            post.update_content(title="New")

    def test_get_content_for_reader_with_allocation(self) -> None:
        post = Post.create_draft(self.writer_id, "Test", "Preview", "Full Content")
        post.publish()

        content = post.get_content_for_reader(has_allocation=True)
        assert content["preview_content"] == "Preview"
        assert content["subscriber_content"] == "Full Content"
        assert content["has_full_access"] is True

    def test_get_content_for_reader_without_allocation(self) -> None:
        post = Post.create_draft(self.writer_id, "Test", "Preview", "Full Content")
        post.publish()

        content = post.get_content_for_reader(has_allocation=False)
        assert content["preview_content"] == "Preview"
        assert content["subscriber_content"] is None
        assert content["has_full_access"] is False

    def test_is_scheduled_for_publishing(self) -> None:
        # Create a post directly with past scheduled time (bypass validation)
        past = datetime.utcnow() - timedelta(minutes=1)
        post = Post(
            writer_id=self.writer_id,
            title="Test",
            preview_content="Preview",
            subscriber_content="Full",
            status=PostStatus.SCHEDULED,
            scheduled_for=past,
        )
        assert post.is_scheduled_for_publishing()

        future = datetime.utcnow() + timedelta(hours=1)
        post2 = Post(
            writer_id=self.writer_id,
            title="Test",
            preview_content="Preview",
            subscriber_content="Full",
            status=PostStatus.SCHEDULED,
            scheduled_for=future,
        )
        assert not post2.is_scheduled_for_publishing()

        post3 = Post.create_draft(self.writer_id, "Test", "Preview", "Full")
        assert not post3.is_scheduled_for_publishing()