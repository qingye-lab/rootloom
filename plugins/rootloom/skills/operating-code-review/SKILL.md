---
name: operating-code-review
description: Review code, diffs, pull requests, migrations, or architecture without modifying files. Lead with severity-ranked evidence-backed findings, challenge root-cause claims, and disclose cleared and unreviewed scope.
---

# Code review

Review only. Do not modify code unless the user explicitly changes the task.

## Scope

Read the requested diff plus the smallest sufficient callers, consumers, contracts,
tests, configuration, schemas, generated behavior, and one analogous sibling. Treat the
author's explanation and previous findings as leads, not proof.

Load specialized References only when Diff Facts require them:

- auth, trust boundaries, secrets, injection, or unsafe parsing:
  [security-review.md](references/security-review.md);
- migrations, DDL, ORM models, persistent serialization, or stored formats:
  [data-and-migration-review.md](references/data-and-migration-review.md);
- manifests, lockfiles, packaging, CI, deployment, or release changes:
  [dependency-and-release-review.md](references/dependency-and-release-review.md);
- formal UI, interaction, accessibility, responsive, or visual changes:
  [ui-review.md](references/ui-review.md).

## Finding standard

A finding must include:

- severity: Critical, High, Medium, or Low;
- exact file and line/symbol;
- failure mode and triggering conditions;
- evidence from a code path, contract mismatch, reproduction, or missing durable test;
- the smallest concrete correction;
- confidence: verified, strongly inferred, or uncertain.

Do not report style preferences as defects. Separate questions and optional
improvements from findings.

## Review method

Start from the failure surface and trace ownership, callers, and consumers. Read the
full relevant diff. Compare it with source-of-truth schemas, manifests, docs, CI, and
tests. Attempt to disprove the strongest completion claim and test negative paths,
cleanup, retries, cancellation, timeouts, partial failure, and mixed versions as
applicable.

A guard, flag, journal, abstraction, or workflow step earns its place only when the
review can name the observable failure, owning boundary, executable enforcement,
regression proof, and decision it changes.

For a defect repair, require:

```text
ROOT_CAUSE_ALIGNMENT: PASS | FAIL | NOT_APPLICABLE
```

`PASS` requires evidence for the trigger, violated invariant, root cause, and repair at
the owning boundary. Caller-only special cases, swallowed exceptions, arbitrary
retries/delays, widened timeouts, silent defaults, duplicated state, or weakened tests
are possible false fixes until repository evidence proves otherwise.

## Output

Start with `## Findings`, ordered by severity. Then state
`ROOT_CAUSE_ALIGNMENT`. Add questions or optional improvements only when useful.

Finish with verification gaps. If there are no material findings, say so explicitly
and list the concrete cleared surfaces, strongest counterexample attempted, analogous
implementation checked, and unavailable or unreviewed evidence.
