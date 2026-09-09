# ADR 0004: Stub Email Log in v1, Provider Interface Ready

Status: accepted

## Context

`PROMPT.md` wants `PostPublished` → Celery + Redis worker → batched email
(full post to allocated readers, preview + upsell to the rest). Running a real
provider (Mailchimp later) is out of v1 scope.

## Decision

- `NotificationSender` interface: `send_batch(recipients, template, ctx)`.
- Single Celery email task `send_post_published_emails(post_id)`; the worker
  fetches the full post via repository/UoW (`PostPublished` carries `post_id`
  only) and branches per recipient on the `has_allocation` flag.
- Explicit retry schedule 1m, 5m, 15m, 1h, 6h (max 5 retries).
- v1 sender is `StubEmailSender` (structured log, `BATCH_SIZE = 100` fixed
  config, reevaluate at provider integration); `process_scheduled_posts` is
  strictly a beat scheduler that publishes due posts and enqueues the one
  email task.

## Consequences

- No real emails in v1; `sent_emails` log is the observable output for tests.
- Mailchimp integration later implements `NotificationSender`, no task rewrite.
