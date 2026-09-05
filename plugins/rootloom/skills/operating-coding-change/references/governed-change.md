# Governed change

Load this Reference for Tier 2 work. Keep a task-local governed packet and execution
plan; persist a plan only when the user or repository explicitly requires one.

## Authority and impact

Resolve the exact repository, branch, environment, service, account, data set, public
or persisted contract, producers, consumers, automation, generated clients, stored
data, mixed-version behavior, and irreversible point. Map security, privacy, cost,
performance, availability, rollout, rollback, and required authorization.

Ask only when authorization or a product/operational decision would materially change
the result. A current request naming an exact high-risk action authorizes that action
once; never infer broader authority.

## Diagnosis and stop conditions

For defects or incidents, record observed evidence, competing hypotheses, the ownership
path, violated invariant, and root cause. A complete repair requires evidence that
explains the material symptoms and rejects plausible alternatives.

An initially unknown cause is normal investigation, not automatic Tier 2 evidence.
Escalate for uncertainty only after bounded diagnosis still leaves materially different
owning boundaries, compatibility choices, risk assumptions, or repair scopes.

Stop the dependent high-risk action when cause, safe scope, compatibility, recovery,
or required authority cannot be established; continue independent authorized work. A reversible `MITIGATION` must name observability, rollback,
residual risk, and its removal or follow-up condition.

## Compatibility

First classify an artifact as regenerable internal state, irreplaceable persisted state,
or an established external contract. A version number, serialized file, retained release,
rollback requirement, or historical replay requirement does not establish a runtime
compatibility obligation.

Rollback, historical replay, and runtime compatibility are independent. Regenerable
internal artifacts use only the current contract: regenerate them for the new runtime,
restore the complete old release for rollback, and use the matching old runtime for
historical replay. Do not add an old-format reader, adapter, dual path, flag, or migration
unless repository evidence identifies an old consumer or stored instance that the new
runtime must support after cutover.

Only when that post-cutover consumer evidence exists, for APIs, schemas, config, CLI,
events, or persisted formats:

1. state old and new contracts;
2. inventory known producers and consumers;
3. prefer additive expansion before contraction;
4. define the old/new coexistence window;
5. use adapters, dual read/write, versioning, or flags only when they reduce real risk;
6. define the gate for removing the old path;
7. document migration and rollback or compensating recovery.

Pre-release status is not automatic permission to break established consumers, but
retaining an old release does not itself create such a consumer.

## Data, dependencies, and rollout

For authoritative or irreplaceable data changes evaluate backup/recovery, transactions, locks, timeouts, retries,
idempotency, partial failure, volume, rolling deployment, forward migration, and
rollback or compensation. Prefer expand → migrate/backfill → verify → contract.

For a production dependency, prove existing code is insufficient; inspect maintenance,
security, license, transitive packages, install scripts/binaries, runtime cost, and
supported platforms. Minimize manifest and lockfile churn.

Define dry-run or preview, failure detection, staged rollout, rollback, and the exact
irreversible gate. Never describe command submission as successful external state.

## Durable decisions

When the change accepts a durable architecture, public/persisted contract, dependency,
security, data, or operational choice, create or update the repository's decision
record using `<plugin-root>/resources/contracts/DECISION.template.md`. Record alternatives, evidence,
consequences, verification, revisit conditions, and supersession links. Do not persist
routine implementation history.

A Skills-only package may omit that template. When it is unavailable, use these same
headings directly: title and status metadata, Context, Evidence, Decision, Alternatives
considered, Consequences, Verification, and Revisit when. Do not skip the decision or
invent a different contract merely because the template file is absent.

## Completion

Verify the affected contracts, migration or coexistence behavior, and recovery path where
applicable. Challenge the material completion claim and disclose remaining gaps. Keep the
report proportional: describe the outcome, actual verification, external effects, and any
compatibility or rollback conditions the user needs. Omit inapplicable checklist fields.
A formal Evidence defect report may require `ROOT_CAUSE_ALIGNMENT: PASS`; ordinary reports
can explain the same conclusion in prose.
