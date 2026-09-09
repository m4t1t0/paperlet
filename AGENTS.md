# Paperlet - Agent Instructions

Source of truth: `PROMPT.md` (Substack-style platform). This file is aligned to it.

## Run the App
```bash
source .venv/bin/activate
python app.py
```
Runs on http://localhost:5000

## Invoke Commands (Recommended)
```bash
source .venv/bin/activate
python -m invoke start      # Start server (waits until ready)
python -m invoke stop       # Stop server
python -m invoke restart    # Restart server
python -m invoke --list     # List all tasks
```

## Install Dependencies
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Project Structure
- `app.py` - Application factory with Flask app creation
- `tasks.py` - Invoke tasks for start/stop/restart
- `requirements.txt` - Dependencies (flask, invoke, requests, sqlalchemy, marshmallow, pydantic, redis, httpx, alembic, etc.)
- `PROMPT.md` - Product spec (authoritative)
- `CONTEXT.md` - Ubiquitous language glossary
- `docs/adr/` - Architecture Decision Records
- `backend/src/identity/` - Authentication & User Management (single User, Reader/Writer capabilities, JWT); `api_auth.py` shared Flask auth helpers; `writers_api.py` Writers Catalog (`GET /api/v1/writers`)
- `backend/src/subscriptions/` - Subscription, Allocation Slots (5), Change Credits (2), config-driven
- `backend/src/publishing/` - Posts with preview_content / subscriber_content, scheduled_for, archival access
- `backend/src/notifications/` - PostPublished handling, stub log v1 (Mailchimp later)
- `backend/src/shared/` - Base events, UoW, bus, config
- `backend/src/adapters/payments.py` - PaymentGatewayAdapter ABC + MockPaymentGateway (Stripe later)

## Notes
- Uses Python 3.14 (from .venv)
- Architecture: Cosmic Python (DDD + Hexagonal + UoW + Repository + CQRS) — see `docs/adr/0001-cosmic-python-flask-postgres.md`
- Database: PostgreSQL with SQLAlchemy 2.0 Imperative Mapping + Alembic migrations
- Auth: Stateless JWT (Access + Refresh)
- Scope v1: API-only (Vue SPA deferred)
- Economics configurable (price/slots/credits in config, not hardcoded); writers publish free; readers pay to read
- Payments: Mock now, Stripe-ready — see `docs/adr/0002-mock-payments-stripe-ready.md`
- No writer payouts v1, counts only — see `docs/adr/0003-no-payouts-v1.md`
- Email: stub log v1, provider interface for Mailchimp later — see `docs/adr/0004-no-email-v1-provider-ready.md`
- Testing: pytest with unit, integration, and e2e (Flask client paywall checks)
- Default port: 5000 (configurable via `invoke start --port=8080`)
- Debug mode off by default for background runs (use `--debug=true` to enable)
