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

Stop as `NO_GO` when cause, safe scope, compatibility, recovery, or required authority
cannot be established. A reversible `MITIGATION` must name observability, rollback,
residual risk, and its removal or follow-up condition.

## Compatibility

For APIs, schemas, config, CLI, events, or persisted formats:

1. state old and new contracts;
2. inventory known producers and consumers;
3. prefer additive expansion before contraction;
4. define the old/new coexistence window;
5. use adapters, dual read/write, versioning, or flags only when they reduce real risk;
6. define the gate for removing the old path;
7. document migration and rollback or compensating recovery.

Pre-release status is not automatic permission to break consumers.

## Data, dependencies, and rollout

For data changes evaluate backup/recovery, transactions, locks, timeouts, retries,
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

## Completion gate

Require contract/migration or mixed-version checks where applicable, the verification
contract, an adversarial challenge pass, rollback readiness, and an explicit residual
risk statement. For governed defect repair require `ROOT_CAUSE_ALIGNMENT: PASS`.
