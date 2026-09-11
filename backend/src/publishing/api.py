"""Publishing API routes."""

from __future__ import annotations
from typing import Any, cast

from flask import Blueprint, Response, jsonify, request
from werkzeug.exceptions import BadRequest, NotFound
from uuid import UUID

from backend.src.identity.api_auth import (
    get_current_reader,
    get_current_user,
    get_current_writer,
    get_optional_reader,
)
from backend.src.shared.domain.value_objects import PostId, ReaderId, WriterId
from backend.src.shared.service_layer.messagebus import MessageBus
from backend.src.publishing.commands import (
    CancelPostCommand,
    CreatePostCommand,
    CreateScheduledPostCommand,
    GetFeedCommand,
    GetPostCommand,
    GetRecentPostsCommand,
    GetWriterPostsCommand,
    PublishPostCommand,
    SchedulePostCommand,
    UpdatePostCommand,
)

posts_bp = Blueprint("posts", __name__, url_prefix="/api/v1/posts")


def get_bus() -> MessageBus:
    """Get message bus from app context."""
    from flask import current_app

    return cast(MessageBus, getattr(current_app, "message_bus"))


@posts_bp.route("", methods=["POST"])
def create_post() -> Response | tuple[Any, ...]:
    """Create a draft or scheduled post.

    Any authenticated user may create a first post — doing so grants the
    WRITER capability (roles are inferred from activity, not signup).
    """
    writer = get_current_user()
    data = request.get_json() or {}

    title = data.get("title", "").strip()
    preview_content = data.get("preview_content", "")
    subscriber_content = data.get("subscriber_content", "")
    scheduled_at = data.get("scheduled_at")

    if not title:
        raise BadRequest("Title is required")
    if not preview_content:
        raise BadRequest("Preview content is required")

    bus = get_bus()

    command: CreatePostCommand | CreateScheduledPostCommand
    if scheduled_at:
        from datetime import datetime

        try:
            scheduled_for = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except ValueError:
            raise BadRequest("Invalid scheduled_at format, use ISO 8601")

        command = CreateScheduledPostCommand(
            writer_id=WriterId(value=writer["id"]),
            title=title,
            preview_content=preview_content,
            subscriber_content=subscriber_content,
            scheduled_for=scheduled_for,
        )
    else:
        command = CreatePostCommand(
            writer_id=WriterId(value=writer["id"]),
            title=title,
            preview_content=preview_content,
            subscriber_content=subscriber_content,
        )

    post = bus.handle(command)

    return jsonify(
        {
            "id": str(post.id),
            "title": post.title,
            "status": post.status.value,
            "scheduled_for": post.scheduled_for.isoformat()
            if post.scheduled_for
            else None,
            "created_at": post.created_at.isoformat(),
        }
    ), 201


@posts_bp.route("/<post_id>/publish", methods=["POST"])
def publish_post(post_id: str) -> Response | tuple[Any, ...]:
    """Publish a post immediately."""
    writer = get_current_writer()

    try:
        post_uuid = UUID(post_id)
    except ValueError:
        raise BadRequest("Invalid post_id format")

    command = PublishPostCommand(writer_id=WriterId(value=writer["id"]), post_id=PostId(value=post_uuid))
    bus = get_bus()
    post = bus.handle(command)

    return jsonify(
        {
            "id": str(post.id),
            "title": post.title,
            "status": post.status.value,
            "published_at": post.published_at.isoformat()
            if post.published_at
            else None,
        }
    )


@posts_bp.route("/<post_id>/schedule", methods=["POST"])
def schedule_post(post_id: str) -> Response | tuple[Any, ...]:
    """Schedule a draft post."""
    writer = get_current_writer()
    data = request.get_json() or {}
    scheduled_at = data.get("scheduled_at")

    if not scheduled_at:
        raise BadRequest("scheduled_at is required")

    from datetime import datetime

    try:
        scheduled_for = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
    except ValueError:
        raise BadRequest("Invalid scheduled_at format, use ISO 8601")

    try:
        post_uuid = UUID(post_id)
    except ValueError:
        raise BadRequest("Invalid post_id format")

    command = SchedulePostCommand(
        writer_id=WriterId(value=writer["id"]), post_id=PostId(value=post_uuid), scheduled_for=scheduled_for
    )
    bus = get_bus()
    post = bus.handle(command)

    return jsonify(
        {
            "id": str(post.id),
            "title": post.title,
            "status": post.status.value,
            "scheduled_for": post.scheduled_for.isoformat()
            if post.scheduled_for
            else None,
        }
    )


@posts_bp.route("/<post_id>", methods=["DELETE"])
def cancel_post(post_id: str) -> Response | tuple[Any, ...]:
    """Cancel a scheduled post."""
    writer = get_current_writer()

    try:
        post_uuid = UUID(post_id)
    except ValueError:
        raise BadRequest("Invalid post_id format")

    command = CancelPostCommand(writer_id=WriterId(value=writer["id"]), post_id=PostId(value=post_uuid))
    bus = get_bus()
    post = bus.handle(command)

    return jsonify(
        {
            "id": str(post.id),
            "title": post.title,
            "status": post.status.value,
        }
    )


@posts_bp.route("/<post_id>", methods=["PATCH"])
def update_post(post_id: str) -> Response | tuple[Any, ...]:
    """Update post content."""
    writer = get_current_writer()
    data = request.get_json() or {}

    try:
        post_uuid = UUID(post_id)
    except ValueError:
        raise BadRequest("Invalid post_id format")

    command = UpdatePostCommand(
        writer_id=WriterId(value=writer["id"]),
        post_id=PostId(value=post_uuid),
        title=data.get("title"),
        preview_content=data.get("preview_content"),
        subscriber_content=data.get("subscriber_content"),
    )
    bus = get_bus()
    post = bus.handle(command)

    return jsonify(
        {
            "id": str(post.id),
            "title": post.title,
            "status": post.status.value,
            "updated_at": post.updated_at.isoformat(),
        }
    )


@posts_bp.route("/<post_id>", methods=["GET"])
def get_post(post_id: str) -> Response | tuple[Any, ...]:
    """Get a single post with paywall logic (public preview, no auth required)."""
    reader = get_optional_reader()

    try:
        post_uuid = UUID(post_id)
    except ValueError:
        raise BadRequest("Invalid post_id format")

    command = GetPostCommand(
        post_id=PostId(value=post_uuid),
        reader_id=ReaderId(value=reader["id"]) if reader else None,
    )
    bus = get_bus()
    try:
        result = bus.handle(command)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise NotFound(str(e))
        raise BadRequest(str(e))

    return jsonify(result)


@posts_bp.route("/recent", methods=["GET"])
def get_recent_posts() -> Response | tuple[Any, ...]:
    """Get latest published posts (public, preview-masked — homepage feed)."""
    limit = request.args.get("limit", 10, type=int)
    command = GetRecentPostsCommand(limit=max(1, min(limit, 50)))
    bus = get_bus()
    return jsonify(bus.handle(command))


@posts_bp.route("/feed", methods=["GET"])
def get_feed() -> Response | tuple[Any, ...]:
    """Get reader's feed of posts from allocated writers."""
    reader = get_current_reader()

    limit = request.args.get("limit", 20, type=int)
    cursor = request.args.get("cursor")

    command = GetFeedCommand(reader_id=ReaderId(value=reader["id"]), limit=limit, cursor=cursor)
    bus = get_bus()
    result = bus.handle(command)

    return jsonify(result)


@posts_bp.route("/writer", methods=["GET"])
def get_writer_posts() -> Response | tuple[Any, ...]:
    """Get current writer's posts."""
    writer = get_current_writer()

    status = request.args.get("status")

    command = GetWriterPostsCommand(writer_id=WriterId(value=writer["id"]), status=status)
    bus = get_bus()
    posts = bus.handle(command)

    return jsonify(
        {
            "posts": [
                {
                    "id": str(p.id),
                    "title": p.title,
                    "status": p.status.value,
                    "preview_content": p.preview_content,
                    "subscriber_content": p.subscriber_content,
                    "scheduled_for": p.scheduled_for.isoformat()
                    if p.scheduled_for
                    else None,
                    "published_at": p.published_at.isoformat()
                    if p.published_at
                    else None,
                    "created_at": p.created_at.isoformat(),
                }
                for p in posts
            ]
        }
    )
