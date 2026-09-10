"""Subscriptions API routes."""

from __future__ import annotations
from typing import Any, cast

from flask import Blueprint, Response, jsonify, request
from werkzeug.exceptions import BadRequest
from uuid import UUID

from backend.src.identity.api_auth import get_current_user
from backend.src.shared.domain.value_objects import ReaderId, WriterId
from backend.src.shared.service_layer.messagebus import MessageBus
from backend.src.subscriptions.commands import (
    AssignAllocationCommand,
    GetAllocationsCommand,
    HandlePaymentWebhookCommand,
    ReleaseAllocationCommand,
    SubscribeCommand,
    SwapAllocationCommand,
)

subscriptions_bp = Blueprint(
    "subscriptions", __name__, url_prefix="/api/v1/subscriptions"
)


def get_bus() -> MessageBus:
    """Get message bus from app context."""
    from flask import current_app

    return cast(MessageBus, getattr(current_app, "message_bus"))


@subscriptions_bp.route("/subscribe", methods=["POST"])
def subscribe() -> Response | tuple[Any, ...]:
    """Create a new subscription."""
    user = get_current_user()
    data = request.get_json() or {}
    payment_method_id = data.get("payment_method_id", "pm_mock_default")

    command = SubscribeCommand(
        reader_id=ReaderId(value=user["id"]), payment_method_id=payment_method_id
    )
    bus = get_bus()
    subscription = bus.handle(command)

    return jsonify(subscription.get_allocation_summary()), 201


@subscriptions_bp.route("/allocations", methods=["GET"])
def get_allocations() -> Response | tuple[Any, ...]:
    """Get current allocations and change credits."""
    user = get_current_user()

    command = GetAllocationsCommand(reader_id=ReaderId(value=user["id"]))
    bus = get_bus()
    summary = bus.handle(command)

    return jsonify(summary)


@subscriptions_bp.route("/allocations/assign", methods=["POST"])
def assign_allocation() -> Response | tuple[Any, ...]:
    """Assign a writer to an empty slot."""
    user = get_current_user()
    data = request.get_json() or {}
    writer_id_str = data.get("writer_id")

    if not writer_id_str:
        raise BadRequest("writer_id is required")

    try:
        writer_id = UUID(writer_id_str)
    except ValueError:
        raise BadRequest("Invalid writer_id format")

    command = AssignAllocationCommand(reader_id=ReaderId(value=user["id"]), writer_id=WriterId(value=writer_id))
    bus = get_bus()
    result = bus.handle(command)

    return jsonify(result)


@subscriptions_bp.route("/allocations/swap", methods=["POST"])
def swap_allocation() -> Response | tuple[Any, ...]:
    """Swap one writer for another."""
    user = get_current_user()
    data = request.get_json() or {}
    current_writer_id_str = data.get("current_writer_id")
    new_writer_id_str = data.get("new_writer_id")

    if not current_writer_id_str or not new_writer_id_str:
        raise BadRequest("current_writer_id and new_writer_id are required")

    try:
        current_writer_id = UUID(current_writer_id_str)
        new_writer_id = UUID(new_writer_id_str)
    except ValueError:
        raise BadRequest("Invalid writer_id format")

    command = SwapAllocationCommand(
        reader_id=ReaderId(value=user["id"]),
        current_writer_id=WriterId(value=current_writer_id),
        new_writer_id=WriterId(value=new_writer_id),
    )
    bus = get_bus()
    try:
        result = bus.handle(command)
    except ValueError as e:
        raise BadRequest(str(e))

    return jsonify(result)


@subscriptions_bp.route("/allocations/<writer_id>", methods=["DELETE"])
def release_allocation(writer_id: str) -> Response | tuple[Any, ...]:
    """Release a writer slot."""
    user = get_current_user()

    try:
        writer_uuid = UUID(writer_id)
    except ValueError:
        raise BadRequest("Invalid writer_id format")

    command = ReleaseAllocationCommand(reader_id=ReaderId(value=user["id"]), writer_id=WriterId(value=writer_uuid))
    bus = get_bus()
    try:
        result = bus.handle(command)
    except ValueError as e:
        raise BadRequest(str(e))

    return jsonify(result)


@subscriptions_bp.route("/webhook", methods=["POST"])
def payment_webhook() -> Response | tuple[Any, ...]:
    """Public payment gateway webhook (Stripe-ready, no auth)."""
    data = request.get_json() or {}
    # Support both internal {event_type, payload} and Stripe {type, data} shapes
    event_type = data.get("event_type") or data.get("type")
    payload = data.get("payload")
    if payload is None:
        stripe_data = data.get("data") or {}
        payload = stripe_data.get("object", {}) if isinstance(stripe_data, dict) else {}
    if not event_type:
        raise BadRequest("event_type is required")

    command = HandlePaymentWebhookCommand(event_type=event_type, payload=payload or {})
    bus = get_bus()
    bus.handle(command)
    return jsonify({"received": True})
