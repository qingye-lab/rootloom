---
name: operating-coding-change
description: The single Rootloom entry for code changes. Route Direct, Scoped, Governed, Evidence, and external-action work; repair owning invariants, preserve unrelated work, and report only verification that ran.
---

# Coding change

Deliver the smallest complete result. This Skill owns every implementation tier; never ask
the user to choose another Rootloom change workflow.

## 1. Resolve

Identify the outcome, repository and scope, constraints, non-goals, and proof. Read the host's
active project-instruction chain (for example, `AGENTS.md`) and the smallest evidence needed to route.
A dirty worktree is a preservation constraint, not an escalation signal. Preserve unrelated
user work and record relevant pre-existing failures.

For a defect, establish:

```text
symptom → trigger/state → owning boundary → violated invariant → root cause
```

If the cause is external or unproved, label a reversible workaround `MITIGATION` with its
gap, residual risk, and removal condition. Never call symptom suppression a fix.

## 2. Route

- `direct`: mechanical, local, reversible work with an unambiguous target and no
  behavior or contract decision. Load no Reference. Inspect the target, edit, run the
  smallest relevant check, inspect its diff, and report; skip broader inventory and
  challenge work unless target evidence is ambiguous.
- `scoped`: ordinary defects, feature slices, tests, refactors, or bounded multi-file
  work. Use this Skill's verification and challenge steps; load no Reference.
- `governed`: established shared/external public APIs, schemas, persisted contracts,
  migrations, security, infrastructure, deployment/release, destructive effects, major
  dependencies, material root-cause uncertainty remaining after bounded diagnosis,
  failed repairs, or substantial blast radius. A
  local callable/signature shape, file count, or dirty worktree alone is not public-contract evidence. Read
  [references/governed-change.md](references/governed-change.md) and
  [references/verification-contract.md](references/verification-contract.md).
- `evidence`: only when explicitly requested, repository-required, or needed for a
  release/governed decision. Read [references/evidence-mode.md](references/evidence-mode.md),
  [references/evidence-contract.md](references/evidence-contract.md), and
  [references/verification-contract.md](references/verification-contract.md).
Before the first edit in Governed or Evidence mode, load every required Reference relative
to this `SKILL.md`. If any required Reference cannot be loaded, stop instead of proceeding.
Modes compose. Governed external operations also read [references/external-actions.md](references/external-actions.md);
Evidence Mode records proof, never a replacement for diagnosis, discipline, or approval.
Initial cause uncertainty routes through bounded diagnosis, not directly to Governed:
an established local owner and repair boundary → `scoped`; materially different owners,
compatibility strategies, or high-risk assumptions remaining afterward → `governed`.

## 3. Change

Repair the invariant at its owner. Prefer one source of truth, normalized inputs, explicit
outputs and errors, existing architecture and dependencies, and native tests. Keep the diff
focused; reject speculative abstraction, unrelated cleanup, silent fallbacks, generated
churn, dependency refreshes, and weakened tests, types, security, observability, or errors.

Batch target, focused caller/test, and exact-scope status reads in one shell turn; after editing,
batch the focused check, diff check, final diff, and status unless a failure needs diagnosis.

## 4. Verify and challenge

Before choosing commands, map the primary path, owning invariant, and one adjacent negative
or alternate path. Run focused evidence first, then affected tests and type/lint,
build/package, runtime, rendered UI, or broader checks in proportion to impact. Prefer
fail-before/pass-after evidence for defects and classify failures. Never claim unrun checks.

Use one post-check challenge pass: test the strongest counterexample, inspect one
analogous caller or sibling, review the final diff and worktree, and remove mechanisms
that do not change a real decision.

## 5. Report

Lead with the observable outcome:
```text
Cause         Root cause or key design decision
Change        Files, behavior, compatibility, and external effects
Verification  Exact checks run, outcomes, and what each proves
Risk          Remaining gaps, rollback state, or unverified surfaces
```
For defect repair include `ROOT_CAUSE_ALIGNMENT: PASS | FAIL`; use `NOT_APPLICABLE` for
features, documentation, and mechanical work.
