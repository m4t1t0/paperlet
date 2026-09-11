"""Identity API routes."""

from __future__ import annotations
from typing import Any, cast

from flask import Blueprint, Response, jsonify, request
from werkzeug.exceptions import BadRequest

from backend.src.identity.api_auth import get_bearer_user_id
from backend.src.identity.commands import (
    GetProfileCommand,
    LoginCommand,
    RefreshTokenCommand,
    RegisterCommand,
)
from backend.src.shared.service_layer.messagebus import MessageBus

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


def get_bus() -> MessageBus:
    """Get message bus from app context."""
    from flask import current_app

    return cast(MessageBus, getattr(current_app, "message_bus"))


@auth_bp.route("/register", methods=["POST"])
def register() -> Response | tuple[Any, ...]:
    """Register a new user (email + password only; no role).

    Reader/Writer capabilities are inferred from activity, never chosen at
    signup: creating a post grants WRITER, subscribing/following grants READER.
    A client-sent `role` field, if present, is ignored for backwards compat.
    """
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        raise BadRequest("Email and password are required")

    def _optional_str(value: object) -> str | None:
        text = str(value).strip() if value is not None else ""
        return text or None

    command = RegisterCommand(
        email=email,
        password=password,
        first_name=_optional_str(data.get("first_name")),
        last_name=_optional_str(data.get("last_name")),
        avatar_url=_optional_str(data.get("avatar_url")),
    )
    bus = get_bus()
    user = bus.handle(command)

    return jsonify(
        {
            "id": str(user.id),
            "email": user.email,
            "created_at": user.created_at.isoformat(),
        }
    ), 201


@auth_bp.route("/login", methods=["POST"])
def login() -> Response | tuple[Any, ...]:
    """Login and get tokens."""
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        raise BadRequest("Email and password are required")

    command = LoginCommand(
        email=email,
        password=password,
        user_agent=request.headers.get("User-Agent"),
        ip=request.remote_addr,
    )
    bus = get_bus()
    tokens = bus.handle(command)

    return jsonify(
        {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_in": tokens.expires_in,
            "token_type": tokens.token_type,
        }
    )


@auth_bp.route("/refresh", methods=["POST"])
def refresh() -> Response | tuple[Any, ...]:
    """Refresh access token."""
    data = request.get_json() or {}
    refresh_token = data.get("refresh_token", "")

    if not refresh_token:
        raise BadRequest("Refresh token is required")

    command = RefreshTokenCommand(
        refresh_token=refresh_token,
        user_agent=request.headers.get("User-Agent"),
        ip=request.remote_addr,
    )
    bus = get_bus()
    tokens = bus.handle(command)

    return jsonify(
        {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_in": tokens.expires_in,
            "token_type": tokens.token_type,
        }
    )


@auth_bp.route("/me", methods=["GET"])
def me() -> Response | tuple[Any, ...]:
    """Get current user profile."""
    user_id = get_bearer_user_id()
    bus = get_bus()

    from backend.src.shared.domain.value_objects import UserId

    command = GetProfileCommand(user_id=UserId(value=user_id))
    user = bus.handle(command)

    return jsonify(
        {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "avatar_url": user.avatar_url,
            "created_at": user.created_at.isoformat(),
            "is_writer": user.is_writer(),
            "is_reader": user.is_reader(),
        }
    )
