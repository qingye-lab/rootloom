---
name: project-memory
description: Initialize, retrieve, and explicitly update the separate Rootloom Memory plugin's repository-owned architecture, risk, decision, and failure lessons. Use only when explicitly requested. Memory is experimental, advisory, and outside Rootloom Core.
---

# Rootloom Memory

Keep a small, local, reviewable memory in `.project-memory/`. This Skill is shipped by
the separately installed `rootloom-memory` plugin, never by Rootloom Core. It is an
experimental engineering aid, not an authority, prerequisite, or automatic activity log.

## Rules

- Query memory at task intake by the paths and intent actually in scope; do not inject the whole project history when only a few entries are relevant.
- Treat every result as a lead. Verify it against current source, tests, schemas, manifests, CI, and runtime evidence.
- Record only durable facts or explicitly labeled hypotheses that will change a future engineering decision. Do not copy task transcripts, model reasoning, raw logs, credentials, or sensitive payloads.
- Attach compact evidence references when practical. Prefer current repository paths, test names, issue/trace references, or accepted decision records over pasted evidence.
- Never initialize, record, resolve, supersede, or refresh memory silently. Every write is an explicit command followed by diff review.
- Keep accepted architecture and contract decisions in the repository's durable
  decision-record convention; `decisions.json` is only a relevant index. Maintain
  stable ownership and dependency rules in `architecture.md` with current evidence links.

## Initialize

```bash
python3 <skill-dir>/scripts/project_memory.py --repo /path/to/repo init
```

This creates the compatible `rootloom-project-memory-v1` files only when absent:

```text
.project-memory/
├── README.md
├── architecture.md
├── known-risks.json
├── decisions.json
└── failures.json
```

## Retrieve relevant context

Use repeatable paths plus the task intent. Context is read-only, bounded, and excludes expired, resolved, or superseded entries by default:

```bash
python3 <skill-dir>/scripts/project_memory.py --repo /path/to/repo context \
  --path src/relay.py \
  --query 'fix reconnect ordering' \
  --limit 8
```

The result keeps `architecture`, `failures`, `risks`, and `decisions` as direct fields for compatibility. `selection` explains the query/truncation, while `stale` names matching historical entries that must not silently influence the current decision. Use `--include-stale` only when investigating history.

## Record verified lessons

Failure lesson:

```bash
python3 <skill-dir>/scripts/project_memory.py --repo /path/to/repo record-failure \
  --summary 'Relay reconnect failed' \
  --root-cause 'Connection state transition race' \
  --fix 'Serialize transitions in the connection state machine' \
  --path src/relay.py \
  --evidence tests/test_relay.py::test_reconnect
```

Known risk:

```bash
python3 <skill-dir>/scripts/project_memory.py --repo /path/to/repo record-risk \
  --summary 'Relay reconnect ordering is fragile' \
  --mitigation 'Exercise repeated and cancelled transitions' \
  --path src/relay.py \
  --evidence docs/decisions/relay-lifecycle.md \
  --expires 2027-01-01
```

Decision index:

```bash
python3 <skill-dir>/scripts/project_memory.py --repo /path/to/repo record-decision \
  --summary 'All worker calls cross the relay boundary' \
  --record docs/decisions/relay-boundary.md \
  --path src/relay.py
```

New entries receive a deterministic ID, active status, evidence/path metadata, and optional expiry. Repeating the exact record reports `deduplicated: true` and does not grow the collection.

## Resolve or supersede

Lifecycle changes are explicit and preserve history:

```bash
python3 <skill-dir>/scripts/project_memory.py --repo /path/to/repo set-status \
  --kind risks \
  --id risk-0123456789abcdef \
  --status resolved
```

Use `--status superseded --superseded-by <new-id>` when another entry replaces the old one. Inspect the resulting JSON diff before accepting it.

## Compatibility and limits

- Existing v1 envelopes and legacy entries without ID, status, paths, evidence, or expiry remain readable and are never rewritten by `context`.
- Collections are bounded to 1 MiB and 1,000 entries; architecture context is bounded to 64 KiB; query output defaults to 20 entries per kind and accepts 1–100.
- Memory paths must be normalized repository-relative paths. Symlinked memory directories/files are refused or ignored to keep repository memory inside its owning boundary.
- No database, vector index, embeddings, daemon, Hook write, or network service is involved.
