---
name: operating-coding-change
description: The single Rootloom entry point for code changes. Route mechanical, scoped, governed, evidence-strict, and external-action work; diagnose defects at the owning boundary, preserve unrelated work, and report only verification that actually ran.
---

# Coding change

Deliver the observable result with the smallest complete change. This Skill owns every implementation tier; do not ask the user to select a second Rootloom change workflow.

## 1. Resolve the task

Identify the requested outcome, repository and scope, constraints, non-goals, and proof
of completion. Read the active `AGENTS.md` chain and inspect only enough repository
evidence to route the mode. A dirty worktree is a preservation constraint, not by
itself a reason to escalate. Preserve unrelated user work and record relevant
pre-existing failures.

For a defect, establish this evidence chain before editing:

```text
symptom → trigger/state → owning boundary → violated invariant → root cause
```

If the cause is external or cannot be proved, label a reversible workaround
`MITIGATION` with its gap, residual risk, and removal condition. Never present symptom
suppression as a root-cause fix.

## 2. Route the mode

- `direct`: mechanical, local, reversible work with an unambiguous target and no
  behavior or contract decision. Load no Reference. Inspect the exact target, edit it,
  run the smallest relevant check, inspect its diff, and report; skip broader inventory
  and challenge work unless target evidence makes the classification ambiguous.
- `scoped`: ordinary defects, feature slices, tests, refactors, or bounded multi-file
  work. Read [references/verification-contract.md](references/verification-contract.md).
- `governed`: established shared/external public APIs, schemas, persisted contracts,
  migrations, security boundaries, infrastructure, deployment/release, destructive
  effects, major dependencies, uncertain root cause, failed repairs, or substantial
  blast radius. A local callable/signature shape, file count, or dirty worktree alone
  is not public-contract evidence. Read
  [references/governed-change.md](references/governed-change.md) and
  [references/verification-contract.md](references/verification-contract.md).
- `evidence`: only when the user explicitly requests a machine evidence bundle, the
  repository requires one, or a release/governed decision needs it. Read
  [references/evidence-mode.md](references/evidence-mode.md) and
  [references/evidence-contract.md](references/evidence-contract.md), plus
  [references/verification-contract.md](references/verification-contract.md).
Modes compose. Governed external operations also require [references/external-actions.md](references/external-actions.md).
Evidence Mode adds a recording layer; it never replaces semantic diagnosis, change discipline, or approval.

## 3. Make the change

Repair the invariant at the boundary that owns the behavior. Prefer one source of
truth, normalized inputs, explicit outputs and errors, cohesive functions, existing
architecture and dependencies, and repository-native test style.

Keep the diff focused. Reject speculative abstractions, unrelated cleanup, silent
fallbacks, generated churn, broad dependency refreshes, and weakened tests, types,
security, observability, or error handling. Do not hand-edit generated or vendored
output when a canonical generator exists.

## 4. Verify and challenge

Prove the primary path, the owning-boundary invariant, and an adjacent negative,
edge, or alternate path. Run focused checks first, then broader tests, type/lint,
build/package, runtime, or rendered UI checks in proportion to impact.

After checks, inspect the actual diff from a fresh adversarial position: test the
strongest plausible counterexample, inspect one analogous caller or sibling, and
remove mechanisms that do not change a real decision. Never claim an unrun check
passed.

## 5. Report

Lead with the observable outcome, then report:

```text
Cause         Root cause or key design decision
Change        Files, behavior, compatibility, and external effects
Verification  Exact checks run, outcomes, and what each proves
Risk          Remaining gaps, rollback state, or unverified surfaces
```

For defect repair include `ROOT_CAUSE_ALIGNMENT: PASS | FAIL`; use `NOT_APPLICABLE`
for features, documentation, and mechanical work.
