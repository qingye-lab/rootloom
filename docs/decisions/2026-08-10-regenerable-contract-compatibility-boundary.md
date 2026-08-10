# Require consumer evidence before runtime compatibility

- Status: accepted
- Date: 2026-08-10
- Owners: Rootloom maintainers
- Scope: Change routing, governed compatibility, review guidance, and Core Reset evaluation
- Supersedes: none
- Superseded by: none

## Context

Rootloom 4.2 correctly described adapters, dual paths, versioning, and migration as
conditional risk controls, but Change routing named schemas and persisted contracts
before it distinguished authoritative data from regenerable internal records. A model
could therefore treat a versioned temporary artifact as a production compatibility
contract and conflate rollback or historical replay with a requirement for the new
runtime to read the old format.

## Evidence

| Claim | Kind | Source and environment | Observed | Reference | Freshness / redaction |
| --- | --- | --- | --- | --- | --- |
| The 4.2 Change route listed schemas and persisted contracts as Governed signals without a regenerability test | fact | immutable `v4.2.0` Skill | 2026-08-10 | `plugins/rootloom/skills/operating-coding-change/SKILL.md` | Public tag; no sensitive data |
| The 4.2 Governed compatibility section began with additive expansion and coexistence after inventorying consumers | fact | immutable `v4.2.0` Reference | 2026-08-10 | `plugins/rootloom/skills/operating-coding-change/references/governed-change.md` | Public tag; no sensitive data |
| Core Reset had no scenario where a versioned artifact was regenerable and the current runtime had to reject the old format | fact | released 14-scenario suite | 2026-08-10 | `evals/core-reset/scenarios.json`; `evals/core-reset/reports/4.2.0.md` | Repository source |

## Decision

A version number or serialized artifact alone does not create a governed compatibility
contract. Before routing schema or format work, Rootloom establishes whether the artifact
is authoritative or irreplaceable and whether the new runtime must encounter old
instances after cutover.

Regenerable internal artifacts remain Scoped unless another governed risk applies. Their
current runtime accepts only the current contract; rollback restores the complete old release,
and historical replay uses the matching old runtime. Rootloom may recommend an
old-format reader, adapter, dual path, flag, or migration only when repository evidence
identifies a real post-cutover consumer or stored instance.

The rule is owned by the Change route, Governed compatibility Reference, global working
agreement, and data/migration review Reference. It adds no Evidence format, state, or
mandatory artifact.

## Alternatives considered

- Rely on the existing phrase “only when they reduce real risk” — rejected because the
  missing artifact-authority classification occurs before that judgment and predictably
  over-routes versioned temporary records.
- Treat every versioned artifact as Governed but report compatibility as not applicable —
  rejected because loading the compatibility workflow already adds unnecessary prompt and
  decision cost.
- Remove compatibility guidance — rejected because established external consumers and
  irreplaceable stored state still need coexistence and migration controls.

## Consequences

- Positive: rollback, historical replay, and production compatibility become independent
  decisions.
- Positive: regenerable versioned records stay on the self-contained Scoped path and do
  not acquire legacy readers or migrations by default.
- Negative: semantic routing must determine artifact authority rather than relying on the
  presence of a schema or version number.
- Operational: the existing public API and data-migration scenarios retain Governed
  coverage; a new current-only regenerable-artifact scenario prevents regression.

## Verification

- Focused tests assert the new route wording, compatibility gate, and current-only scorer.
- Core Reset requires the regenerable versioned artifact to route Scoped with no Reference,
  accept only v2, and reject v1 and future versions.
- Repository validation binds the expanded 15-scenario release result to the final Core
  tree.

## Revisit when

- Real projects show that regenerable artifacts still require mixed-version runtime
  support for an operational reason not represented by a post-cutover consumer.
- Route evaluation cannot distinguish authoritative state from generated artifacts without
  unacceptable intervention or task cost.
