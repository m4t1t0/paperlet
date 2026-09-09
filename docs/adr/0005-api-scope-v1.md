# ADR 0005: v1 API Scope (Lifecycle Extras Are Intentional)

Status: accepted

## Context

`PROMPT.md` lists a minimal endpoint core, but the writer dashboard, paywall
UI, and operations need a few more: post lifecycle (`publish`, `schedule`,
`cancel`, `update`, writer listing), a public writers catalog, public preview
reads, a payment webhook, and health probes. A spec review flagged these as
possible scope creep.

## Decision

Retain as intentional v1 scope (all covered by tests):

- Publishing lifecycle: `POST /posts/{id}/publish`, `POST /posts/{id}/schedule`,
  `DELETE /posts/{id}` (cancel), `PATCH /posts/{id}` (update),
  `GET /posts/writer` — required for draft → scheduled → published with
  soft-cancel semantics from `CONTEXT.md`.
- Writers catalog: `GET /api/v1/writers` (searchable) + `GET /{writer_id}`
  (profile + paywall-masked posts) — required by `PROMPT.md` writers section.
- Public reads: `GET /posts/{id}` without auth returns preview only
  (`PROMPT.md`: preview free to public); authenticated readers get subscriber
  content when allocated.
- Ops: `POST /api/v1/auth/refresh` (refresh rotation), public
  `POST /api/v1/subscriptions/webhook`, `GET /health` (liveness) +
  `GET /health/ready` (DB, Redis, migrations).
- Errors: RFC 7807 hybrid envelope (`type`/`title`/`status`/`detail` + custom
  `code`); `message` kept as alias of `detail` for backwards compatibility.
  Success payloads stay unwrapped resources.

## Consequences

- Endpoint additions that serve the listed dashboards/paywall/ops are features,
  not creep; genuinely new product surface needs a new ADR.
