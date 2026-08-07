# Recover interrupted Personal setup transactions

- Status: accepted
- Date: 2026-08-07
- Owners: Rootloom maintainers
- Scope: `plugins/rootloom/skills/setup-rootloom/scripts/setup_rootloom.py`
- Supersedes: none
- Superseded by: none

## Context

Personal setup updates several Codex-home files and publishes `state.json` last. Per-file
atomic replacement and backups protected individual files, but a process stop between
target replacements could leave visible targets and recorded setup state out of sync.

## Evidence

| Claim | Kind | Source and environment | Observed | Reference | Freshness / redaction |
| --- | --- | --- | --- | --- | --- |
| Target replacement and state publication were sequential | fact | Rootloom source | 2026-08-07 | `setup_rootloom.py`, prior implementation | local source only |
| A fault injected after the first target replacement left no state but did leave the target changed | fact | Focused unit test | 2026-08-07 | `test_interrupted_apply_is_completed_from_transaction_journal` | temporary Codex home |
| The staged recovery path converges after interruption | fact | Focused unit test | 2026-08-07 | same test; `python3 -m unittest tests.test_setup_rootloom` | 18 tests passed |

## Decision

Before the first managed target write, setup creates the normal backup, stages every
replacement and removal plus the final setup state, and atomically publishes a
`rootloom-setup-transaction-v1` journal. Mutating setup and rollback operations recover
that exact staged transaction under the setup lock before doing new work. Recovery is
idempotent, preflights all targets, refuses post-interruption edits, verifies final hashes,
and removes the journal only after convergence. `status` reports the journal read-only.

The journal is an internal additive persisted format. Existing installations without a
journal remain readable; no migration is required. Hostile same-user replacement of the
lock or target paths remains outside the contract.

## Alternatives considered

- Keep the documented manual reconciliation path — rejected because the owning setup boundary can safely stage and replay its own small target set.
- Roll back automatically after interruption — deferred because completing the exact planned transaction preserves the user's selected setup intent and existing backup chain.
- Add a full filesystem transaction dependency — rejected because the local standard-library-only runtime contract does not require one.

## Consequences

- Positive: interrupted setup converges without manual file-by-file repair when targets are unchanged.
- Positive: staged bytes preserve the exact intended transaction even if the plugin source changes before recovery.
- Negative: each backup consumes additional local space for staged copies.
- Operational: a pending journal is visible through `status`; a target changed after interruption must be explicitly reconciled before recovery can continue.

## Verification

- Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_setup_rootloom`.
- Run `make check` and the repository validator.
- Inject a failure after the first target replacement and verify the next mutating setup resumes and removes `transaction.json` only after all final hashes converge.

## Revisit when

- Setup manages enough targets that staged backup size or recovery duration needs a bounded policy.
- Hostile same-user filesystem replacement becomes an explicit security requirement.
- The persisted setup state format or rollback semantics require an incompatible change.
