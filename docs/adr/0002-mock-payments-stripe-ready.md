# ADR 0002: Mock Payments Now, Stripe-Ready Interface

Status: accepted

## Context

`PROMPT.md` requires a `PaymentGatewayAdapter(ABC)` with a mock implementation
for v1 and an easy path to `StripePaymentGateway` consuming Stripe webhooks
(`customer.subscription.created`, `invoice.payment_succeeded`).

## Decision

- `PaymentGatewayAdapter` in `adapters/payments.py` with `create_subscription`
  (`customer_id`, opaque string `price_id`, `payment_method_id`),
  `cancel_subscription`, `get_subscription_status`, `handle_webhook`.
- `MockPaymentGateway` simulates lifecycle locally and emits Stripe-canonical
  event names (`customer.subscription.updated/deleted`, `invoice.*`); the
  service layer also accepts legacy mock aliases.
- `SubscriptionService` maps config (`SUBSCRIPTION_PRICE_ID`, default
  `price_monthly_eur_995`; amount `SUBSCRIPTION_MONTHLY_PRICE_EUR` stays for
  display) to the gateway; never passes float amounts as price IDs.
- Public, unauthenticated `POST /api/v1/subscriptions/webhook` accepts both
  internal `{event_type, payload}` and Stripe `{type, data}` shapes and
  dispatches `HandlePaymentWebhookCommand`.

## Consequences

- Stripe integration later means adding one adapter + webhook secret
  verification, no service-layer rewrite.
- `price_id` is always a string; tests use `price_monthly_eur_995`.
