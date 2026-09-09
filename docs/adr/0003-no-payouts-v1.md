# ADR 0003: No Writer Payouts in v1

Status: accepted

## Context

The v1 scope is reader subscriptions (€9.95/month global, 5 allocation slots,
2 change credits) and paywalled reading. Writer monetization (revenue share,
payouts, tax reporting) would add payments, ledger, and compliance complexity.

## Decision

- v1 tracks subscriber counts only (allocations per writer via read models);
  no money flows to writers, no payout ledger, no revenue-share calculation.
- Subscription state (`active`, `past_due`, `canceled`) is owned by the
  payments side; identity/publishing read it via projections.

## Consequences

- Writer dashboard shows subscriber-count metrics, not earnings.
- Any future payouts feature needs a new bounded context + ADR.
