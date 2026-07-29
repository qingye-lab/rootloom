# <Task title>

## Status

- State: draft | in progress | blocked | complete
- Owner: <name or agent>
- Last updated: <YYYY-MM-DD>
- Task type: <bug/debugging, architecture, data/schema/migration, security, release/deploy, production operation, or other>
- Risk: Tier 2 (Governed)

## Goal and observable success

<What changes for users or systems, and how completion is proven.>

## Non-goals

- <Explicitly excluded scope.>

## Baseline evidence

- <Current behavior, failing test, trace, metrics, relevant paths.>
- <Pre-existing failures or dirty-tree constraints.>

### Evidence provenance

| Claim | Kind | Source and environment | Observed | Reference | Freshness / redaction |
| --- | --- | --- | --- | --- | --- |
| <material fact or inference> | fact | <repository, runtime, issue, or external system> | <time or window> | <path, command, artifact, query, trace, or correlation ID> | <notes> |

## Governed defect diagnosis

- Observed failure: <behavior and trigger, or not applicable>
- Competing hypotheses: <candidate causes and evidence>
- Ownership path: <where the behavior or state is owned>
- Violated invariant: <rule that failed>
- Root cause: <evidence-backed cause, NO_GO, or explicit MITIGATION>
- Root-cause alignment: <PASS, FAIL, or NOT_APPLICABLE>

## Constraints and invariants

- <Compatibility, security, data, performance, legal, cost, or operational rules.>

## Impact map

- Producers: <paths/services>
- Consumers: <paths/services>
- Persisted data: <tables/files/topics or none>
- Public contracts: <APIs/schemas/config/CLI/events>
- Generated artifacts: <paths/generator or none>
- External systems: <accounts/environments/resources or none>

## Design and decisions

- Ownership: <where state/data/behavior lives>
- Interfaces: <inputs, outputs, errors, contracts>
- Dependency direction: <allowed edges>
- Compatibility window: <old/new coexistence>
- Alternatives rejected: <option and evidence-based reason>

## Implementation sequence

1. <Small independently verifiable expansion step.>
2. <Migration/backfill/compatibility step.>
3. <Verification and rollout step.>
4. <Contraction only after its gate.>

## Rollout, failure, and rollback

- Dry-run/preview: <procedure>
- Mixed-version behavior: <description>
- Failure detection: <logs/metrics/errors/checks>
- Rollback or compensation: <procedure>
- Irreversible point: <none or exact approval gate>

## Verification

- Original failure path: `<command, test, trace, or observation>`
- Owning-boundary invariant: `<command, test, assertion, or contract proof>`
- Adjacent negative/alternate path: `<command, test, or observation>`
- Focused tests: `<commands>`
- Contract/migration tests: `<commands>`
- Type/lint/build/package: `<commands>`
- UI/browser evidence: `<routes, states, screenshots>`
- Security/dependency checks: `<commands>`
- Post-action verification: `<checks>`

## Risks

- Risk: <failure mode>
  - Mitigation: <control>
  - Residual risk: <what remains>

## Decision log

- <YYYY-MM-DD> — <decision, evidence, consequence>

## Durable decision records

- <Accepted ADR/decision-record link, or none because no durable decision was created.>
