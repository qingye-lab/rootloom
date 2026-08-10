# Data and migration review

First establish whether stored artifacts are authoritative or irreplaceable and whether
the new runtime must encounter old instances. Versioned but regenerable internal records
use the current contract only; rollback restores the complete old release and historical
replay uses its matching runtime. Neither operation alone requires mixed-version support.

When real post-cutover consumers exist, inspect old/new application coexistence,
expand/migrate/contract ordering, backups,
transactions, locks, timeouts, retries, idempotency, re-entrancy, partial failure,
volume, online migration, backfill verification, and rollback or compensating repair.

Flag destructive contraction in the same rollout unless explicitly justified. Do not
request an old reader, adapter, dual path, flag, or migration without that consumer
evidence. Where compatibility applies, verify
old readers against new data, new readers against old data, interrupted/repeated
migration, and the gate that allows removal of the legacy path.
