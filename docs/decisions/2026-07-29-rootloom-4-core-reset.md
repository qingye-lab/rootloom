# Reset Rootloom 4 to four public entries

- Status: accepted
- Date: 2026-07-29
- Owners: Rootloom maintainers
- Scope: plugin public Skill surface, optional Evidence, Guidance, and Project Memory packaging
- Supersedes: [Reset Personal Core product boundaries](2026-07-16-personal-core-product-boundaries.md) where it deferred a 4.0 release and Memory separation
- Superseded by: none

## Context

Rootloom 3.4 exposed nine public Skills. Daily change, high-risk change, and the
evidence bundle were separate entries even though they shared diagnosis, scope,
verification, and completion semantics. Guidance similarly split deterministic seeding
from semantic refinement, while experimental Memory shipped in the main plugin despite
being explicitly optional and non-authoritative.

The public surface made internal assurance layers look like competing user workflows.
The stable product purpose is narrower: make code-change scope controllable, causes
explainable, verification inspectable, and completion claims honest.

## Evidence

| Claim | Kind | Source and environment | Observed | Reference | Freshness / redaction |
| --- | --- | --- | --- | --- | --- |
| Rootloom 3.4 exposes nine public Skills | fact | `v3.4.0` repository tag | 2026-07-29 | `plugins/rootloom/skills/*/SKILL.md` | Immutable Git tag; no sensitive data |
| The 3.4 Change, High-risk, and Evidence Skills repeat diagnosis, scope, verification, and report rules | fact | `v3.4.0` Skill text | 2026-07-29 | `operating-coding-change`, `operating-high-risk-change`, `engineering-change` | Immutable Git tag |
| Seeder and Refiner modify different sections of the same `AGENTS.md` contract | fact | current repository | 2026-07-29 | `plugins/rootloom/skills/project-guidance/` | Local source |
| Project Memory is explicit, advisory, and not an ordinary-task prerequisite | fact | existing product decision and tests | 2026-07-29 | [Personal Core boundaries](2026-07-16-personal-core-product-boundaries.md), `tests/test_project_memory.py` | Current repository |
| The 4.0 candidate passes the 30-cell comparative gate, with a thin elapsed-time margin | measured fact | isolated No Rootloom / 3.4 / 4.0 runs using `gpt-5.6-sol`, `xhigh`, Codex CLI `0.146.0-alpha.3.1` | 2026-07-29 | [`evals/core-reset/results-2026-07-29.json`](../../evals/core-reset/results-2026-07-29.json) | Sanitized scores and transcript hashes retained; raw transcripts remain local |

## Decision

Rootloom Core exposes exactly four public Skills:

1. `operating-coding-change` — the single implementation entry with Direct, Scoped,
   Governed, Evidence, and External Action modes;
2. `operating-code-review` — a review-only workflow;
3. `project-guidance` — Seed, Refresh, Refine, and Validate modes;
4. `setup-rootloom` — installation, upgrade, rollback, and optional global setup.

High-risk instructions become on-demand Change References. Analyzer, Baseline,
Contract, Seal, and Finalizer move to `plugins/rootloom/resources/evidence/` and are
loaded only by explicit Evidence Mode. Durable decision recording becomes a Governed
mode responsibility rather than a public Skill.

Project Memory moves to the separately installable experimental
`rootloom-memory` plugin under `experiments/rootloom-memory/`. Rootloom Core does not
discover or read Memory. The optional plugin preserves the
`rootloom-project-memory-v1` repository format.

Baseline v2–v4, Summary revision 5, change-contract, review-manifest, and seal wire
formats remain unchanged. The Evidence CLI location changes in 4.0, and the removed
`--include-project-memory` option has no Core replacement; users query the separate
Memory plugin explicitly before a task when they want historical leads.

## Alternatives considered

- Keep all nine Skills and improve descriptions — rejected because users would still
  choose among internal modes that share one owning workflow.
- Keep compatibility alias Skills — rejected because Codex discovery would continue to
  expose more than four public entries and preserve the routing cost.
- Delete Evidence or Memory — rejected because both capabilities remain useful when
  explicitly requested; the problem is default discovery and ownership, not existence.
- Keep Memory code in Core but hide its Skill — rejected because Core Evidence would
  retain a cross-feature context dependency and an ambiguous installation boundary.
- Split Evidence into another plugin — deferred because deterministic Evidence is a
  Change mode and shares Core privacy and path contracts; moving it to resources
  removes prompt cost without creating another installation choice.

## Consequences

- Positive: daily implementation has one entry and loads only the References required
  by risk and evidence mode.
- Positive: the main plugin has four discoverable Skills; Memory installation and
  context use are explicit.
- Positive: deterministic Evidence and Guidance scripts remain available without
  inflating ordinary Skill context.
- Negative: 3.x prompts naming removed Skills must migrate, and Evidence CLI paths
  change.
- Negative: Core Evidence no longer enriches its assessment from `.project-memory/`;
  callers must query Memory separately and verify every lead against current evidence.
- Operational: English/Chinese docs, website copy, Hook paths, tests, marketplace
  metadata, and repository validation must move atomically with the public surface.
- Operational: the 2026-07-29 candidate passed the comparative matrix. Its average
  elapsed-time improvement was only 0.11%, so the result clears the defined gate but
  does not establish a stable performance advantage.

## Verification

- Repository validation enumerates exactly four Core Skills and one separate Memory
  Skill.
- Focused tests exercise the relocated Evidence, Guidance, Hook, Setup, and Memory
  paths while preserving frozen Evidence wire revisions.
- `evals/core-reset/evaluate.py` compares 3.4 and 4.0 default Skill context and enforces
  at least 30% reduction for ordinary Change input.
- The No Rootloom / Rootloom 3.4 / Rootloom 4.0 behavioral matrix was executed and
  reviewed; `make core-reset-eval` validates all 30 cells and binds them to the current
  Core tree digest.

## Revisit when

- Comparative runs show worse scope control, false verification claims, root-cause
  alignment, governed coverage, or Evidence completeness than 3.4.
- Codex adds a first-class private or conditional Skill-routing mechanism that removes
  the discovery cost without packaging separation.
- Rootloom Memory reaches stable authority, lifecycle, and maintenance requirements
  that justify promotion out of `experiments/`.
