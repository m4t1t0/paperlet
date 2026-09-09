# ADR 0001: Cosmic Python on Flask + PostgreSQL

Status: accepted

## Context

`PROMPT.md` requires a Flask backend with DDD, Hexagonal architecture, Unit of
Work, Repository pattern, and CQRS, plus stateless JWT auth and an API-only v1
(Vue SPA deferred). The team needs one documented way to structure bounded
contexts (`identity`, `subscriptions`, `publishing`, `notifications`, `shared`).

## Decision

- Flask 3.x with REST APIs under `/api/v1/`.
- SQLAlchemy 2.0 **imperative mapping** (domain models stay pure Python; mapping
  lives in `adapters/orm.py`), PostgreSQL in production.
- Repository ABCs in `adapters/repository.py` + SQLAlchemy implementations.
- Unit of Work context manager + command/event message bus (`shared/`).
- CQRS read models as event-driven projection tables (not materialized views).
- Stateless JWT: 15 min access (`sub`, `sid`), 30 day rotating hashed refresh
  in a `sessions` table.
- Alembic autogenerate for migrations (reviewed before apply);
  seed script `python -m scripts.seed_dev` (idempotent).

## Consequences

- Domain stays DB-free, but repositories must translate persistence concerns
  (e.g. User roles set <-> JSON column) without leaking ORM into the domain.
- Projections must be registered on the bus or written explicitly by handlers;
  silent event loss (no publisher) is a known failure mode to guard against.
- SQLite is test/dev bootstrap only; Postgres semantics (e.g. upserts) must be
  gated or avoided in shared code paths.
