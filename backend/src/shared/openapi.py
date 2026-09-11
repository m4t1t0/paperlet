"""OpenAPI 3.0 spec builder for the Paperlet API.

Single source of truth for `docs/openapi.yaml` (see `scripts/generate_openapi.py`
and `invoke openapi`):

* Paths/methods are discovered from the Flask app's own `url_map`, so a new
  endpoint can never silently miss the spec.
* Per-endpoint metadata (summaries, params, bodies, responses) lives in the
  `PATHS` table below. Generation FAILS on any `/api/*` or `/health*` route
  without metadata — document new endpoints here first.

Regenerate after any API change: `invoke openapi` (or `--check` to verify).
"""

from __future__ import annotations

import re
from typing import Any

SPEC_TITLE = "Paperlet API"
SPEC_VERSION = "1.0.0"
OPENAPI_VERSION = "3.0.3"


# ---------------------------------------------------------------------------
# Small builders (all return plain JSON-compatible dicts)
# ---------------------------------------------------------------------------


def _ref(name: str) -> dict[str, Any]:
    return {"$ref": f"#/components/schemas/{name}"}


def _error_response(description: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {"application/json": {"schema": _ref("Error")}},
    }


def _json_response(description: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "description": description,
        "content": {"application/json": {"schema": schema}},
    }


def _param(
    name: str,
    *,
    location: str = "query",
    required: bool = False,
    schema: dict[str, Any] | None = None,
    description: str = "",
) -> dict[str, Any]:
    return {
        "name": name,
        "in": location,
        "required": required,
        "description": description,
        "schema": schema or {"type": "string"},
    }


def _uuid_param(name: str, description: str) -> dict[str, Any]:
    return _param(
        name,
        location="path",
        required=True,
        schema={"type": "string", "format": "uuid"},
        description=description,
    )


def _body(schema: dict[str, Any], *, required: bool = True) -> dict[str, Any]:
    return {
        "required": required,
        "content": {"application/json": {"schema": schema}},
    }


def _op(
    summary: str,
    *,
    tags: list[str],
    responses: dict[str, dict[str, Any]],
    auth: bool = True,
    description: str = "",
    parameters: list[dict[str, Any]] | None = None,
    request_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one operation; adds the 401 response for authed endpoints."""
    op: dict[str, Any] = {"summary": summary, "tags": tags}
    if description:
        op["description"] = description
    if parameters:
        op["parameters"] = parameters
    if request_body is not None:
        op["requestBody"] = request_body
    merged = dict(responses)
    if auth and "401" not in merged:
        merged["401"] = _error_response("Missing, invalid, or expired access token.")
    op["responses"] = merged
    if auth:
        op["security"] = [{"bearerAuth": []}]
    return op


# ---------------------------------------------------------------------------
# Reusable schemas (mirror the Flask response shapes)
# ---------------------------------------------------------------------------

_NULLABLE_STR = {"type": "string", "nullable": True}
_NULLABLE_UUID = {"type": "string", "format": "uuid", "nullable": True}
_NULLABLE_DATETIME = {"type": "string", "format": "date-time", "nullable": True}

SCHEMAS: dict[str, Any] = {
    "Error": {
        "type": "object",
        "required": ["title", "status", "detail", "message", "code"],
        "properties": {
            "title": {"type": "string", "example": "Unauthorized"},
            "status": {"type": "integer", "example": 401},
            "detail": {"type": "string"},
            "message": {"type": "string", "description": "Alias of detail."},
            "code": {"type": "string", "example": "UNAUTHORIZED"},
        },
    },
    "RegisterRequest": {
        "type": "object",
        "required": ["email", "password"],
        "properties": {
            "email": {"type": "string", "format": "email"},
            "password": {"type": "string", "format": "password"},
            "first_name": {"type": "string"},
            "last_name": {"type": "string"},
            "avatar_url": {"type": "string"},
        },
        "description": (
            "No role field: capabilities are inferred from activity. "
            "A client-sent `role`, if present, is ignored."
        ),
    },
    "RegisteredUser": {
        "type": "object",
        "required": ["id", "email", "created_at"],
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "email": {"type": "string"},
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
    "LoginRequest": {
        "type": "object",
        "required": ["email", "password"],
        "properties": {
            "email": {"type": "string", "format": "email"},
            "password": {"type": "string", "format": "password"},
        },
    },
    "TokenPair": {
        "type": "object",
        "required": ["access_token", "refresh_token", "expires_in", "token_type"],
        "properties": {
            "access_token": {"type": "string"},
            "refresh_token": {"type": "string"},
            "expires_in": {"type": "integer", "description": "Access TTL in seconds."},
            "token_type": {"type": "string", "example": "Bearer"},
        },
    },
    "RefreshRequest": {
        "type": "object",
        "required": ["refresh_token"],
        "properties": {"refresh_token": {"type": "string"}},
    },
    "Profile": {
        "type": "object",
        "required": [
            "id",
            "email",
            "display_name",
            "first_name",
            "last_name",
            "avatar_url",
            "created_at",
            "is_writer",
            "is_reader",
        ],
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "email": {"type": "string"},
            "display_name": {"type": "string"},
            "first_name": _NULLABLE_STR,
            "last_name": _NULLABLE_STR,
            "avatar_url": _NULLABLE_STR,
            "created_at": {"type": "string", "format": "date-time"},
            "is_writer": {"type": "boolean"},
            "is_reader": {"type": "boolean"},
        },
    },
    "PostView": {
        "type": "object",
        "description": (
            "Paywall-applied post. `subscriber_content` is null without an "
            "active allocation to the writer (or authorship)."
        ),
        "required": [
            "id",
            "writer_id",
            "title",
            "preview_content",
            "status",
            "published_at",
            "created_at",
            "subscriber_content",
            "has_full_access",
            "writer_name",
            "writer_avatar_url",
        ],
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "writer_id": {"type": "string", "format": "uuid"},
            "title": {"type": "string"},
            "preview_content": {"type": "string"},
            "status": {"type": "string", "example": "published"},
            "published_at": _NULLABLE_DATETIME,
            "created_at": {"type": "string", "format": "date-time"},
            "subscriber_content": _NULLABLE_STR,
            "has_full_access": {"type": "boolean"},
            "writer_name": _NULLABLE_STR,
            "writer_avatar_url": _NULLABLE_STR,
        },
    },
    "CreatePostRequest": {
        "type": "object",
        "required": ["title", "preview_content"],
        "properties": {
            "title": {"type": "string"},
            "preview_content": {"type": "string"},
            "subscriber_content": {"type": "string", "default": ""},
            "scheduled_at": {
                "type": "string",
                "format": "date-time",
                "description": "ISO 8601. When present the post is created scheduled.",
            },
        },
    },
    "CreatedPost": {
        "type": "object",
        "required": ["id", "title", "status", "scheduled_for", "created_at"],
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "title": {"type": "string"},
            "status": {"type": "string"},
            "scheduled_for": _NULLABLE_DATETIME,
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
    "PublishedPost": {
        "type": "object",
        "required": ["id", "title", "status", "published_at"],
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "title": {"type": "string"},
            "status": {"type": "string"},
            "published_at": _NULLABLE_DATETIME,
        },
    },
    "ScheduledPost": {
        "type": "object",
        "required": ["id", "title", "status", "scheduled_for"],
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "title": {"type": "string"},
            "status": {"type": "string"},
            "scheduled_for": _NULLABLE_DATETIME,
        },
    },
    "CancelledPost": {
        "type": "object",
        "required": ["id", "title", "status"],
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "title": {"type": "string"},
            "status": {"type": "string"},
        },
    },
    "UpdatedPost": {
        "type": "object",
        "required": ["id", "title", "status", "updated_at"],
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "title": {"type": "string"},
            "status": {"type": "string"},
            "updated_at": {"type": "string", "format": "date-time"},
        },
    },
    "UpdatePostRequest": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "preview_content": {"type": "string"},
            "subscriber_content": {"type": "string"},
        },
    },
    "Feed": {
        "type": "object",
        "required": ["posts", "next_cursor"],
        "properties": {
            "posts": {"type": "array", "items": _ref("PostView")},
            "next_cursor": _NULLABLE_STR,
        },
    },
    "RecentPosts": {
        "type": "object",
        "description": "Latest published posts, always preview-masked (public).",
        "required": ["posts"],
        "properties": {"posts": {"type": "array", "items": _ref("PostView")}},
    },
    "WriterPost": {
        "type": "object",
        "description": "Full post for the owning writer (no paywall masking).",
        "required": [
            "id",
            "title",
            "status",
            "preview_content",
            "subscriber_content",
            "scheduled_for",
            "published_at",
            "created_at",
        ],
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "title": {"type": "string"},
            "status": {"type": "string"},
            "preview_content": {"type": "string"},
            "subscriber_content": {"type": "string"},
            "scheduled_for": _NULLABLE_DATETIME,
            "published_at": _NULLABLE_DATETIME,
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
    "WriterPosts": {
        "type": "object",
        "required": ["posts"],
        "properties": {"posts": {"type": "array", "items": _ref("WriterPost")}},
    },
    "WriterSummary": {
        "type": "object",
        "required": [
            "id",
            "email",
            "display_name",
            "first_name",
            "last_name",
            "avatar_url",
            "created_at",
        ],
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "email": {"type": "string"},
            "display_name": {"type": "string"},
            "first_name": _NULLABLE_STR,
            "last_name": _NULLABLE_STR,
            "avatar_url": _NULLABLE_STR,
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
    "WritersList": {
        "type": "object",
        "required": ["writers", "total"],
        "properties": {
            "writers": {"type": "array", "items": _ref("WriterSummary")},
            "total": {"type": "integer"},
        },
    },
    "WriterDetail": {
        "type": "object",
        "required": [
            "id",
            "email",
            "display_name",
            "first_name",
            "last_name",
            "avatar_url",
            "created_at",
            "subscriber_post_count",
            "posts",
        ],
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "email": {"type": "string"},
            "display_name": {"type": "string"},
            "first_name": _NULLABLE_STR,
            "last_name": _NULLABLE_STR,
            "avatar_url": _NULLABLE_STR,
            "created_at": {"type": "string", "format": "date-time"},
            "subscriber_post_count": {"type": "integer"},
            "posts": {"type": "array", "items": _ref("PostView")},
        },
    },
    "AllocationEntry": {
        "type": "object",
        "required": ["writer_id", "allocated_at"],
        "properties": {
            "writer_id": {
                **_NULLABLE_UUID,
                "description": "Null for an empty slot.",
            },
            "allocated_at": _NULLABLE_DATETIME,
        },
    },
    "AllocationSummary": {
        "type": "object",
        "description": (
            "Reader subscription state. When no subscription exists, "
            "`subscription_id`/`billing_cycle_start` are null and status is `none`."
        ),
        "required": [
            "subscription_id",
            "status",
            "billing_cycle_start",
            "change_credits_remaining",
            "change_credits_per_cycle",
            "total_slots",
            "allocated_slots",
            "empty_slots",
            "allocations",
        ],
        "properties": {
            "subscription_id": _NULLABLE_UUID,
            "status": {"type": "string", "example": "active"},
            "billing_cycle_start": _NULLABLE_DATETIME,
            "change_credits_remaining": {"type": "integer"},
            "change_credits_per_cycle": {"type": "integer"},
            "total_slots": {"type": "integer", "example": 5},
            "allocated_slots": {"type": "integer"},
            "empty_slots": {"type": "integer"},
            "allocations": {"type": "array", "items": _ref("AllocationEntry")},
        },
    },
    "AllocationResult": {
        "type": "object",
        "required": ["success", "credits_spent", "allocations"],
        "properties": {
            "success": {"type": "boolean"},
            "credits_spent": {"type": "integer"},
            "allocations": {"type": "array", "items": _ref("AllocationEntry")},
        },
    },
    "SubscribeRequest": {
        "type": "object",
        "properties": {
            "payment_method_id": {"type": "string", "default": "pm_mock_default"}
        },
    },
    "AssignRequest": {
        "type": "object",
        "required": ["writer_id"],
        "properties": {"writer_id": {"type": "string", "format": "uuid"}},
    },
    "SwapRequest": {
        "type": "object",
        "required": ["current_writer_id", "new_writer_id"],
        "properties": {
            "current_writer_id": {"type": "string", "format": "uuid"},
            "new_writer_id": {"type": "string", "format": "uuid"},
        },
    },
    "WebhookRequest": {
        "type": "object",
        "description": (
            "Internal `{event_type, payload}` shape or Stripe `{type, data.object}` "
            "shape. Unknown subscription ids are accepted without effect."
        ),
    },
    "WebhookResult": {
        "type": "object",
        "required": ["received"],
        "properties": {"received": {"type": "boolean"}},
    },
    "Health": {
        "type": "object",
        "required": ["status"],
        "properties": {"status": {"type": "string", "example": "ok"}},
    },
    "Readiness": {
        "type": "object",
        "required": ["status", "checks"],
        "properties": {
            "status": {"type": "string", "example": "ready"},
            "checks": {
                "type": "object",
                "description": "database / redis / migrations, each {ok, detail}.",
            },
        },
    },
}

_AUTH_HEADER = _param(
    "Authorization",
    location="header",
    required=False,
    schema={"type": "string"},
    description=(
        "Optional `Bearer <access_token>`. Full content is returned when the "
        "reader has an active allocation to the writer."
    ),
)

_LIMIT_PARAM = _param(
    "limit",
    required=False,
    schema={"type": "integer", "default": 20},
    description="Max posts to return.",
)
_CURSOR_PARAM = _param(
    "cursor",
    required=False,
    schema={"type": "string"},
    description="Opaque pagination cursor (published_at of the last seen post).",
)

# ---------------------------------------------------------------------------
# Endpoint metadata: (path, methods) matched against the live url_map.
# ---------------------------------------------------------------------------

PATHS: list[dict[str, Any]] = [
    {
        "path": "/api/v1/auth/register",
        "methods": ["POST"],
        "op": _op(
            "Register a new user",
            tags=["Identity"],
            auth=False,
            description=(
                "Email + password only. Reader/Writer capabilities are inferred "
                "from activity, never chosen at signup."
            ),
            request_body=_body(_ref("RegisterRequest")),
            responses={
                "201": _json_response("User registered.", _ref("RegisteredUser")),
                "400": _error_response("Email and password are required."),
            },
        ),
    },
    {
        "path": "/api/v1/auth/login",
        "methods": ["POST"],
        "op": _op(
            "Login and get tokens",
            tags=["Identity"],
            auth=False,
            request_body=_body(_ref("LoginRequest")),
            responses={
                "200": _json_response("Access + refresh token pair.", _ref("TokenPair")),
                "400": _error_response("Email and password are required."),
                "401": _error_response("Invalid credentials or deactivated account."),
            },
        ),
    },
    {
        "path": "/api/v1/auth/refresh",
        "methods": ["POST"],
        "op": _op(
            "Refresh access token",
            tags=["Identity"],
            auth=False,
            description="Rotates the refresh token on every use.",
            request_body=_body(_ref("RefreshRequest")),
            responses={
                "200": _json_response("New token pair.", _ref("TokenPair")),
                "400": _error_response("Refresh token is required."),
                "401": _error_response("Invalid, expired, or revoked refresh token."),
            },
        ),
    },
    {
        "path": "/api/v1/auth/me",
        "methods": ["GET"],
        "op": _op(
            "Get current user profile",
            tags=["Identity"],
            responses={"200": _json_response("Profile with capabilities.", _ref("Profile"))},
        ),
    },
    {
        "path": "/api/v1/writers",
        "methods": ["GET"],
        "op": _op(
            "Searchable list of public writers",
            tags=["Writers"],
            auth=False,
            parameters=[
                _param("q", required=False, description="Case-insensitive email filter."),
                _param(
                    "limit",
                    required=False,
                    schema={"type": "integer", "default": 20},
                    description="Max writers to return.",
                ),
                _param(
                    "offset",
                    required=False,
                    schema={"type": "integer", "default": 0},
                    description="Writers to skip.",
                ),
            ],
            responses={"200": _json_response("Writer catalog page.", _ref("WritersList"))},
        ),
    },
    {
        "path": "/api/v1/writers/{writer_id}",
        "methods": ["GET"],
        "op": _op(
            "Writer profile and published newsletters",
            tags=["Writers"],
            auth=False,
            description="Posts are paywall-masked for readers without an allocation.",
            parameters=[
                _uuid_param("writer_id", "Writer id."),
                _AUTH_HEADER,
            ],
            responses={
                "200": _json_response("Writer with masked posts.", _ref("WriterDetail")),
                "400": _error_response("Invalid writer_id format."),
                "404": _error_response("Writer not found."),
            },
        ),
    },
    {
        "path": "/api/v1/subscriptions/subscribe",
        "methods": ["POST"],
        "op": _op(
            "Create a subscription",
            tags=["Subscriptions"],
            description=(
                "Starts the monthly subscription via the payment gateway and "
                "grants the READER capability."
            ),
            request_body=_body(_ref("SubscribeRequest"), required=False),
            responses={
                "201": _json_response("Allocation summary.", _ref("AllocationSummary")),
            },
        ),
    },
    {
        "path": "/api/v1/subscriptions/allocations",
        "methods": ["GET"],
        "op": _op(
            "Get allocations and change credits",
            tags=["Subscriptions"],
            responses={
                "200": _json_response("Allocation summary.", _ref("AllocationSummary")),
            },
        ),
    },
    {
        "path": "/api/v1/subscriptions/allocations/assign",
        "methods": ["POST"],
        "op": _op(
            "Assign a writer to an empty slot",
            tags=["Subscriptions"],
            description="Filling an empty slot consumes 0 change credits.",
            request_body=_body(_ref("AssignRequest")),
            responses={
                "200": _json_response("Updated allocations.", _ref("AllocationResult")),
                "400": _error_response("Missing/invalid writer_id or no subscription."),
            },
        ),
    },
    {
        "path": "/api/v1/subscriptions/allocations/swap",
        "methods": ["POST"],
        "op": _op(
            "Swap one writer for another",
            tags=["Subscriptions"],
            description="Consumes 1 change credit; rejected at 0 remaining credits.",
            request_body=_body(_ref("SwapRequest")),
            responses={
                "200": _json_response("Updated allocations.", _ref("AllocationResult")),
                "400": _error_response("Missing ids, no subscription, or no credits."),
            },
        ),
    },
    {
        "path": "/api/v1/subscriptions/allocations/{writer_id}",
        "methods": ["DELETE"],
        "op": _op(
            "Release a writer slot",
            tags=["Subscriptions"],
            description="Consumes 1 change credit.",
            parameters=[_uuid_param("writer_id", "Allocated writer to release.")],
            responses={
                "200": _json_response("Updated allocations.", _ref("AllocationResult")),
                "400": _error_response("Invalid id, no subscription, or no credits."),
            },
        ),
    },
    {
        "path": "/api/v1/subscriptions/webhook",
        "methods": ["POST"],
        "op": _op(
            "Payment gateway webhook",
            tags=["Subscriptions"],
            auth=False,
            description="Public, Stripe-ready. No auth.",
            request_body=_body({"$ref": "#/components/schemas/WebhookRequest"}),
            responses={
                "200": _json_response("Event accepted.", _ref("WebhookResult")),
                "400": _error_response("event_type is required."),
            },
        ),
    },
    {
        "path": "/api/v1/posts",
        "methods": ["POST"],
        "op": _op(
            "Create a draft or scheduled post",
            tags=["Publishing"],
            description=(
                "Any authenticated user may create a first post — doing so "
                "grants the WRITER capability."
            ),
            request_body=_body(_ref("CreatePostRequest")),
            responses={
                "201": _json_response("Post created.", _ref("CreatedPost")),
                "400": _error_response("Missing title/preview or bad scheduled_at."),
            },
        ),
    },
    {
        "path": "/api/v1/posts/{post_id}/publish",
        "methods": ["POST"],
        "op": _op(
            "Publish a post immediately",
            tags=["Publishing"],
            parameters=[_uuid_param("post_id", "Draft post id.")],
            responses={
                "200": _json_response("Published post.", _ref("PublishedPost")),
                "400": _error_response("Invalid post_id format."),
            },
        ),
    },
    {
        "path": "/api/v1/posts/{post_id}/schedule",
        "methods": ["POST"],
        "op": _op(
            "Schedule a draft post",
            tags=["Publishing"],
            parameters=[_uuid_param("post_id", "Draft post id.")],
            request_body=_body(
                {
                    "type": "object",
                    "required": ["scheduled_at"],
                    "properties": {
                        "scheduled_at": {
                            "type": "string",
                            "format": "date-time",
                        }
                    },
                }
            ),
            responses={
                "200": _json_response("Scheduled post.", _ref("ScheduledPost")),
                "400": _error_response("Missing/invalid scheduled_at or post_id."),
            },
        ),
    },
    {
        "path": "/api/v1/posts/{post_id}",
        "methods": ["DELETE"],
        "op": _op(
            "Cancel a scheduled post",
            tags=["Publishing"],
            parameters=[_uuid_param("post_id", "Scheduled post id.")],
            responses={
                "200": _json_response("Cancelled post.", _ref("CancelledPost")),
                "400": _error_response("Invalid post_id format."),
            },
        ),
    },
    {
        "path": "/api/v1/posts/{post_id}",
        "methods": ["PATCH"],
        "op": _op(
            "Update post content",
            tags=["Publishing"],
            parameters=[_uuid_param("post_id", "Post id.")],
            request_body=_body(_ref("UpdatePostRequest"), required=False),
            responses={
                "200": _json_response("Updated post.", _ref("UpdatedPost")),
                "400": _error_response("Invalid post_id format."),
            },
        ),
    },
    {
        "path": "/api/v1/posts/{post_id}",
        "methods": ["GET"],
        "op": _op(
            "Get a single post with paywall logic",
            tags=["Publishing"],
            auth=False,
            description="Public preview; no auth required.",
            parameters=[
                _uuid_param("post_id", "Post id."),
                _AUTH_HEADER,
            ],
            responses={
                "200": _json_response("Paywall-applied post.", _ref("PostView")),
                "400": _error_response("Invalid post_id format."),
                "404": _error_response("Post not found."),
            },
        ),
    },
    {
        "path": "/api/v1/posts/recent",
        "methods": ["GET"],
        "op": _op(
            "Latest published posts",
            tags=["Publishing"],
            auth=False,
            description="Public homepage feed, always preview-masked.",
            parameters=[
                _param(
                    "limit",
                    required=False,
                    schema={"type": "integer", "default": 10, "maximum": 50},
                    description="Max posts to return.",
                ),
            ],
            responses={
                "200": _json_response("Recent posts.", _ref("RecentPosts")),
            },
        ),
    },
    {
        "path": "/api/v1/posts/feed",
        "methods": ["GET"],
        "op": _op(
            "Reader feed from allocated writers",
            tags=["Publishing"],
            description="Empty without an active subscription/allocation (archival included).",
            parameters=[_LIMIT_PARAM, _CURSOR_PARAM],
            responses={"200": _json_response("Feed page.", _ref("Feed"))},
        ),
    },
    {
        "path": "/api/v1/posts/writer",
        "methods": ["GET"],
        "op": _op(
            "Current writer's posts",
            tags=["Publishing"],
            parameters=[
                _param(
                    "status",
                    required=False,
                    schema={
                        "type": "string",
                        "enum": ["draft", "scheduled", "published", "cancelled"],
                    },
                    description="Filter by status.",
                ),
            ],
            responses={"200": _json_response("Own posts, unmasked.", _ref("WriterPosts"))},
        ),
    },
    {
        "path": "/health",
        "methods": ["GET"],
        "op": _op(
            "Liveness probe",
            tags=["Health"],
            auth=False,
            responses={"200": _json_response("Alive.", _ref("Health"))},
        ),
    },
    {
        "path": "/health/ready",
        "methods": ["GET"],
        "op": _op(
            "Readiness probe",
            tags=["Health"],
            auth=False,
            description="Checks database, Redis, and migrations. 503 when not ready.",
            responses={
                "200": _json_response("Ready.", _ref("Readiness")),
                "503": _json_response("Not ready.", _ref("Readiness")),
            },
        ),
    },
]


# ---------------------------------------------------------------------------
# Builder: merge live url_map with the metadata table (strict)
# ---------------------------------------------------------------------------

_FLASK_PARAM_RE = re.compile(r"<(?:[^<>:]+:)?([^<>]+)>")


def _flask_to_openapi_path(rule: str) -> str:
    """Convert Flask `<param>` converters to OpenAPI `{param}`."""
    return _FLASK_PARAM_RE.sub(r"{\1}", rule)


def _include_rule(rule: str) -> bool:
    return rule.startswith("/api/") or rule.startswith("/health")


def build_openapi_spec() -> dict[str, Any]:
    """Build the full OpenAPI document from the live Flask app."""
    from app import create_app

    app = create_app()
    indexed = {(p["path"], tuple(sorted(p["methods"]))): p for p in PATHS}
    paths: dict[str, Any] = {}
    for rule in app.url_map.iter_rules():
        if not _include_rule(rule.rule):
            continue
        methods = sorted(
            m for m in (rule.methods or set()) if m not in ("HEAD", "OPTIONS")
        )
        oapi_path = _flask_to_openapi_path(rule.rule)
        meta = indexed.get((oapi_path, tuple(methods)))
        if meta is None:
            raise RuntimeError(
                f"Undocumented API endpoint: {'|'.join(methods)} {rule.rule} — "
                "add metadata to PATHS in backend/src/shared/openapi.py, "
                "then run `invoke openapi`."
            )
        item = paths.setdefault(oapi_path, {})
        for method in methods:
            operation = dict(meta["op"])
            if not operation.get("responses"):
                raise RuntimeError(f"No responses documented for {method} {oapi_path}.")
            item[method.lower()] = operation
    return {
        "openapi": OPENAPI_VERSION,
        "info": {
            "title": SPEC_TITLE,
            "version": SPEC_VERSION,
            "description": (
                "Substack-style platform: readers subscribe to writers via "
                "allocation slots; posts are paywalled (preview + subscriber content)."
            ),
        },
        "servers": [{"url": "http://localhost:5000"}],
        "paths": paths,
        "components": {
            "schemas": SCHEMAS,
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "Access token from POST /api/v1/auth/login.",
                }
            },
        },
    }


def render_openapi_yaml(spec: dict[str, Any]) -> str:
    """Render the spec to YAML text with a generated-file header."""
    import yaml

    header = "# Generated by `invoke openapi` — do not edit by hand.\n"
    return header + yaml.safe_dump(
        spec, sort_keys=False, default_flow_style=False, allow_unicode=True
    )
