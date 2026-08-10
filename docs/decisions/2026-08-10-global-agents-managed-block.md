# Merge global AGENTS.md through the Rootloom managed block

- Status: accepted
- Date: 2026-08-10
- Owners: Rootloom maintainers
- Scope: optional Codex-home setup writer
- Supersedes: none
- Superseded by: none

## Context

The optional setup copies global policy into `~/.codex/AGENTS.md`. Treating that path as
a whole-file target makes valid user guidance outside Rootloom's markers look like drift
and makes an upgrade plan propose replacing unrelated content.

## Evidence

| Claim | Kind | Source and environment | Observed | Reference | Freshness / redaction |
| --- | --- | --- | --- | --- | --- |
| A 4.2.1 installation with the exact managed block plus a user-owned server-profile suffix reported `AGENTS.md` as an update candidate | runtime observation | local Codex home | 2026-08-10 | `setup_rootloom.py status` before this change | current; hashes only |
| Replacing only the marked block yields the 4.2.1 policy while preserving the suffix byte-for-byte | runtime observation | local Codex home | 2026-08-10 | managed-block and suffix SHA-256 comparison | current; no credentials read |

## Decision

`setup_rootloom.py` owns only the single Rootloom-managed block in global `AGENTS.md`.
Install inserts that block before an existing unmarked file. Upgrade replaces only the
well-formed block. Drift detection hashes the block, while transactions and backups keep
the complete merged file for atomic recovery. Missing, duplicated, or malformed marker
pairs stop setup instead of falling back to whole-file replacement.

## Alternatives considered

- Keep whole-file ownership and require users to restore the template before upgrade — rejected because unrelated user guidance is not Rootloom drift.
- Overwrite the complete file after exact authorization — rejected because a valid managed boundary already identifies the narrower owning scope.
- Add a second global guidance file — rejected because Codex already defines the global `AGENTS.md` hierarchy and another file would add no authoritative boundary.

## Consequences

- Positive: install and upgrade preserve unrelated global guidance without compatibility adapters or parallel configuration paths.
- Negative: malformed markers require explicit manual repair.
- Operational: existing full-file state hashes remain readable for the upgrade that converts them to managed-block hashes; normal backups and rollback remain available.

## Verification

- `python3 -m unittest tests.test_setup_rootloom`
- `make check`

## Revisit when

- Codex introduces a native independently managed global policy file or marker-aware configuration API.
