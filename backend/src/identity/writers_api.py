"""Writers Catalog API routes (/api/v1/writers)."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, jsonify, request
from uuid import UUID
from werkzeug.exceptions import BadRequest, NotFound

from backend.src.identity.api_auth import get_optional_reader_id

writers_bp = Blueprint("writers", __name__, url_prefix="/api/v1/writers")


@writers_bp.route("", methods=["GET"])
def list_writers() -> Response | tuple[Any, ...]:
    """Searchable list of public writers."""
    from backend.src.identity.adapters.sqlalchemy_repository import (
        SqlAlchemyUserRepository,
    )
    from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork

    query = request.args.get("q", "").strip().lower()
    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)

    with SqlAlchemyUnitOfWork() as uow:
        user_repo = SqlAlchemyUserRepository(uow.session)
        users = user_repo.list()
        writers = [u for u in users if u.is_writer()]
        if query:
            writers = [w for w in writers if query in w.email.lower()]
        total = len(writers)
        writers = writers[offset : offset + limit]
        result = [
            {
                "id": str(w.id),
                "email": w.email,
                "created_at": w.created_at.isoformat(),
            }
            for w in writers
        ]
    return jsonify({"writers": result, "total": total})


@writers_bp.route("/<writer_id>", methods=["GET"])
def get_writer(writer_id: str) -> Response | tuple[Any, ...]:
    """Writer profile & past newsletters (paywall-masked for non-subscribers)."""
    try:
        writer_uuid = UUID(writer_id)
    except ValueError:
        raise BadRequest("Invalid writer_id format")

    from backend.src.identity.adapters.sqlalchemy_repository import (
        SqlAlchemyUserRepository,
    )
    from backend.src.publishing.adapters.sqlalchemy_repository import (
        SqlAlchemyPostRepository,
    )
    from backend.src.subscriptions.adapters.sqlalchemy_repository import (
        SqlAlchemySubscriptionRepository,
    )
    from backend.src.publishing.domain.model import PostStatus
    from backend.src.shared.adapters.unit_of_work import SqlAlchemyUnitOfWork

    reader_id = get_optional_reader_id()

    with SqlAlchemyUnitOfWork() as uow:
        user_repo = SqlAlchemyUserRepository(uow.session)
        writer = user_repo.get(writer_uuid)
        if not writer or not writer.is_writer():
            raise NotFound("Writer not found")

        post_repo = SqlAlchemyPostRepository(uow.session)
        posts = post_repo.get_by_writer(writer_uuid, PostStatus.PUBLISHED)

        has_allocation = False
        if reader_id:
            sub_repo = SqlAlchemySubscriptionRepository(uow.session)
            subscription = sub_repo.get_by_reader(reader_id)
            if subscription:
                status = (
                    subscription.status.value
                    if hasattr(subscription.status, "value")
                    else subscription.status
                )
                if status == "active":
                    has_allocation = subscription.is_writer_allocated(writer_uuid)

        post_data = [
            p.get_content_for_reader(has_allocation, reader_id) for p in posts
        ]

        result = {
            "id": str(writer.id),
            "email": writer.email,
            "created_at": writer.created_at.isoformat(),
            "subscriber_post_count": len(post_data),
            "posts": post_data,
        }
    return jsonify(result)
