# Paperlet

Substack-style platform connecting Readers and Writers with a global subscription model, allocation slots, and paywalled content.

## Language

**Writer**:
A user who creates and publishes newsletters/posts. Has capability to write.
_Avoid_: Author, creator, publisher

**Reader**:
A user who subscribes to writers and consumes content. Has capability to read subscriber content via allocation slots.
_Avoid_: Subscriber, follower, consumer

**Allocation Slot**:
One of 5 positions in a reader's active subscription that can be assigned to a writer, granting access to that writer's subscriber content.
_Avoid_: Slot, seat, position

**Change Credit**:
A monthly budget (2 per billing cycle) allowing a reader to swap or remove an existing writer allocation. Filling an empty slot consumes 0 credits.
_Avoid_: Swap credit, change budget, token

**Preview Content**:
The publicly accessible portion of a post, visible to all users regardless of subscription status.
_Avoid_: Teaser, excerpt, public content

**Subscriber Content**:
The paywalled portion of a post, visible only to readers with an active allocation to the post's writer.
_Avoid_: Premium content, paid content, full content

**Billing Cycle**:
The monthly period anchored to a reader's subscription start date, governing change credit reset and payment renewal.
_Avoid_: Month, period, cycle

**Post**:
A published newsletter consisting of title, preview_content, subscriber_content, and optional scheduled_for timestamp.
_Avoid_: Newsletter, article, publication

---

## Architecture Decisions (Glossary Extensions)

**User (Aggregate)**:
Identity aggregate containing credentials, JWT session management, and Reader/Writer capabilities derived from state (has subscription / has newsletter). Not separate Reader/Writer aggregates. Roles are inferred from activity, never chosen at signup: `POST /register` takes email + password plus optional profile fields (first/last name, avatar URL); a client-sent `role` is ignored; creating a first post grants WRITER, subscribing or allocating/following a writer grants READER.

**Subscription (Aggregate)**:
Owns allocation slots (max 5) and change credits (2 per billing cycle). Anchored to subscription start date for credit reset. Enforces unique writer per subscription.

**Post (Aggregate)**:
Owns preview_content and subscriber_content. Status machine: draft → scheduled → published. Soft-delete for scheduled posts (status=cancelled).

**Allocation Log**:
Domain event (immutable) + projected SQL table for admin/debug queries. Records allocate/swap/release with credits spent.

**JWT Access Token**:
15 min TTL, claims: `sub` (user_id), `sid` (session_id). No capability claim — reader/writer derived from state. No revocation check per request.

**JWT Refresh Token**:
30 days TTL, stored hashed in `sessions` table with `session_id`, rotated on every use. Enables revocation and theft detection.

**Session**:
Table: `id`, `user_id`, `refresh_token_hash`, `expires_at`, `revoked_at`, `user_agent`, `ip`. Source of truth for refresh token validity.

**PaymentGatewayAdapter (Interface)**:
Methods: `create_subscription`, `cancel_subscription`, `handle_webhook`, `get_subscription_status`. Mock implementation for v1, Stripe-ready.

**Subscription State**:
Owned by Payments context (`active`, `past_due`, `canceled`). Identity reads via read model projection.

**NotificationSender (Interface)**:
`send_batch(recipients, template, ctx) → list[SendResult]`. Single Celery task branches on `has_allocation` flag. Exponential backoff retry (1m, 5m, 15m, 1h, 6h, max 5).

**PostPublished Event**:
Carries `post_id` only. Worker fetches full post via repository/UoW. Avoids message bloat.

**API Versioning**:
URL path `/api/v1/` (per PROMPT). RFC 7807 hybrid error envelope with custom `code` enum.

**Pagination**:
Cursor-based default (`next_cursor`) for reader feed; offset/limit (`page`, `per_page`) opt-in for writer dashboard.

**Testing**:
- Unit: pure domain only (`tests/unit/domain/`)
- Adapters: SQLite in-memory (`tests/unit/adapters/`)
- Integration: PostgreSQL test DB, function-scoped transaction rollback
- E2E: Service layer for rules + Flask client for auth/paywall integration

**Migrations**:
Alembic autogenerate (`alembic revision --autogenerate`), reviewed. Seed script: `python -m scripts.seed_dev` (idempotent).

**Read Models**:
Event-driven projection tables updated via domain event handlers. Not materialized views.

**Health Checks**:
`GET /health` (liveness), `GET /health/ready` (readiness — DB, Redis, migrations).

**Logging**:
JSON structured logs with `request_id`, `user_id`, `trace_id` (W3C TraceContext).

**Rate Limiting**:
Defense in depth: ingress (Nginx/Traefik) for DDoS + Flask-Limiter on `/api/*` per-IP and per-user (JWT `sub`).

**Email Batch Size**:
Fixed config `BATCH_SIZE = 100` (ADR pending — reevaluate at real provider integration).