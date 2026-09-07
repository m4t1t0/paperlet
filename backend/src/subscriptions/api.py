"""Subscriptions API routes."""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from werkzeug.exceptions import BadRequest, NotFound, Unauthorized

from backend.src.identity.domain.model import User
from backend.src.identity.service import JwtService
from backend.src.shared.config import get_settings
from backend.src.shared.service_layer.messagebus import MessageBus
from backend.src.subscriptions.commands import (
    AssignAllocationCommand,
    GetAllocationsCommand,
    ReleaseAllocationCommand,
    SubscribeCommand,
    SwapAllocationCommand,
)
from backend.src.subscriptions.domain.model import SubscriptionStatus

subscriptions_bp = Blueprint("subscriptions", __name__, url_prefix="/api/v1/subscriptions")


def get_bus() -> MessageBus:
    """Get message bus from app context."""
    from flask import current_app
    return current_app.message_bus


def get_current_user() -> dict:
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
        return {"id": user.id}


@subscriptions_bp.route("/subscribe", methods=["POST"])
def subscribe() -> tuple:
    """Create a new subscription."""
    user = get_current_user()
    data = request.get_json() or {}
    payment_method_id = data.get("payment_method_id", "pm_mock_default")

    command = SubscribeCommand(reader_id=user["id"], payment_method_id=payment_method_id)
    bus = get_bus()
    subscription = bus.handle(command)

    return jsonify(subscription.get_allocation_summary()), 201


@subscriptions_bp.route("/allocations", methods=["GET"])
def get_allocations() -> tuple:
    """Get current allocations and change credits."""
    user = get_current_user()

    command = GetAllocationsCommand(reader_id=user["id"])
    bus = get_bus()
    summary = bus.handle(command)

    return jsonify(summary)


@subscriptions_bp.route("/allocations/assign", methods=["POST"])
def assign_allocation() -> tuple:
    """Assign a writer to an empty slot."""
    user = get_current_user()
    data = request.get_json() or {}
    writer_id_str = data.get("writer_id")

    if not writer_id_str:
        raise BadRequest("writer_id is required")

    from uuid import UUID
    try:
        writer_id = UUID(writer_id_str)
    except ValueError:
        raise BadRequest("Invalid writer_id format")

    command = AssignAllocationCommand(reader_id=user["id"], writer_id=writer_id)
    bus = get_bus()
    result = bus.handle(command)

    return jsonify(result)


@subscriptions_bp.route("/allocations/swap", methods=["POST"])
def swap_allocation() -> tuple:
    """Swap one writer for another."""
    user = get_current_user()
    data = request.get_json() or {}
    current_writer_id_str = data.get("current_writer_id")
    new_writer_id_str = data.get("new_writer_id")

    if not current_writer_id_str or not new_writer_id_str:
        raise BadRequest("current_writer_id and new_writer_id are required")

    from uuid import UUID
    try:
        current_writer_id = UUID(current_writer_id_str)
        new_writer_id = UUID(new_writer_id_str)
    except ValueError:
        raise BadRequest("Invalid writer_id format")

    command = SwapAllocationCommand(
        reader_id=user["id"],
        current_writer_id=current_writer_id,
        new_writer_id=new_writer_id,
    )
    bus = get_bus()
    try:
        result = bus.handle(command)
    except ValueError as e:
        raise BadRequest(str(e))

    return jsonify(result)


@subscriptions_bp.route("/allocations/<writer_id>", methods=["DELETE"])
def release_allocation(writer_id: str) -> tuple:
    """Release a writer slot."""
    user = get_current_user()

    from uuid import UUID
    try:
        writer_uuid = UUID(writer_id)
    except ValueError:
        raise BadRequest("Invalid writer_id format")

    command = ReleaseAllocationCommand(reader_id=user["id"], writer_id=writer_uuid)
    bus = get_bus()
    try:
        result = bus.handle(command)
    except ValueError as e:
        raise BadRequest(str(e))

    return jsonify(result)