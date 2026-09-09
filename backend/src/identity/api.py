"""Identity API routes."""

from __future__ import annotations
from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest

from backend.src.identity.api_auth import get_bearer_user_id
from backend.src.identity.commands import (
    GetProfileCommand,
    LoginCommand,
    RefreshTokenCommand,
    RegisterCommand,
)
from backend.src.identity.domain.model import UserRole
from backend.src.shared.service_layer.messagebus import MessageBus

# Re-export for type checking
__all__ = ["UserRole"]

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


def get_bus() -> MessageBus:
    """Get message bus from app context."""
    from flask import current_app

    return current_app.message_bus


@auth_bp.route("/register", methods=["POST"])
def register() -> tuple:
    """Register a new user."""
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")
    role_str = data.get("role", "reader")

    if not email or not password:
        raise BadRequest("Email and password are required")

    try:
        role = UserRole(role_str)
    except ValueError:
        raise BadRequest(f"Invalid role: {role_str}")

    command = RegisterCommand(email=email, password=password, role=role)
    bus = get_bus()
    user = bus.handle(command)

    return jsonify(
        {
            "id": str(user.id),
            "email": user.email,
            "roles": [r.value for r in user.roles],
            "created_at": user.created_at.isoformat(),
        }
    ), 201


@auth_bp.route("/login", methods=["POST"])
def login() -> tuple:
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
def refresh() -> tuple:
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
def me() -> tuple:
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
            "roles": [r.value for r in user.roles],
            "created_at": user.created_at.isoformat(),
            "is_writer": user.is_writer(),
            "is_reader": user.is_reader(),
        }
    )
