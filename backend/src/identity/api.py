"""Identity API routes."""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest, Unauthorized

from backend.src.identity.commands import GetProfileCommand, LoginCommand, RefreshTokenCommand, RegisterCommand
from backend.src.identity.domain.model import UserRole
from backend.src.shared.service_layer.messagebus import MessageBus

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

    return jsonify({
        "id": str(user.id),
        "email": user.email,
        "roles": [r.value for r in user.roles],
        "created_at": user.created_at.isoformat(),
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login() -> tuple:
    """Login and get tokens."""
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        raise BadRequest("Email and password are required")

    command = LoginCommand(email=email, password=password)
    bus = get_bus()
    tokens = bus.handle(command)

    return jsonify({
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_in": tokens.expires_in,
        "token_type": tokens.token_type,
    })


@auth_bp.route("/refresh", methods=["POST"])
def refresh() -> tuple:
    """Refresh access token."""
    data = request.get_json() or {}
    refresh_token = data.get("refresh_token", "")

    if not refresh_token:
        raise BadRequest("Refresh token is required")

    command = RefreshTokenCommand(refresh_token=refresh_token)
    bus = get_bus()
    tokens = bus.handle(command)

    return jsonify({
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_in": tokens.expires_in,
        "token_type": tokens.token_type,
    })


@auth_bp.route("/me", methods=["GET"])
def me() -> tuple:
    """Get current user profile."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise Unauthorized("Missing or invalid Authorization header")

    access_token = auth_header[7:]
    bus = get_bus()

    # Decode token to get user_id
    from backend.src.identity.service import JwtService
    from backend.src.shared.config import get_settings

    settings = get_settings()
    jwt_service = JwtService()
    try:
        user_id, _ = jwt_service.verify_access_token(access_token)
    except ValueError as e:
        raise Unauthorized(str(e))

    command = GetProfileCommand(user_id=user_id)
    user = bus.handle(command)

    return jsonify({
        "id": str(user.id),
        "email": user.email,
        "roles": [r.value for r in user.roles],
        "created_at": user.created_at.isoformat(),
        "is_writer": user.is_writer(),
        "is_reader": user.is_reader(),
    })