---
name: operating-coding-change
description: Complete scoped code changes with proportional verification; load governed, Evidence, and external-action procedures only when needed.
---

# Coding change

Implement the user's requested outcome within the active repository guidance and authorized
scope. A question or review alone does not authorize a repair. Preserve unrelated changes;
a dirty worktree is a preservation constraint, not a reason to stop or escalate.

## Diagnose and route

Read the smallest evidence needed to identify the owner and verification boundary. For a
defect, connect the observed trigger, violated invariant, root cause, and proposed repair.
Initial uncertainty calls for bounded diagnosis; escalate only when materially different
owners, compatibility choices, or high-risk assumptions remain. Label an unproved workaround
as mitigation and explain its limitation and removal condition.

Choose the route internally; do not ask the user to choose a workflow:

- `direct`: mechanical, local, reversible work. Inspect, edit, and check the target; no
  Reference or separate challenge pass is required.
- `scoped`: bounded defects, features, tests, refactors, and documentation. Use the checks
  below without loading additional References by default.
- `governed`: changes affecting security, production, infrastructure, destructive effects,
  major dependencies, established public APIs, irreplaceable persisted contracts, or a
  materially uncertain blast radius. Read [governed-change.md](references/governed-change.md)
  and [verification-contract.md](references/verification-contract.md) before dependent edits.
  Regenerable internal artifacts, file count, and keyword mentions alone do not trigger this
  route; identify real consumers and changed behavior.
- `evidence`: only on explicit request or an applicable repository requirement. Read
  [evidence-mode.md](references/evidence-mode.md), [evidence-contract.md](references/evidence-contract.md),
  and [verification-contract.md](references/verification-contract.md). Evidence records proof;
  it does not grant authority or replace diagnosis.

For deployment, release, infrastructure, production data, or other external execution, read
[external-actions.md](references/external-actions.md). Verify exact authorization; preserve
explicit approval gates and do not infer permission for destructive actions, purchases,
credential/permission changes, incompatible contracts, or scope expansion. If a required
procedure or authorization is unavailable, stop only the dependent action and continue
independent authorized work. Platform and hard-deny controls remain authoritative.

## Implement and verify

Repair at the owning boundary with existing architecture and dependencies. Avoid unrelated
cleanup, speculative abstractions, silent fallback, and weakened tests or security. Protect
established external contracts and irreplaceable state; do not add compatibility paths
without evidence of a consumer that needs them.

Check the requested behavior and owning invariant. Exercise a failure or alternate path,
or inspect an analogous caller, when it addresses a concrete risk. For documentation,
check a plausible misinterpretation instead of inventing runtime tests. Use the smallest
relevant test, type/lint, build, runtime, or rendered-UI evidence; a full suite or matrix is
needed only for unbounded impact, shared test infrastructure, or an explicit applicable gate.
After checks pass, expand only for new changes, failures, or unresolved concerns.

Review the final diff for scope and preservation of user work. Report the result, relevant
verification actually observed, and material limitations. Never claim an unrun or failed
check passed. For defect repair, explain whether the change fixes the root cause; use
`ROOT_CAUSE_ALIGNMENT: PASS | FAIL` only when a formal reporting contract requests it.

## Large artifacts

Start with bounded reads sufficient for the task. Use [artifact-context.md](references/artifact-context.md)
when repeated access or substantial context cost makes receipt reuse worthwhile, or when the
user requests isolation. Worker availability is not a prerequisite for ordinary bounded
analysis. Respect explicit isolation, file-access, retention, and upload restrictions.
