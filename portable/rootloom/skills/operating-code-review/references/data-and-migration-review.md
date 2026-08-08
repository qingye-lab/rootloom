# Data and migration review

Inspect old/new application coexistence, expand/migrate/contract ordering, backups,
transactions, locks, timeouts, retries, idempotency, re-entrancy, partial failure,
volume, online migration, backfill verification, and rollback or compensating repair.

Flag destructive contraction in the same rollout unless explicitly justified. Verify
old readers against new data, new readers against old data, interrupted/repeated
migration, and the gate that allows removal of the legacy path.
