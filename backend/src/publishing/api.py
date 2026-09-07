"""Publishing API routes."""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest, NotFound, Unauthorized

from backend.src.identity.domain.model import User
from backend.src.identity.service import JwtService
from backend.src.shared.service_layer.messagebus import MessageBus
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
from backend.src.publishing.domain.model import PostStatus

posts_bp = Blueprint("posts", __name__, url_prefix="/api/v1/posts")


def get_bus() -> MessageBus:
    """Get message bus from app context."""
    from flask import current_app
    return current_app.message_bus


def get_current_user(require_writer: bool = False) -> dict:
    """Get current user from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise Unauthorized("Missing or invalid Authorization header")

    access_token = auth_header[7:]
    jwt_service = JwtService()
    try:
        user_id, _ = jwt_service.verify_access_token(access_token)
    except ValueError as e:
        raise Unauthorized(str(e))

    from backend.src.identity.adapters.sqlalchemy_repository import SqlAlchemyUserRepository
    from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork

    with SqlAlchemyUnitOfWork() as uow:
        user_repo = SqlAlchemyUserRepository(uow.session)
        user = user_repo.get(user_id)
        if not user or not user.is_active:
            raise Unauthorized("User not found or inactive")
        if require_writer and not user.is_writer():
            raise Unauthorized("Writer capability required")
        return {"id": user.id, "is_writer": user.is_writer(), "is_reader": user.is_reader()}


def get_current_reader() -> dict:
    """Get current user as reader (no writer requirement)."""
    return get_current_user(require_writer=False)


def get_current_writer() -> dict:
    """Get current user as writer."""
    return get_current_user(require_writer=True)


@posts_bp.route("", methods=["POST"])
def create_post() -> tuple:
    """Create a draft or scheduled post."""
    writer = get_current_writer()
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

    if scheduled_at:
        from datetime import datetime
        try:
            scheduled_for = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except ValueError:
            raise BadRequest("Invalid scheduled_at format, use ISO 8601")

        command = CreateScheduledPostCommand(
            writer_id=writer["id"],
            title=title,
            preview_content=preview_content,
            subscriber_content=subscriber_content,
            scheduled_for=scheduled_for,
        )
    else:
        command = CreatePostCommand(
            writer_id=writer["id"],
            title=title,
            preview_content=preview_content,
            subscriber_content=subscriber_content,
        )

    post = bus.handle(command)

    return jsonify({
        "id": str(post.id),
        "title": post.title,
        "status": post.status.value,
        "scheduled_for": post.scheduled_for.isoformat() if post.scheduled_for else None,
        "created_at": post.created_at.isoformat(),
    }), 201


@posts_bp.route("/<post_id>/publish", methods=["POST"])
def publish_post(post_id: str) -> tuple:
    """Publish a post immediately."""
    writer = get_current_writer()

    from uuid import UUID
    try:
        post_uuid = UUID(post_id)
    except ValueError:
        raise BadRequest("Invalid post_id format")

    command = PublishPostCommand(writer_id=writer["id"], post_id=post_uuid)
    bus = get_bus()
    post = bus.handle(command)

    return jsonify({
        "id": str(post.id),
        "title": post.title,
        "status": post.status.value,
        "published_at": post.published_at.isoformat() if post.published_at else None,
    })


@posts_bp.route("/<post_id>/schedule", methods=["POST"])
def schedule_post(post_id: str) -> tuple:
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

    from uuid import UUID
    try:
        post_uuid = UUID(post_id)
    except ValueError:
        raise BadRequest("Invalid post_id format")

    command = SchedulePostCommand(writer_id=writer["id"], post_id=post_uuid, scheduled_for=scheduled_for)
    bus = get_bus()
    post = bus.handle(command)

    return jsonify({
        "id": str(post.id),
        "title": post.title,
        "status": post.status.value,
        "scheduled_for": post.scheduled_for.isoformat() if post.scheduled_for else None,
    })


@posts_bp.route("/<post_id>", methods=["DELETE"])
def cancel_post(post_id: str) -> tuple:
    """Cancel a scheduled post."""
    writer = get_current_writer()

    from uuid import UUID
    try:
        post_uuid = UUID(post_id)
    except ValueError:
        raise BadRequest("Invalid post_id format")

    command = CancelPostCommand(writer_id=writer["id"], post_id=post_uuid)
    bus = get_bus()
    post = bus.handle(command)

    return jsonify({
        "id": str(post.id),
        "title": post.title,
        "status": post.status.value,
    })


@posts_bp.route("/<post_id>", methods=["PATCH"])
def update_post(post_id: str) -> tuple:
    """Update post content."""
    writer = get_current_writer()
    data = request.get_json() or {}

    from uuid import UUID
    try:
        post_uuid = UUID(post_id)
    except ValueError:
        raise BadRequest("Invalid post_id format")

    command = UpdatePostCommand(
writer_id=writer["id"],
        post_id=post_uuid,
        title=data.get("title"),
        preview_content=data.get("preview_content"),
        subscriber_content=data.get("subscriber_content"),
    )
    bus = get_bus()
    post = bus.handle(command)

    return jsonify({
        "id": str(post.id),
        "title": post.title,
        "status": post.status.value,
        "updated_at": post.updated_at.isoformat(),
    })


@posts_bp.route("/<post_id>", methods=["GET"])
def get_post(post_id: str) -> tuple:
    """Get a single post with paywall logic."""
    reader = get_current_reader()

    from uuid import UUID
    try:
        post_uuid = UUID(post_id)
    except ValueError:
        raise BadRequest("Invalid post_id format")

    command = GetPostCommand(post_id=post_uuid, reader_id=reader["id"])
    bus = get_bus()
    result = bus.handle(command)

    return jsonify(result)


@posts_bp.route("/feed", methods=["GET"])
def get_feed() -> tuple:
    """Get reader's feed of posts from allocated writers."""
    reader = get_current_reader()

    limit = request.args.get("limit", 20, type=int)
    cursor = request.args.get("cursor")

    command = GetFeedCommand(reader_id=reader["id"], limit=limit, cursor=cursor)
    bus = get_bus()
    result = bus.handle(command)

    return jsonify(result)


@posts_bp.route("/writer", methods=["GET"])
def get_writer_posts() -> tuple:
    """Get current writer's posts."""
    writer = get_current_writer()

    status = request.args.get("status")

    command = GetWriterPostsCommand(writer_id=writer["id"], status=status)
    bus = get_bus()
    posts = bus.handle(command)

    return jsonify({
        "posts": [
            {
                "id": str(p.id),
                "title": p.title,
                "status": p.status.value,
                "preview_content": p.preview_content,
                "subscriber_content": p.subscriber_content,
                "scheduled_for": p.scheduled_for.isoformat() if p.scheduled_for else None,
                "published_at": p.published_at.isoformat() if p.published_at else None,
                "created_at": p.created_at.isoformat(),
            }
            for p in posts
        ]
    })